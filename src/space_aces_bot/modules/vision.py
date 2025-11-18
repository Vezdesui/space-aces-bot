from __future__ import annotations

import logging

from space_aces_bot.core.game_state import GameState
from space_aces_bot.core.interfaces import Vision

logger = logging.getLogger(__name__)


class DummyVision(Vision):
    """Dummy vision module that pretends to update the game state."""

    def update_state(self, state: GameState) -> None:
        logger.info("Vision.update_state: updating game state (dummy).")
        # For now we just bump the tick counter slightly to show activity.
        state.tick_counter += 1

    def screenshot(self):
        logger.debug("Vision.screenshot: returning dummy screenshot.")
        return None

