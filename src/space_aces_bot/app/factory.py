from __future__ import annotations

import logging
from typing import Any, Dict, Mapping

from space_aces_bot.drivers.selenium_driver import DummyDriver, SeleniumDriver
from space_aces_bot.modules.combat import BasicCombat, DummyCombat
from space_aces_bot.modules.farm import BasicFarm, DummyFarm
from space_aces_bot.modules.navigation import SimpleNavigation
from space_aces_bot.modules.safety import BasicSafety
from space_aces_bot.modules.vision import DummyVision, TemplateVision

logger = logging.getLogger(__name__)


def create_default_modules(config: Mapping[str, Any] | None) -> Dict[str, Any]:
    """Create default module instances used by the bot.

    The returned dict contains instances for navigation, vision,
    combat, farming, safety and the low-level driver.
    """

    cfg: Mapping[str, Any] = config or {}
    selenium_cfg = cfg.get("selenium", {}) or {}
    farm_cfg = cfg.get("farm", {}) or {}
    vision_cfg = cfg.get("vision", {}) or {}
    combat_cfg = cfg.get("combat", {}) or {}

    navigation = SimpleNavigation()
    if (vision_cfg or {}).get("enabled", True):
        vision = TemplateVision(vision_cfg, logger=logger)
        vision_name = "TemplateVision"
    else:
        vision = DummyVision()
        vision_name = "DummyVision"
    combat = BasicCombat(combat_cfg)
    farm = BasicFarm(farm_cfg, combat_cfg)
    safety = BasicSafety()

    if selenium_cfg.get("enabled", True):
        driver = SeleniumDriver(cfg)
        driver_name = "SeleniumDriver"
    else:
        driver = DummyDriver()
        driver_name = "DummyDriver"

    modules: Dict[str, Any] = {
        "navigation": navigation,
        "vision": vision,
        "combat": combat,
        "farm": farm,
        "safety": safety,
        "driver": driver,
    }

    logger.info(
        "Created default modules: %s (driver=%s, vision=%s)",
        ", ".join(sorted(modules.keys())),
        driver_name,
        vision_name,
    )
    return modules
