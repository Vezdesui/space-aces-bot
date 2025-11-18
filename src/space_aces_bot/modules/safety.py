from __future__ import annotations

import logging

from space_aces_bot.core.game_state import GameState
from space_aces_bot.core.interfaces import Safety

logger = logging.getLogger(__name__)


class DummySafety(Safety):
    """Safety module stub that always reports no danger."""

    def assess(self, state: GameState) -> int:
        logger.info("Safety.assess: danger level is 0 (dummy).")
        return 0

    def decide(self, state: GameState):
        logger.info("Safety.decide: no safety action required (dummy).")
        return None

