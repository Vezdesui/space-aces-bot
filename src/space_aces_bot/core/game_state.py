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
    npc_type: str
    hp: int
    max_hp: int


@dataclass
class Resource:
    """Resource box or collectible on the map."""

    id: str
    position: Position
    resource_type: str
    value: int


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
    npcs: Dict[str, Npc] = field(default_factory=dict)
    resources: Dict[str, Resource] = field(default_factory=dict)
    enemies: Dict[str, EnemyPlayer] = field(default_factory=dict)
    portals: Dict[str, MapPortal] = field(default_factory=dict)

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
