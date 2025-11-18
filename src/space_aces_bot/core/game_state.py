from __future__ import annotations

from dataclasses import dataclass


@dataclass
class GameState:
    """Simple game state representation for the bot skeleton."""

    tick_counter: int = 0

    def __repr__(self) -> str:
        return f"GameState(tick_counter={self.tick_counter})"
