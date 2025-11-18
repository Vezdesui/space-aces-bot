from __future__ import annotations

import logging
from typing import Any, Mapping, Optional

from space_aces_bot.core.actions import ActionType, BotAction
from space_aces_bot.core.game_state import GameState
from space_aces_bot.core.interfaces import Combat

logger = logging.getLogger(__name__)


class DummyCombat(Combat):
    """Combat module stub that never initiates fights."""

    def decide(self, state: GameState) -> BotAction | None:
        logger.info("Combat.decide: no combat action (dummy).")
        return None


class BasicCombat(Combat):
    """Basic combat state machine based on distance and per-target tick counters."""

    def __init__(
        self,
        combat_cfg: Mapping[str, Any] | None = None,
        logger: Optional[logging.Logger] = None,
    ) -> None:
        cfg: Mapping[str, Any] = combat_cfg or {}

        self._enabled: bool = bool(cfg.get("enabled", True))
        self._max_target_distance: float = float(cfg.get("max_target_distance", 0.2))
        self._disengage_distance: float = float(cfg.get("disengage_distance", 0.35))
        # Interpret max_target_time_seconds as a soft cap on per-target ticks.
        self._max_target_ticks: int = int(cfg.get("max_target_time_seconds", 60))

        self._logger = logger or logging.getLogger(__name__)

    def decide(self, state: GameState) -> BotAction | None:
        """Control tactical behaviour for the current target (approach, attack, disengage)."""

        log = self._logger

        if not self._enabled:
            if state.in_combat:
                log.info(
                    "BasicCombat: combat disabled, leaving combat for target_id=%s",
                    state.current_target_id,
                )
            state.in_combat = False
            return None

        # No target selected: Combat does not choose targets, Farm does.
        if state.current_target_id is None:
            state.in_combat = False
            state.ticks_with_current_target = 0
            return None

        target = state.get_current_target()

        # Target disappeared from the NPC list.
        if target is None:
            if state.in_combat:
                log.info(
                    "BasicCombat: current target_id=%s disappeared, stopping combat.",
                    state.current_target_id,
                )
            state.current_target_id = None
            state.in_combat = False
            state.ticks_with_current_target = 0
            return None

        ship_pos = state.ship.position
        target_pos = target.position

        dx = target_pos.x - ship_pos.x
        dy = target_pos.y - ship_pos.y
        distance = (dx * dx + dy * dy) ** 0.5

        ticks = state.ticks_with_current_target

        # If the target is too far away or we've spent too many ticks,
        # consider it lost and disengage.
        if distance >= self._disengage_distance or (
            self._max_target_ticks > 0 and ticks >= self._max_target_ticks
        ):
            log.info(
                "BasicCombat: disengaging from target_id=%s "
                "(distance=%.3f, ticks=%d, max_ticks=%d).",
                target.id,
                distance,
                ticks,
                self._max_target_ticks,
            )
            state.current_target_id = None
            state.in_combat = False
            state.ticks_with_current_target = 0
            return None

        # We have a valid target within engagement envelope.
        if not state.in_combat:
            log.info(
                "BasicCombat: entering combat with target_id=%s (distance=%.3f).",
                target.id,
                distance,
            )
            state.in_combat = True

        # If we are still too far, move closer to the NPC.
        if distance > self._max_target_distance:
            if distance > 0:
                rel_x = dx / distance
                rel_y = dy / distance
            else:
                rel_x = 0.0
                rel_y = 0.0

            log.info(
                "BasicCombat: moving towards target_id=%s (distance=%.3f).",
                target.id,
                distance,
            )

            return BotAction(
                type=ActionType.MOVE,
                target_id=state.current_target_id,
                meta={
                    "rel_x": rel_x,
                    "rel_y": rel_y,
                    "reason": "basic_combat_approach",
                },
            )

        # We are in range: attack the current target.
        log.info(
            "BasicCombat: attacking target_id=%s (distance=%.3f).",
            target.id,
            distance,
        )

        return BotAction(
            type=ActionType.ATTACK,
            target_id=state.current_target_id,
            meta={"reason": "basic_combat_attack"},
        )
