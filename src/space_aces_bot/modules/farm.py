from __future__ import annotations

import logging
from typing import Any, Mapping, Optional, Sequence

from space_aces_bot.core.actions import ActionType, BotAction
from space_aces_bot.core.game_state import GameState, Npc, Resource, Ship
from space_aces_bot.core.interfaces import Farm

logger = logging.getLogger(__name__)


class DummyFarm(Farm):
    """Placeholder farming module that defers to navigation patrol.

    At this stage the farm logic does not drive movement directly. It
    periodically logs that no farming targets were found so that the
    navigation patrol can control movement.
    """

    def __init__(self, log_interval: int = 10) -> None:
        self._tick_counter = 0
        self._log_interval = max(1, int(log_interval))

    def decide(self, state: GameState) -> BotAction | None:  # noqa: ARG002 - state reserved for future use
        self._tick_counter += 1

        if self._tick_counter % self._log_interval == 0:
            logger.info(
                "Farm.decide: no farming targets; deferring to navigation patrol "
                "(tick=%s).",
                self._tick_counter,
            )

        # No farming action yet; navigation patrol defines movement.
        return None


class BasicFarm(Farm):
    """Basic farming strategy that selects NPC targets for combat."""

    def __init__(
        self,
        farm_cfg: Mapping[str, Any] | None = None,
        combat_cfg: Mapping[str, Any] | None = None,
        logger: Optional[logging.Logger] = None,
    ) -> None:
        cfg: Mapping[str, Any] = farm_cfg or {}
        combat_cfg = combat_cfg or {}

        self._collect_boxes: bool = bool(cfg.get("collect_boxes", False))
        self._hunt_npcs: bool = bool(cfg.get("hunt_npcs", True))

        npc_priority_raw: Any = combat_cfg.get("npc_priority", ())
        if isinstance(npc_priority_raw, str):
            priorities: Sequence[str] = [
                part.strip() for part in npc_priority_raw.split(",") if part.strip()
            ]
        elif isinstance(npc_priority_raw, Sequence):
            priorities = [str(p) for p in npc_priority_raw]
        else:
            priorities = []

        self._npc_priority = list(priorities)
        self._logger = logger or logging.getLogger(__name__)

    @staticmethod
    def _distance(ship: Ship, resource: Resource) -> float:
        dx = ship.position.x - resource.position.x
        dy = ship.position.y - resource.position.y
        return (dx * dx + dy * dy) ** 0.5

    def _select_nearest_resource(self, state: GameState) -> Optional[Resource]:
        if not state.resources:
            return None

        ship = state.ship
        resources = list(state.resources.values())
        resources.sort(key=lambda res: self._distance(ship, res))
        return resources[0]

    def _select_target(self, state: GameState) -> Optional[Npc]:
        """Select an NPC target according to the configured priority."""

        if not state.npcs:
            return None

        npcs = list(state.npcs.values())

        if not self._npc_priority:
            # No priority configured: pick the first NPC.
            return npcs[0]

        def sort_key(npc: Npc) -> int:
            try:
                return self._npc_priority.index(npc.npc_type)
            except ValueError:
                # Types not in the priority list are deprioritised.
                return len(self._npc_priority)

        npcs.sort(key=sort_key)
        return npcs[0]

    def decide(self, state: GameState) -> BotAction | None:
        """Decide on farming behaviour: collect boxes first, then hunt NPCs."""

        log = self._logger

        # 1. Try to collect resource boxes if enabled.
        if self._collect_boxes and state.resources:
            resource = self._select_nearest_resource(state)
            if resource is not None:
                rel_x = resource.position.x
                rel_y = resource.position.y
                log.info(
                    "BasicFarm: moving to resource %s kind=%s at rel=(%.3f, %.3f)",
                    resource.id,
                    getattr(resource, "kind", "unknown"),
                    rel_x,
                    rel_y,
                )
                return BotAction(
                    type=ActionType.MOVE,
                    position=None,
                    meta={
                        "rel_x": rel_x,
                        "rel_y": rel_y,
                        "target_resource_id": resource.id,
                        "target_resource_kind": getattr(resource, "kind", "unknown"),
                    },
                )

        # 2. If no boxes or collection disabled, fall back to NPC hunting.
        if not self._hunt_npcs:
            return None

        # If we already have a target, keep it; Combat decides what to do.
        if state.current_target_id is not None:
            return None

        target = self._select_target(state)

        if target is None:
            log.info("BasicFarm: no NPCs available to farm")
            return None

        state.current_target_id = target.id
        state.in_combat = True
        state.ticks_with_current_target = 0

        log.info("BasicFarm: selected NPC %s as new target", target.id)

        # Selecting a target does not itself produce an action; Combat
        # will drive movement/attacks on subsequent ticks.
        return None
