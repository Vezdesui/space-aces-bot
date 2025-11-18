from __future__ import annotations

from space_aces_bot.core.actions import ActionType, BotAction
from space_aces_bot.core.game_state import GameState, Position, Ship
from space_aces_bot.modules.combat import BasicCombat
from space_aces_bot.modules.farm import BasicFarm
from space_aces_bot.modules.vision import TemplateVision


def test_can_import_space_aces_bot() -> None:
    import space_aces_bot  # noqa: F401

    assert "space_aces_bot" in globals() or space_aces_bot is not None


def test_core_types_are_constructible() -> None:
    ship = Ship(
        id="test-ship",
        position=Position(x=0.0, y=0.0),
        hp=1,
        max_hp=1,
        shield=0,
        max_shield=0,
    )

    state = GameState(ship=ship, current_map="1-1")

    action = BotAction(type=ActionType.MOVE, position=Position(x=1.0, y=2.0))

    assert state.ship.id == "test-ship"
    assert action.type is ActionType.MOVE


def test_action_type_contains_expected_members() -> None:
    assert ActionType.MOVE.name == "MOVE"
    assert ActionType.ATTACK.name == "ATTACK"
    assert ActionType.COLLECT.name == "COLLECT"


def test_can_import_basic_farm_and_combat() -> None:
    # Construction should not raise and should accept minimal configs.
    farm = BasicFarm(farm_cfg={}, combat_cfg={})
    combat = BasicCombat(combat_cfg={})
    vision = TemplateVision(vision_cfg={})

    assert farm is not None
    assert combat is not None
    assert vision is not None
