from __future__ import annotations

import logging

from space_aces_bot.core.game_state import GameState
from space_aces_bot.core.interfaces import Combat

logger = logging.getLogger(__name__)


class DummyCombat(Combat):
    """Combat module stub that never initiates fights."""

    def decide(self, state: GameState):
        logger.info("Combat.decide: no combat action (dummy).")
        return None

