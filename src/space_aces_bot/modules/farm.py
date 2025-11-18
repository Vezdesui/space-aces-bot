from __future__ import annotations

import logging

from space_aces_bot.core.actions import BotAction
from space_aces_bot.core.game_state import GameState
from space_aces_bot.core.interfaces import Farm

logger = logging.getLogger(__name__)


class DummyFarm(Farm):
    """Placeholder farming module that defers to navigation patrol.

    At this stage the farm logic does not drive movement directly. It
    periodically logs that no farming targets were found so that the
    navigation patrol can control movement.
    """

    def __init__(self, log_interval: int = 10) -> None:
        self._tick_counter = 0
        self._log_interval = max(1, int(log_interval))

    def decide(self, state: GameState) -> BotAction | None:  # noqa: ARG002 - state reserved for future use
        self._tick_counter += 1

        if self._tick_counter % self._log_interval == 0:
            logger.info(
                "Farm.decide: no farming targets; deferring to navigation patrol "
                "(tick=%s).",
                self._tick_counter,
            )

        # No farming action yet; navigation patrol defines movement.
        return None
