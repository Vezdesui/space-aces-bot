from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any

from .actions import BotAction
from .game_state import GameState, Position


class Navigation(ABC):
    """High-level navigation logic that plans and initiates movement."""

    @abstractmethod
    def set_destination(self, position: Position) -> None:
        """Set desired destination for the ship."""

    @abstractmethod
    def tick(self, state: GameState) -> BotAction | None:
        """Produce a movement action for the current tick, or ``None``."""


class Vision(ABC):
    """Abstraction over how the bot perceives the game world."""

    @abstractmethod
    def update_state(self, state: GameState) -> None:
        """Update the provided ``GameState`` based on current observations."""

    @abstractmethod
    def screenshot(self) -> Any:
        """Return a raw frame or snapshot for debug/diagnostics purposes."""


class Combat(ABC):
    """Combat decision logic (when and whom to attack)."""

    @abstractmethod
    def decide(self, state: GameState) -> BotAction | None:
        """Control tactical behaviour for the current target (approach, attack, disengage)."""


class Farm(ABC):
    """Farming / resource-gathering decision logic."""

    @abstractmethod
    def decide(self, state: GameState) -> BotAction | None:
        """Choose which target to farm and which high-level farming action to perform (e.g. select or switch NPC target)."""


class Safety(ABC):
    """Safety and escape decision logic."""

    @abstractmethod
    def assess(self, state: GameState) -> int:
        """Return a numeric danger score (higher means more dangerous)."""

    @abstractmethod
    def decide(self, state: GameState) -> BotAction | None:
        """Return an escape/repair action if needed, otherwise ``None``."""


class Driver(ABC):
    """Low-level executor that performs actions in the game client."""

    @abstractmethod
    def execute(self, action: BotAction, state: GameState) -> None:
        """Execute the given high-level action in the context of ``state``."""
