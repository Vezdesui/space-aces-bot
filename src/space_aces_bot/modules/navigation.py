from __future__ import annotations

import logging
from typing import List, Optional, Tuple

from space_aces_bot.core.actions import ActionType, BotAction
from space_aces_bot.core.game_state import GameState, Position
from space_aces_bot.core.interfaces import Navigation

logger = logging.getLogger(__name__)


class SimpleNavigation(Navigation):
    """Simple navigation module that patrols predefined waypoints.

    The module keeps a list of patrol waypoints in normalised map
    coordinates (values between 0.0 and 1.0). On every ``tick`` it
    advances a tick counter and, once enough ticks have passed, emits
    a MOVE action targeting the next waypoint in the patrol loop.
    """

    def __init__(self, tick_interval: int = 10) -> None:
        # Optional world-space destination set via `set_destination`. It is
        # currently stored for future use; patrol is based on normalised
        # waypoints.
        self.destination: Optional[Position] = None

        # List of patrol points in normalised coordinates (rel_x, rel_y).
        self._patrol_points: List[Tuple[float, float]] = [
            (0.2, 0.2),
            (0.8, 0.2),
            (0.8, 0.8),
            (0.2, 0.8),
        ]
        self._current_index: int = 0
        self._ticks_since_last_move: int = 0
        self._tick_interval: int = max(1, int(tick_interval))

    def set_destination(self, position: Position) -> None:
        logger.info("Navigation: setting destination to %s", position)
        self.destination = position

    def tick(self, state: GameState) -> BotAction | None:
        if not self._patrol_points:
            logger.debug("Navigation.tick: no patrol points configured, doing nothing.")
            return None

        self._ticks_since_last_move += 1
        if self._ticks_since_last_move < self._tick_interval:
            logger.debug(
                "Navigation.tick: waiting before next patrol move "
                "(ticks_since_last_move=%s, interval=%s).",
                self._ticks_since_last_move,
                self._tick_interval,
            )
            return None

        self._ticks_since_last_move = 0

        waypoint_index = self._current_index
        rel_x, rel_y = self._patrol_points[waypoint_index]

        logger.info(
            "Navigation.tick: selecting patrol waypoint %s at rel=(%.3f, %.3f).",
            waypoint_index,
            rel_x,
            rel_y,
        )

        self._current_index = (self._current_index + 1) % len(self._patrol_points)

        action = BotAction(
            type=ActionType.MOVE,
            position=self.destination,
            meta={
                "rel_x": rel_x,
                "rel_y": rel_y,
                "waypoint_index": waypoint_index,
                "reason": "patrol_waypoint",
            },
        )

        logger.info("Navigation.tick: emitting MOVE action %s", action)
        return action
