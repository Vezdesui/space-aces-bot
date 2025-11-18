from __future__ import annotations

import logging
import random
from typing import Optional

from space_aces_bot.core.actions import ActionType, BotAction
from space_aces_bot.core.game_state import GameState, Position
from space_aces_bot.core.interfaces import Navigation

logger = logging.getLogger(__name__)

MOVE_EVERY_N_TICKS = 10


class SimpleNavigation(Navigation):
    """Simple navigation module with patrol and escape modes.

    In ``patrol`` mode the module walks a list of normalised waypoints
    (values between 0.0 and 1.0) and periodically issues MOVE actions.
    In ``escape`` mode it emits MOVE actions towards a predefined safe
    point on every tick.
    """

    def __init__(self) -> None:
        # Optional world-space destination set via `set_destination`.
        self.destination: Optional[Position] = None

        # List of patrol points in normalised coordinates (rel_x, rel_y).
        self._patrol_points: list[tuple[float, float]] = [
            (0.2, 0.2),
            (0.8, 0.2),
            (0.8, 0.8),
            (0.2, 0.8),
        ]
        self._current_index: int = 0
        self._ticks_since_last_move: int = 0

        # Mode: "patrol" or "escape".
        self._mode: str = "patrol"

    def set_destination(self, position: Position) -> None:
        logger.info("Navigation: setting destination to %s", position)
        self.destination = position

    # ------------------------------------------------------------------
    # Mode control
    # ------------------------------------------------------------------
    def enter_escape_mode(self) -> None:
        self._mode = "escape"
        self._ticks_since_last_move = 0

    def enter_patrol_mode(self) -> None:
        if self._mode != "patrol":
            self._mode = "patrol"
            self._ticks_since_last_move = 0

    # ------------------------------------------------------------------
    # Tick logic
    # ------------------------------------------------------------------
    def tick(self, state: GameState) -> BotAction | None:  # noqa: ARG002
        """Return periodic MOVE actions in patrol/escape modes.

        - In ``escape`` mode a MOVE towards a fixed safe point is
          returned every tick.
        - In ``patrol`` mode a MOVE towards the next waypoint is
          returned roughly every ``MOVE_EVERY_N_TICKS`` ticks.
        """

        self._ticks_since_last_move += 1
        logger.debug(
            "Navigation.tick: mode=%s, ticks_since_last_move=%d",
            self._mode,
            self._ticks_since_last_move,
        )

        # Escape mode: always move towards a fixed safe point.
        if self._mode == "escape":
            safe_x, safe_y = 0.5, 0.5
            logger.info(
                "Navigation.tick: ESCAPE MOVE to safe point rel=(%.3f, %.3f).",
                safe_x,
                safe_y,
            )
            return BotAction(
                type=ActionType.MOVE,
                position=None,
                meta={"rel_x": safe_x, "rel_y": safe_y, "escape": True},
            )

        # Patrol mode: emit MOVE roughly every MOVE_EVERY_N_TICKS ticks.
        if self._mode == "patrol":
            if self._ticks_since_last_move < MOVE_EVERY_N_TICKS:
                logger.debug(
                    "Navigation.tick: PATROL idle "
                    "(ticks_since_last_move=%d, move_every=%d).",
                    self._ticks_since_last_move,
                    MOVE_EVERY_N_TICKS,
                )
                return None

            self._ticks_since_last_move = 0

            if not self._patrol_points:
                logger.debug(
                    "Navigation.tick: no patrol points configured, doing nothing."
                )
                return None

            base_x, base_y = self._patrol_points[self._current_index]

            dx = random.uniform(-0.05, 0.05)
            dy = random.uniform(-0.05, 0.05)
            rel_x = min(max(base_x + dx, 0.05), 0.95)
            rel_y = min(max(base_y + dy, 0.05), 0.95)

            # Advance waypoint index (wrap around).
            self._current_index = (self._current_index + 1) % len(self._patrol_points)

            logger.info(
                "Navigation.tick: PATROL MOVE to rel=(%.3f, %.3f) "
                "(base_rel=(%.3f, %.3f), waypoint_index=%d).",
                rel_x,
                rel_y,
                base_x,
                base_y,
                self._current_index,
            )

            return BotAction(
                type=ActionType.MOVE,
                position=None,
                meta={
                    "rel_x": rel_x,
                    "rel_y": rel_y,
                    "waypoint_index": self._current_index,
                },
            )

        logger.debug("Navigation.tick: unknown mode '%s', doing nothing.", self._mode)
        return None
