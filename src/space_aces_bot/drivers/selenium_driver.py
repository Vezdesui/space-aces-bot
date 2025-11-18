from __future__ import annotations

import logging
from typing import Any, Mapping, Optional

from selenium import webdriver
from selenium.webdriver.chrome.options import Options as ChromeOptions
from selenium.webdriver.chrome.service import Service as ChromeService

from space_aces_bot.core.actions import ActionType, BotAction
from space_aces_bot.core.game_state import GameState
from space_aces_bot.core.interfaces import Driver

logger = logging.getLogger(__name__)


class DummyDriver(Driver):
    """Driver stub that only logs actions instead of executing them."""

    def execute(self, action: BotAction, state: GameState) -> None:
        logger.info(
            "DummyDriver.execute: action=%s target_id=%s position=%s meta=%s tick=%s",
            action.type,
            action.target_id,
            action.position,
            action.meta,
            state.tick_counter,
        )


class SeleniumDriver(Driver):
    """Driver implementation that uses Selenium WebDriver.

    This class is responsible for translating high-level ``BotAction``
    instances into low-level browser interactions with the game client.
    """

    def __init__(
        self,
        config: Mapping[str, Any],
        logger: Optional[logging.Logger] = None,
    ) -> None:
        self._config: Mapping[str, Any] = config
        self._selenium_cfg: Mapping[str, Any] = config.get("selenium", {}) or {}
        self._logger = logger or logging.getLogger(f"{__name__}.SeleniumDriver")
        self._driver: Optional[webdriver.Chrome] = None

        if not self._selenium_cfg.get("enabled", True):
            self._logger.info("Selenium is disabled in configuration.")

    # ------------------------------------------------------------------
    # Lifecycle helpers
    # ------------------------------------------------------------------
    def _create_driver(self) -> webdriver.Chrome:
        """Create and configure a Selenium WebDriver instance."""
        browser = str(self._selenium_cfg.get("browser", "chrome")).lower()

        if browser != "chrome":
            self._logger.warning(
                "Browser %s is not explicitly supported yet; falling back to Chrome.",
                browser,
            )

        options = ChromeOptions()

        # Start maximized (primarily for desktop environments).
        options.add_argument("--start-maximized")

        # Optional headless mode.
        if self._selenium_cfg.get("headless", False):
            # ``--headless=new`` is recommended for modern Chrome versions.
            options.add_argument("--headless=new")

        # Basic anti-detection tweaks.
        if self._selenium_cfg.get("anti_detect", True):
            options.add_argument("--disable-blink-features=AutomationControlled")
            options.add_argument("--disable-infobars")
            options.add_experimental_option(
                "excludeSwitches",
                ["enable-automation"],
            )
            options.add_experimental_option("useAutomationExtension", False)

        # Optional preferences to reduce noise from notifications/popups.
        prefs = {
            "profile.default_content_setting_values.notifications": 2,
        }
        options.add_experimental_option("prefs", prefs)

        driver_path = str(self._selenium_cfg.get("driver_path", "")).strip()

        try:
            if driver_path and driver_path.upper() != "CHANGE_ME":
                self._logger.info(
                    "Creating Chrome WebDriver with explicit driver path: %s",
                    driver_path,
                )
                service = ChromeService(driver_path)
                driver = webdriver.Chrome(service=service, options=options)
            else:
                self._logger.info(
                    "Creating Chrome WebDriver using system PATH (no driver_path set)."
                )
                driver = webdriver.Chrome(options=options)
        except Exception:
            self._logger.exception("Failed to create Selenium WebDriver.")
            raise

        return driver

    def start(self) -> None:
        """Start the Selenium driver and open the game URL."""
        if self._driver is None:
            self._driver = self._create_driver()

        url = str(self._selenium_cfg.get("game_url", "")).strip()
        if not url:
            self._logger.warning(
                "No selenium.game_url provided in configuration; skipping navigation."
            )
            return

        self._logger.info("Opening game URL in Selenium: %s", url)
        try:
            assert self._driver is not None
            self._driver.get(url)
        except Exception:
            self._logger.exception("Error while opening game URL: %s", url)
        else:
            self._logger.info("Game page opened: %s", url)

    def stop(self) -> None:
        """Gracefully stop the Selenium driver and close the browser."""
        if self._driver is None:
            return

        self._logger.info("Stopping Selenium WebDriver.")
        try:
            self._driver.quit()
        except Exception:
            # Ignore errors when shutting down the driver.
            self._logger.exception("Error while quitting Selenium WebDriver.")
        finally:
            self._driver = None

    # ------------------------------------------------------------------
    # Driver interface implementation
    # ------------------------------------------------------------------
    def execute(self, action: BotAction, state: GameState) -> None:
        """Execute a high-level action using Selenium.

        For now, this method only logs what would be done. Actual DOM
        interaction (locating elements, sending keys, etc.) will be
        added in a later implementation phase.
        """

        if self._driver is None:
            self._logger.warning(
                "SeleniumDriver.execute called but driver is not started; "
                "action %s will be ignored.",
                action,
            )
            return

        self._logger.info(
            "SeleniumDriver.execute: received action=%s target_id=%s position=%s meta=%s tick=%s",
            action.type,
            action.target_id,
            action.position,
            action.meta,
            state.tick_counter,
        )

        if action.type is ActionType.IDLE:
            self._logger.info("SeleniumDriver: IDLE action, nothing to perform.")
            return

        if action.type is ActionType.MOVE:
            pos = action.position
            self._logger.info(
                "SeleniumDriver: MOVE action towards map position (%s, %s). "
                "This would trigger a click in the game client.",
                getattr(pos, "x", None),
                getattr(pos, "y", None),
            )
            # TODO: Convert logical map coordinates to browser window
            # coordinates and perform a real click, e.g. via:
            #   from selenium.webdriver import ActionChains
            #   ActionChains(self._driver).move_by_offset(x, y).click().perform()
            return

        # Other actions are acknowledged but not yet implemented.
        if action.type in {
            ActionType.ATTACK,
            ActionType.COLLECT,
            ActionType.JUMP,
            ActionType.REPAIR,
            ActionType.ESCAPE,
        }:
            self._logger.info(
                "SeleniumDriver: received %s action for target_id=%s, "
                "but this action type is not implemented yet.",
                action.type.name,
                action.target_id,
            )
            return
