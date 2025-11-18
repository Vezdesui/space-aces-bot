from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, Optional


@dataclass
class Position:
    """Simple 2D position on the game map."""

    x: float
    y: float


@dataclass
class Ship:
    """Player ship representation."""

    id: str
    position: Position
    hp: int
    max_hp: int
    shield: int
    max_shield: int
    speed: Optional[float] = None


@dataclass
class Npc:
    """Non-player character (ally or neutral)."""

    id: str
    position: Position
    hp: int
    max_hp: int
    npc_type: str = "unknown"


@dataclass
class Resource:
    """Resource box or collectible on the map."""

    id: str
    position: Position
    resource_type: str
    value: int
    kind: str = "unknown"


@dataclass
class EnemyPlayer:
    """Enemy player detected on the map."""

    id: str
    position: Position
    threat_level: float


@dataclass
class MapPortal:
    """Portal that leads to another map."""

    id: str
    position: Position
    target_map: str


@dataclass
class GameState:
    """Representation of the current game state for the bot."""

    ship: Ship
    current_map: str = "1-1"
    tick_counter: int = 0
    current_target_id: Optional[str] = None
    in_combat: bool = False
    ticks_with_current_target: int = 0
    npcs: Dict[str, Npc] = field(default_factory=dict)
    resources: Dict[str, Resource] = field(default_factory=dict)
    enemies: Dict[str, EnemyPlayer] = field(default_factory=dict)
    portals: Dict[str, MapPortal] = field(default_factory=dict)
    _last_target_id: Optional[str] = field(default=None, repr=False, compare=False)

    def get_current_target(self) -> Optional[Npc]:
        if self.current_target_id is None:
            return None
        return self.npcs.get(self.current_target_id)

    def advance_tick(self) -> None:
        """Advance global tick counter and update target-related counters."""

        self.tick_counter += 1

        current_id = self.current_target_id

        # No active target: reset counters and tracking.
        if current_id is None:
            self.ticks_with_current_target = 0
            self._last_target_id = None
            return

        # If target disappeared from NPC list, reset and clear.
        if current_id not in self.npcs:
            self.ticks_with_current_target = 0
            self._last_target_id = None
            return

        # If target changed, reset per-target tick counter.
        if self._last_target_id != current_id:
            self.ticks_with_current_target = 0

        self.ticks_with_current_target += 1
        self._last_target_id = current_id

    def clear_vision_objects(self) -> None:
        """Clear dynamic objects populated by the vision system."""

        self.resources.clear()

    def __repr__(self) -> str:
        return (
            "GameState("
            f"map={self.current_map!r}, "
            f"tick={self.tick_counter}, "
            f"ship_id={self.ship.id!r}, "
            f"npcs={len(self.npcs)}, "
            f"resources={len(self.resources)}, "
            f"enemies={len(self.enemies)}, "
            f"portals={len(self.portals)}"
            ")"
        )
