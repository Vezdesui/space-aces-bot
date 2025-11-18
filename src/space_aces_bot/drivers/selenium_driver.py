from __future__ import annotations

import logging

from space_aces_bot.core.actions import BotAction
from space_aces_bot.core.game_state import GameState
from space_aces_bot.core.interfaces import Driver

logger = logging.getLogger(__name__)


class DummyDriver(Driver):
    """Driver stub that only logs actions instead of executing them."""

    def execute(self, action: BotAction, state: GameState) -> None:
        logger.info(
            "Driver.execute: action=%s target_id=%s position=%s meta=%s tick=%s",
            action.type,
            action.target_id,
            action.position,
            action.meta,
            state.tick_counter,
        )

