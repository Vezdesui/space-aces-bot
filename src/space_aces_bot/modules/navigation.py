from __future__ import annotations

import logging
from typing import Optional

from space_aces_bot.core.actions import ActionType, BotAction
from space_aces_bot.core.game_state import GameState, Position
from space_aces_bot.core.interfaces import Navigation

logger = logging.getLogger(__name__)


class SimpleNavigation(Navigation):
    """Very simple navigation module that moves towards a destination."""

    def __init__(self) -> None:
        self.destination: Optional[Position] = None

    def set_destination(self, position: Position) -> None:
        logger.info("Navigation: setting destination to %s", position)
        self.destination = position

    def tick(self, state: GameState) -> BotAction | None:
        if self.destination is None:
            logger.debug("Navigation.tick: no destination set, doing nothing.")
            return None

        ship_pos = state.ship.position
        dest = self.destination

        if ship_pos.x == dest.x and ship_pos.y == dest.y:
            logger.debug("Navigation.tick: already at destination, no move.")
            return None

        logger.info(
            "Navigation.tick: moving from (%s, %s) towards (%s, %s)",
            ship_pos.x,
            ship_pos.y,
            dest.x,
            dest.y,
        )

        return BotAction(
            type=ActionType.MOVE,
            position=dest,
            meta={"reason": "move_to_destination"},
        )

