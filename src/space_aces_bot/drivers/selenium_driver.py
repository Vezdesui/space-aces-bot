from __future__ import annotations

import logging
from typing import Any, Mapping, Optional

from selenium import webdriver
from selenium.common.exceptions import NoSuchElementException, TimeoutException
from selenium.webdriver.chrome.options import Options as ChromeOptions
from selenium.webdriver.chrome.service import Service as ChromeService
from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import WebDriverWait

from space_aces_bot.core.actions import ActionType, BotAction
from space_aces_bot.core.game_state import GameState
from space_aces_bot.core.interfaces import Driver

logger = logging.getLogger(__name__)


# Centralized selectors and timeouts used by SeleniumDriver.
LOGIN_SELECTORS = {
    # Prefer explicit login fields by name; ``find_element`` will return
    # the first match in DOM order, which corresponds to the primary
    # login form on the Space Aces home page.
    "username": "input[name='email'],input[name='username']",
    "password": "input[name='password']",
    # Fallback CSS for submit controls; actual login button is resolved
    # primarily via ``button_xpath`` below.
    "submit": "button[type=submit],input[type=submit],button",
    # XPath expression targeting the primary "Sign-in" button.
    "button_xpath": "//button[normalize-space()=\"Sign-in\"]",
}

DEFAULT_LOGIN_TIMEOUT = 20.0
DEFAULT_LOGIN_RESULT_TIMEOUT = 20.0


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

            self._logger.info("Chrome WebDriver instance created successfully.")
        except Exception:
            self._logger.exception("Failed to create Selenium WebDriver.")
            raise

        return driver

    def start(self) -> None:
        """Start the Selenium driver and open the game URL."""
        if self._driver is None:
            self._logger.info("Creating Selenium WebDriver instance.")
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

    def _is_logged_in(self) -> bool:
        """Heuristically determine whether the user is logged in.

        By default, this checks for the absence of a visible password field
        that matches ``LOGIN_SELECTORS['password']``. Optionally, a custom
        CSS selector ``selenium.logged_in_selector`` may be provided in the
        configuration to positively identify the logged-in state.
        """

        if self._driver is None:
            return False

        try:
            marker_selector = str(self._selenium_cfg.get("logged_in_selector", "")).strip()

            if marker_selector:
                elements = self._driver.find_elements(By.CSS_SELECTOR, marker_selector)
                logged_in = bool(elements)
                self._logger.info(
                    "Login state check using marker selector '%s': logged_in=%s",
                    marker_selector,
                    logged_in,
                )
                return logged_in

            # Default heuristic: consider the user logged in once the visible
            # "Sign-in" button disappears from the page.
            sign_in_buttons = self._driver.find_elements(
                By.XPATH,
                LOGIN_SELECTORS["button_xpath"],
            )
            visible_buttons = [btn for btn in sign_in_buttons if btn.is_displayed()]
            logged_in = not visible_buttons
            self._logger.info(
                "Login state heuristic: visible_sign_in_buttons=%d, logged_in=%s",
                len(visible_buttons),
                logged_in,
            )
            return logged_in
        except Exception:
            self._logger.exception("Error while checking logged-in state.")
            return False

    def login(self, username: str, password: str) -> bool:
        """Attempt to log in using the provided credentials.

        The page is expected to be opened by :meth:`start` beforehand.
        The method fills the login form and waits for a logged-in state
        using :meth:`_is_logged_in`.
        """

        if self._driver is None:
            self._logger.warning(
                "SeleniumDriver.login called but driver is not started; "
                "skipping login attempt.",
            )
            return False

        login_timeout = float(self._selenium_cfg.get("login_timeout", DEFAULT_LOGIN_TIMEOUT))
        result_timeout = float(
            self._selenium_cfg.get("login_result_timeout", DEFAULT_LOGIN_RESULT_TIMEOUT)
        )

        self._logger.info(
            "Starting login attempt for Space Aces user (timeouts: form=%.1fs, result=%.1fs).",
            login_timeout,
            result_timeout,
        )

        try:
            wait = WebDriverWait(self._driver, login_timeout)

            # Locate the username and password inputs.
            self._logger.info(
                "Waiting for username input using selector '%s'.",
                LOGIN_SELECTORS["username"],
            )
            username_field = wait.until(
                EC.presence_of_element_located(
                    (By.CSS_SELECTOR, LOGIN_SELECTORS["username"]),
                )
            )
            self._logger.info("Username input element located for login.")

            self._logger.info(
                "Waiting for password input using selector '%s'.",
                LOGIN_SELECTORS["password"],
            )
            password_field = wait.until(
                EC.presence_of_element_located(
                    (By.CSS_SELECTOR, LOGIN_SELECTORS["password"]),
                )
            )
            self._logger.info("Password input element located for login.")

            # Locate a submit control for the login form.
            submit_element: Optional[Any] = None
            try:
                submit_element = self._driver.find_element(
                    By.XPATH,
                    LOGIN_SELECTORS["button_xpath"],
                )
                self._logger.info(
                    "Login submit button located via XPath '%s'.",
                    LOGIN_SELECTORS["button_xpath"],
                )
            except NoSuchElementException:
                self._logger.warning(
                    "Login submit button XPath '%s' not found; "
                    "falling back to CSS selectors '%s'.",
                    LOGIN_SELECTORS["button_xpath"],
                    LOGIN_SELECTORS["submit"],
                )
                for candidate in self._driver.find_elements(
                    By.CSS_SELECTOR,
                    LOGIN_SELECTORS["submit"],
                ):
                    if candidate.is_displayed():
                        submit_element = candidate
                        break

            if submit_element is None:
                self._logger.error("Could not locate login submit button on page.")
                return False

            # Fill in credentials and submit.
            self._logger.info("Filling Space Aces login form (username only, password hidden).")
            username_field.clear()
            username_field.send_keys(username)

            password_field.clear()
            password_field.send_keys(password)

            self._logger.info("Submitting Space Aces login form.")
            submit_element.click()

            # Wait for a change in page state that indicates login success.
            self._logger.info("Waiting for login result (logged-in state).")
            try:
                WebDriverWait(self._driver, result_timeout).until(lambda _d: self._is_logged_in())
            except TimeoutException:
                self._logger.warning(
                    "Timed out waiting for login result after %.1f seconds.",
                    result_timeout,
                )
                return self._is_logged_in()

            is_logged_in = self._is_logged_in()
            if is_logged_in:
                self._logger.info("Login appears to be successful based on page state.")
            else:
                self._logger.warning("Login appears to have failed based on page state.")

            return is_logged_in
        except TimeoutException:
            self._logger.exception(
                "Timed out while waiting for login form after %.1f seconds.",
                login_timeout,
            )
            return False
        except Exception:
            self._logger.exception("Unexpected error while attempting to log in.")
            return False

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
