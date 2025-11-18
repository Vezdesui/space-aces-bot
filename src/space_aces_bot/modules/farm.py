from __future__ import annotations

import logging

from space_aces_bot.core.actions import ActionType, BotAction
from space_aces_bot.core.game_state import GameState
from space_aces_bot.core.interfaces import Farm

logger = logging.getLogger(__name__)


class DummyFarm(Farm):
    """Simple farming module that occasionally idles."""

    def __init__(self) -> None:
        self._counter = 0

    def decide(self, state: GameState):
        # As a simple heuristic, every second call we return an IDLE action.
        self._counter += 1
        if self._counter % 2 == 0:
            logger.info("Farm.decide: returning IDLE action (dummy).")
            return BotAction(type=ActionType.IDLE, meta={"reason": "dummy_farm"})

        logger.info("Farm.decide: no farming action this tick.")
        return None
