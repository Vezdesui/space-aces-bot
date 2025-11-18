from __future__ import annotations

import logging
from dataclasses import replace

from space_aces_bot.core.actions import ActionType, BotAction
from space_aces_bot.core.game_state import GameState, Position
from space_aces_bot.core.interfaces import Safety

logger = logging.getLogger(__name__)


# Simple heuristics for safety assessment.
_EDGE_WARN_THRESHOLD = 0.8
_EDGE_DANGER_THRESHOLD = 1.2
_STATIONARY_EPSILON = 1e-3
_STATIONARY_TICKS_WARN = 50
_STATIONARY_TICKS_ESCAPE = 100
_ESCAPE_DANGER_THRESHOLD = 70


class BasicSafety(Safety):
    """Basic safety module with simple danger heuristics.

    The implementation considers three factors:

    * proximity to notional map edges (based on ship position),
    * the ship being stationary for many ticks,
    * low hit points relative to max HP.
    """

    def __init__(self) -> None:
        self._last_position: Position | None = None
        self._stationary_ticks: int = 0

    def assess(self, state: GameState) -> int:
        """Return an integer danger score in the range 0–100."""

        ship = state.ship
        pos = ship.position

        danger = 0

        # HP heuristic.
        hp_ratio = 1.0
        if ship.max_hp > 0:
            hp_ratio = max(0.0, min(1.0, ship.hp / ship.max_hp))
            if hp_ratio <= 0.3:
                danger += 60
            elif hp_ratio <= 0.6:
                danger += 30

        # Edge heuristic (treat position as normalised around 0.0).
        x = pos.x
        y = pos.y
        if abs(x) >= _EDGE_DANGER_THRESHOLD or abs(y) >= _EDGE_DANGER_THRESHOLD:
            danger += 40
        elif abs(x) >= _EDGE_WARN_THRESHOLD or abs(y) >= _EDGE_WARN_THRESHOLD:
            danger += 20

        # Stationary heuristic.
        if self._last_position is not None:
            dx = pos.x - self._last_position.x
            dy = pos.y - self._last_position.y
            if dx * dx + dy * dy <= _STATIONARY_EPSILON * _STATIONARY_EPSILON:
                self._stationary_ticks += 1
            else:
                self._stationary_ticks = 0
        else:
            self._stationary_ticks = 0

        self._last_position = replace(pos)

        if self._stationary_ticks >= _STATIONARY_TICKS_ESCAPE:
            danger += 40
        elif self._stationary_ticks >= _STATIONARY_TICKS_WARN:
            danger += 20

        danger = max(0, min(100, danger))

        # Derived flags for more descriptive logging.
        low_hp = hp_ratio <= 0.6
        near_edge = abs(x) >= _EDGE_WARN_THRESHOLD or abs(y) >= _EDGE_WARN_THRESHOLD

        # Emit a detailed debug line only once in a while to avoid log spam.
        tick = getattr(state, "tick_counter", 0)
        if tick % 10 == 0:
            logger.debug(
                (
                    "Safety.assess: tick=%d danger=%d "
                    "(near_edge=%s, low_hp=%s, idle_ticks=%d, "
                    "hp_ratio=%.2f, pos=(%.3f, %.3f))"
                ),
                tick,
                danger,
                near_edge,
                low_hp,
                self._stationary_ticks,
                hp_ratio,
                pos.x,
                pos.y,
            )

        return danger

    def decide(self, state: GameState) -> BotAction | None:
        """Return an ESCAPE-like MOVE action when danger is high."""

        danger = self.assess(state)
        if danger < _ESCAPE_DANGER_THRESHOLD:
            logger.debug(
                "Safety.decide: danger=%d below escape threshold=%d, no action.",
                danger,
                _ESCAPE_DANGER_THRESHOLD,
            )
            return None

        # For now, escape towards the map centre in normalised coordinates.
        safe_rel_x = 0.5
        safe_rel_y = 0.5
        reason = "basic_safety_escape"

        logger.info(
            "Safety.decide: danger=%d >= %d, issuing ESCAPE MOVE to rel=(%.3f, %.3f).",
            danger,
            _ESCAPE_DANGER_THRESHOLD,
            safe_rel_x,
            safe_rel_y,
        )
        logger.info(
            "Safety.decide: ESCAPE triggered (reason=%s, danger=%d)",
            reason,
            danger,
        )

        return BotAction(
            type=ActionType.MOVE,
            position=None,
            meta={
                "rel_x": safe_rel_x,
                "rel_y": safe_rel_y,
                "escape": True,
                "danger": danger,
                "reason": reason,
            },
        )
