from __future__ import annotations

import logging
from typing import Any, Dict, Mapping

from space_aces_bot.drivers.selenium_driver import DummyDriver
from space_aces_bot.modules.combat import DummyCombat
from space_aces_bot.modules.farm import DummyFarm
from space_aces_bot.modules.navigation import SimpleNavigation
from space_aces_bot.modules.safety import DummySafety
from space_aces_bot.modules.vision import DummyVision

logger = logging.getLogger(__name__)


def create_default_modules(config: Mapping[str, Any] | None) -> Dict[str, Any]:
    """Create default module instances used by the bot.

    The returned dict contains instances for navigation, vision,
    combat, farming, safety and the low-level driver.
    """

    navigation = SimpleNavigation()
    vision = DummyVision()
    combat = DummyCombat()
    farm = DummyFarm()
    safety = DummySafety()
    driver = DummyDriver()

    modules: Dict[str, Any] = {
        "navigation": navigation,
        "vision": vision,
        "combat": combat,
        "farm": farm,
        "safety": safety,
        "driver": driver,
    }

    logger.info("Created default modules: %s", ", ".join(modules.keys()))
    return modules

