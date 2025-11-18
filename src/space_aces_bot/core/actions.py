from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, Optional

from .game_state import Position


class ActionType(Enum):
    """High-level action types produced by decision modules."""

    IDLE = "idle"
    MOVE = "move"
    ATTACK = "attack"
    COLLECT = "collect"
    JUMP = "jump"
    REPAIR = "repair"
    ESCAPE = "escape"


@dataclass
class BotAction:
    """High-level bot action returned by strategy modules.

    Higher-level modules (Farm, Combat, Safety, Navigation, etc.)
    should return either an instance of this class or ``None``.
    A separate driver layer will later translate ``BotAction`` into
    low-level interactions (clicks / WebSocket commands).
    """

    type: ActionType
    target_id: Optional[str] = None
    position: Optional[Position] = None
    meta: Dict[str, Any] = field(default_factory=dict)

