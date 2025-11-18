from __future__ import annotations

import logging
import time
from typing import Any, Mapping, Optional

from selenium import webdriver
from selenium.common.exceptions import (
    ElementClickInterceptedException,
    NoSuchElementException,
    StaleElementReferenceException,
    TimeoutException,
)
from selenium.webdriver.chrome.options import Options as ChromeOptions
from selenium.webdriver.chrome.service import Service as ChromeService
from selenium.webdriver.common.action_chains import ActionChains
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

# Default selector for the main game map element. By default, the first
# <canvas> element on the page is treated as the map. This can be overridden
# via the selenium.map_selector configuration option if needed.
MAP_ELEMENT_SELECTOR = "canvas"

# Dashboard and in-game selectors.
# Case-insensitive match for PLAY button text on the dashboard.
PLAY_BUTTON_XPATH = (
    "//button["
    "contains(translate(normalize-space(), 'abcdefghijklmnopqrstuvwxyz', 'ABCDEFGHIJKLMNOPQRSTUVWXYZ'), 'PLAY')"
    "]"
)
GAME_WINDOW_TITLE_CONTAINS = "Space Aces"
GAME_WINDOW_TITLE_GAME_CONTAINS = "Game"
# Selector for the Start button in the game window.
# Currently the game exposes a dedicated button with id="modpack"
# that controls entering the play view; we treat this as the Start
# button. If the DOM changes, adjust this selector or move it into
# configuration.
GAME_START_BUTTON_XPATH = "//button[@id='modpack']"

# Competition popup selectors.
COMPETITION_POPUP_XPATH = (
    "//*[contains(translate(normalize-space(), 'abcdefghijklmnopqrstuvwxyz', 'ABCDEFGHIJKLMNOPQRSTUVWXYZ'), "
    "'COMPETITION RULES') "
    "or contains(translate(normalize-space(), 'abcdefghijklmnopqrstuvwxyz', 'ABCDEFGHIJKLMNOPQRSTUVWXYZ'), "
    "'PILOT! WE HAVE AN IMPORTANT ANNOUNCEMENT TO MAKE!')]"
)
COMPETITION_CLOSE_BUTTON_REL_XPATH = (
    ".//button["
    "contains(translate(normalize-space(), 'abcdefghijklmnopqrstuvwxyz', 'ABCDEFGHIJKLMNOPQRSTUVWXYZ'), 'CLOSE')"
    "]"
)

# Daily Login Bonus container selector in the game view.
DAILY_LOGIN_CONTAINER_XPATH = (
    "//*[contains(translate(normalize-space(), 'abcdefghijklmnopqrstuvwxyz', 'ABCDEFGHIJKLMNOPQRSTUVWXYZ'), "
    "'DAILY LOGIN BONUS')]"
)

# Maximum time to wait for the Daily Login Bonus / START flow.
START_MAX_WAIT_SECONDS = 40.0


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
        self.in_game: bool = False

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

        # Start maximized (primarily for desktop environments). We
        # deliberately avoid incognito/private mode so that session
        # cookies persist and to reduce the risk of triggering
        # anti-bot heuristics tied to ephemeral profiles.
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
        # Reset in-game flag whenever we (re)start the driver.
        self.in_game = False

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

    # ------------------------------------------------------------------
    # Competition popup helpers
    # ------------------------------------------------------------------
    def _close_competition_popup_if_present(self) -> None:
        """Close the competition popup on the dashboard if it is present.

        The method looks for a popup containing text such as
        ``COMPETITION RULES`` or ``Pilot! We have an important announcement
        to make!`` and attempts to click its Close button. All errors are
        logged but do not propagate further.
        """

        if self._driver is None:
            return

        driver = self._driver

        timeout = float(self._selenium_cfg.get("competition_popup_timeout", 25.0))
        popup_xpath = str(self._selenium_cfg.get("competition_popup_xpath", COMPETITION_POPUP_XPATH))
        close_rel_xpath = str(
            self._selenium_cfg.get("competition_close_button_xpath", COMPETITION_CLOSE_BUTTON_REL_XPATH)
        )

        try:
            self._logger.debug(
                "Checking for competition popup using XPath '%s' (timeout=%.1fs).",
                popup_xpath,
                timeout,
            )

            wait = WebDriverWait(driver, timeout)
            try:
                popup = wait.until(EC.visibility_of_element_located((By.XPATH, popup_xpath)))
            except TimeoutException:
                self._logger.debug(
                    "No competition popup detected within %.1f seconds.",
                    timeout,
                )
                return

            try:
                close_button = popup.find_element(By.XPATH, close_rel_xpath)
            except NoSuchElementException:
                self._logger.warning(
                    "Competition popup detected but Close button was not found using relative XPath '%s'. "
                    "Will search for Close button globally.",
                    close_rel_xpath,
                )
                try:
                    close_button = driver.find_element(By.XPATH, close_rel_xpath)
                except NoSuchElementException:
                    self._logger.warning(
                        "Competition popup Close button not found; popup will be left open."
                    )
                    return

            self._logger.info("Competition popup detected, clicking Close button.")
            try:
                close_button.click()
            except Exception:
                self._logger.warning(
                    "Failed to click Close button for competition popup.",
                    exc_info=True,
                )
                return

            try:
                WebDriverWait(driver, timeout).until(
                    EC.invisibility_of_element_located((By.XPATH, popup_xpath))
                )
                self._logger.info("Competition popup closed.")
            except TimeoutException:
                self._logger.warning(
                    "Competition popup Close clicked but popup did not disappear within %.1f seconds.",
                    timeout,
                )
        except Exception:
            self._logger.warning(
                "Unexpected error while handling competition popup; proceeding without closing it.",
                exc_info=True,
            )

    # ------------------------------------------------------------------
    # Game entry helpers
    # ------------------------------------------------------------------
    def _wait_and_click_start_button(self) -> bool:
        """Wait for the Daily Login Bonus / START button and click it.

        The method assumes we are already in the ``Space aces | Game`` window.
        It periodically checks the Daily Login Bonus container and the START
        button, attempting a click whenever the button appears interactable,
        and stops once the container disappears or the timeout expires.
        """

        if self._driver is None:
            self._logger.warning(
                "SeleniumDriver._wait_and_click_start_button called but driver is not started; "
                "skipping start button workflow.",
            )
            return False

        driver = self._driver

        start_xpath = str(self._selenium_cfg.get("start_button_xpath", GAME_START_BUTTON_XPATH)).strip()
        daily_login_xpath = str(
            self._selenium_cfg.get("daily_login_container_xpath", DAILY_LOGIN_CONTAINER_XPATH)
        ).strip()

        if not daily_login_xpath:
            self._logger.warning(
                "Game: daily login container XPath is empty; START workflow may be unreliable."
            )

        self._logger.info("Game: waiting for Daily Login Bonus / START button.")

        end_time = time.time() + START_MAX_WAIT_SECONDS
        while time.time() < end_time:
            # 1) Check if the Daily Login Bonus container is still visible.
            try:
                if daily_login_xpath:
                    container = driver.find_element(By.XPATH, daily_login_xpath)
                    if not container.is_displayed():
                        self._logger.info("Game: Daily Login Bonus container hidden - in game.")
                        return True
                else:
                    # If we do not have a container selector, fall back to checking the map.
                    map_element = self._find_map_element()
                    if map_element is not None:
                        self._logger.info(
                            "Game: no daily login container XPath configured, but map is present; "
                            "assuming in-game view."
                        )
                        return True
            except NoSuchElementException:
                self._logger.info(
                    "Game: Daily Login Bonus container not found - in game."
                )
                return True
            except StaleElementReferenceException:
                self._logger.info(
                    "Game: Daily Login Bonus container reference became stale, will re-check.",
                )
            except Exception:
                self._logger.warning(
                    "Game: unexpected error while checking Daily Login Bonus container, will retry.",
                    exc_info=False,
                )

            # 2) Try to locate and click the START/Loading button.
            try:
                btn = driver.find_element(By.XPATH, start_xpath)
                self._logger.debug("Game: DOM START button present, trying JS click.")
                driver.execute_script("arguments[0].click();", btn)
            except (NoSuchElementException, StaleElementReferenceException) as e:
                self._logger.debug(
                    "Game: DOM START button not ready yet (%s), will try fallback.",
                    e.__class__.__name__,
                )
            except Exception:
                self._logger.warning(
                    "Game: unexpected error while interacting with DOM START button, will retry.",
                    exc_info=False,
                )

            # 3) Additional fallback: click a rough START area by viewport coordinates.
            self._fallback_click_start_area()

            time.sleep(0.8)

        self._logger.warning(
            "Game: failed to dismiss Daily Login Bonus / START within %.1f seconds.",
            START_MAX_WAIT_SECONDS,
        )
        return False

    def _fallback_click_start_area(self) -> None:
        """Грубый клик в зону, где визуально находится зелёная кнопка START.

        This helper approximates the START area using viewport dimensions,
        clicking near the bottom-centre of the window. It is intentionally
        best-effort and must never raise exceptions to callers.
        """

        if self._driver is None:
            self._logger.warning(
                "SeleniumDriver._fallback_click_start_area called but driver is not started; "
                "skipping fallback click.",
            )
            return

        driver = self._driver

        try:
            width = float(
                driver.execute_script(
                    "return window.innerWidth || document.documentElement.clientWidth || document.body.clientWidth;"
                )
                or 0.0
            )
            height = float(
                driver.execute_script(
                    "return window.innerHeight || document.documentElement.clientHeight || document.body.clientHeight;"
                )
                or 0.0
            )

            if width <= 0.0 or height <= 0.0:
                self._logger.warning(
                    "Game: fallback START click aborted due to invalid viewport size "
                    "(width=%.1f, height=%.1f).",
                    width,
                    height,
                )
                return

            # Target a point near the bottom-centre of the viewport.
            click_x = width * 0.5
            click_y = height * 0.9

            # Offsets are relative to the element centre when using
            # move_to_element_with_offset.
            offset_x = click_x - (width / 2.0)
            offset_y = click_y - (height / 2.0)

            body = driver.find_element(By.TAG_NAME, "body")

            self._logger.info(
                "Game: fallback click into START area at viewport (%.1f, %.1f) offsets=(%.1f, %.1f).",
                click_x,
                click_y,
                offset_x,
                offset_y,
            )

            actions = ActionChains(driver)
            actions.move_to_element_with_offset(body, offset_x, offset_y).click().perform()
        except Exception:
            self._logger.warning(
                "Game: fallback click into START area failed; ignoring and continuing.",
                exc_info=False,
            )

    def enter_game(self) -> bool:
        """Enter the in-game view from the Space Aces dashboard.

        This method assumes that the user is already logged in and the
        current page is the Space Aces dashboard. It will attempt to:

        1. Click the PLAY button on the dashboard.
        2. Switch to the game window/tab (title contains ``Space Aces`` and ``Game``).
        3. Wait for the ``Start`` button to become available and click it.

        On success, :attr:`in_game` is set to ``True`` and the method
        returns ``True``. On failure, it logs the problem and returns
        ``False`` without raising exceptions.
        """

        # Ensure we start from a consistent state; only set to True on success.
        self.in_game = False

        if self._driver is None:
            self._logger.warning(
                "SeleniumDriver.enter_game called but driver is not started; "
                "skipping game entry.",
            )
            return False

        driver = self._driver

        enter_timeout = float(self._selenium_cfg.get("enter_game_timeout", 30.0))
        self._logger.info(
            "Starting enter_game sequence (timeout=%.1fs).",
            enter_timeout,
        )

        try:
            wait = WebDriverWait(driver, enter_timeout)

            # Close competition popup if it is present on the dashboard.
            self._close_competition_popup_if_present()

            # 1) Click PLAY on the dashboard.
            play_xpath = str(self._selenium_cfg.get("play_button_xpath", PLAY_BUTTON_XPATH))
            self._logger.info(
                "Waiting for PLAY button using XPath '%s'.",
                play_xpath,
            )

            original_handles = list(driver.window_handles)

            try:
                play_button = wait.until(
                    EC.element_to_be_clickable((By.XPATH, play_xpath)),
                )
            except TimeoutException:
                self._logger.error(
                    "PLAY button was not found or not clickable within %.1f seconds "
                    "using XPath '%s'.",
                    enter_timeout,
                    play_xpath,
                )
                return False

            self._logger.info("Dashboard: PLAY clicked.")
            try:
                play_button.click()
            except ElementClickInterceptedException:
                self._logger.warning(
                    "PLAY button click was intercepted, likely by an overlay; "
                    "waiting for overlays to disappear before retrying."
                )
                try:
                    WebDriverWait(driver, enter_timeout).until(
                        EC.invisibility_of_element_located((By.CSS_SELECTOR, ".v-overlay__scrim"))
                    )
                    self._logger.info("Retrying click on PLAY button after overlay disappearance.")
                    play_button.click()
                except Exception:
                    self._logger.exception(
                        "Failed to click PLAY button even after waiting for overlays."
                    )
                    return False

            # 2) Wait for a new window/tab and switch to the game window.
            self._logger.info("Waiting for game window/tab to appear.")

            try:
                WebDriverWait(driver, enter_timeout).until(
                    lambda d: len(d.window_handles) > len(original_handles)
                )
            except TimeoutException:
                self._logger.warning(
                    "No new window handle appeared after clicking PLAY within %.1f seconds; "
                    "will search for game window among existing handles.",
                    enter_timeout,
                )

            game_handle = None
            handles = driver.window_handles

            title_contains = str(
                self._selenium_cfg.get("game_window_title_contains", GAME_WINDOW_TITLE_CONTAINS)
            )
            title_game_contains = str(
                self._selenium_cfg.get(
                    "game_window_title_game_contains",
                    GAME_WINDOW_TITLE_GAME_CONTAINS,
                )
            )

            for handle in handles:
                driver.switch_to.window(handle)
                title = driver.title or ""
                title_lower = title.lower()
                if title_contains.lower() in title_lower and title_game_contains.lower() in title_lower:
                    game_handle = handle
                    self._logger.info(
                        "Found game window handle=%s with title=%r.",
                        handle,
                        title,
                    )
                    break

            if game_handle is None:
                self._logger.error(
                    "Could not locate game window with title containing %r and %r "
                    "(case-insensitive). Available titles: %s",
                    title_contains,
                    title_game_contains,
                    [driver.switch_to.window(h) or driver.title for h in handles],
                )
                return False

            driver.switch_to.window(game_handle)
            self._logger.info("Switched to Space aces  Game window (title=%r).", driver.title)

            # 3) Wait for the Start button and click it using the helper.
            start_ok = self._wait_and_click_start_button()
            if start_ok:
                self.in_game = True
                self._logger.info(
                    "Game: Daily Login Bonus dismissed, in_game=True."
                )
                return True

            self._logger.info("Game: failed to dismiss Daily Login Bonus / START.")
            return False
        except Exception:
            self._logger.exception("Unexpected error during enter_game sequence.")

            # Fallback: if the main map element is already present, assume that
            # the game view is ready even though the explicit Start flow did
            # not complete successfully. This can happen when the loader or
            # mod UI changes the expected DOM structure.
            try:
                map_element = self._find_map_element()
            except Exception:
                return False

            if map_element is not None:
                self.in_game = True
                self._logger.warning(
                    "enter_game encountered an error, but map element is present; "
                    "assuming game view is ready (in_game=True)."
                )
                return True

            return False
    # ------------------------------------------------------------------
    # Map helpers
    # ------------------------------------------------------------------
    def _find_map_element(self):
        """Locate the primary game map element in the DOM.

        The selector is configurable via ``selenium.map_selector`` and
        defaults to :data:`MAP_ELEMENT_SELECTOR` (currently the first
        ``<canvas>`` element on the page).
        """

        if self._driver is None:
            self._logger.warning(
                "SeleniumDriver._find_map_element called but driver is not started; "
                "skipping map lookup.",
            )
            return None

        selector = str(self._selenium_cfg.get("map_selector", MAP_ELEMENT_SELECTOR)).strip()
        if not selector:
            self._logger.error(
                "Map selector is empty; cannot locate map element. "
                "Check selenium.map_selector configuration.",
            )
            return None

        self._logger.info("Locating map element using selector '%s'.", selector)

        try:
            element = self._driver.find_element(By.CSS_SELECTOR, selector)
            self._logger.info("Map element located successfully.")
            return element
        except NoSuchElementException:
            self._logger.error(
                "Could not locate map element using selector '%s'.",
                selector,
            )
            return None
        except Exception:
            self._logger.exception("Unexpected error while locating map element.")
            return None

    def _click_on_map_relative(self, rel_x: float, rel_y: float) -> None:
        """Click on the game map using normalised coordinates.

        *rel_x* and *rel_y* must be within ``[0.0, 1.0]`` and represent
        the position on the map relative to its size, where (0.5, 0.5)
        is the centre.
        """

        if self._driver is None:
            self._logger.warning(
                "SeleniumDriver._click_on_map_relative called but driver is not started; "
                "skipping click.",
            )
            return

        try:
            if not (0.0 <= rel_x <= 1.0 and 0.0 <= rel_y <= 1.0):
                self._logger.warning(
                    "Normalised map coordinates out of range: rel_x=%.3f rel_y=%.3f; "
                    "expected values between 0.0 and 1.0. Click will be skipped.",
                    rel_x,
                    rel_y,
                )
                return

            map_element = self._find_map_element()
            if map_element is None:
                self._logger.error(
                    "Cannot click on map because the map element could not be located.",
                )
                return

            size = map_element.size or {}
            location = map_element.location or {}

            width = float(size.get("width") or 0.0)
            height = float(size.get("height") or 0.0)
            if width <= 0.0 or height <= 0.0:
                self._logger.warning(
                    "Map element has non-positive size: width=%s height=%s; click will be skipped.",
                    width,
                    height,
                )
                return

            left = float(location.get("x") or 0.0)
            top = float(location.get("y") or 0.0)

            abs_x = left + width * rel_x
            abs_y = top + height * rel_y

            # ActionChains offsets are relative to the element's centre when
            # using move_to_element_with_offset. Compute offsets accordingly.
            offset_x = width * rel_x - (width / 2.0)
            offset_y = height * rel_y - (height / 2.0)

            self._logger.info(
                "Clicking on map at rel=(%.3f, %.3f) abs=(%.1f, %.1f) offset=(%.1f, %.1f).",
                rel_x,
                rel_y,
                abs_x,
                abs_y,
                offset_x,
                offset_y,
            )

            actions = ActionChains(self._driver)
            actions.move_to_element_with_offset(map_element, offset_x, offset_y).click().perform()
        except Exception:
            self._logger.exception(
                "Unexpected error while clicking on map at rel=(%s, %s).",
                rel_x,
                rel_y,
            )

    def stop(self) -> None:
        """Gracefully stop the Selenium driver and close the browser."""
        if self._driver is None:
            # Ensure flag is reset even if the driver was already None.
            self.in_game = False
            return

        self._logger.info("Stopping Selenium WebDriver.")
        try:
            self._driver.quit()
        except Exception:
            # Ignore errors when shutting down the driver.
            self._logger.exception("Error while quitting Selenium WebDriver.")
        finally:
            self._driver = None
            self.in_game = False

    # ------------------------------------------------------------------
    # Driver interface implementation
    # ------------------------------------------------------------------
    def execute(self, action: BotAction, state: GameState) -> None:
        """Execute a high-level action using Selenium.

        For now, MOVE/ESCAPE actions with normalised map coordinates
        trigger clicks on the game map. Other actions are logged but
        not yet implemented.
        """

        if self._driver is None:
            self._logger.warning(
                "SeleniumDriver.execute called but driver is not started; "
                "action %s will be ignored.",
                action,
            )
            return

        self._logger.info(
            "SeleniumDriver.execute: action=%s in_game=%s meta=%s",
            action.type,
            self.in_game,
            getattr(action, "meta", None),
        )

        # Block game-related actions until we have successfully entered the game.
        if not self.in_game:
            self._logger.warning(
                "SeleniumDriver.execute: received %s but in_game=False; skipping action.",
                action.type.name,
            )
            return

        if action.type is ActionType.IDLE:
            self._logger.info("SeleniumDriver: IDLE action, nothing to perform.")
            return

        if action.type in {ActionType.MOVE, ActionType.ESCAPE}:
            meta = action.meta or {}
            rel_x = rel_y = None
            if isinstance(meta, dict):
                rel_x = meta.get("rel_x")
                rel_y = meta.get("rel_y")

            if isinstance(rel_x, (int, float)) and isinstance(rel_y, (int, float)):
                self._logger.info(
                    "SeleniumDriver: %s using normalised map coordinates rel_x=%.3f rel_y=%.3f.",
                    action.type.name,
                    float(rel_x),
                    float(rel_y),
                )
                try:
                    self._click_on_map_relative(float(rel_x), float(rel_y))
                except Exception:
                    self._logger.exception(
                        "Error while clicking on map for %s at rel=(%s, %s).",
                        action.type.name,
                        rel_x,
                        rel_y,
                    )
            else:
                self._logger.warning(
                    "SeleniumDriver.execute: MOVE/ESCAPE without rel_x/rel_y in meta, skipping."
                )
            return

        if action.type is ActionType.ATTACK:
            # TODO: Implement actual attack execution:
            #  - either by clicking on the NPC on the mini-map/main map
            #  - or by pressing the appropriate attack key.
            self._logger.info(
                "SeleniumDriver: ATTACK action on target_id=%s (not implemented yet)",
                action.target_id,
            )
            return

        # Other actions (ATTACK, COLLECT, JUMP, REPAIR, etc.) are acknowledged
        # but not implemented yet.
        self._logger.info(
            "SeleniumDriver.execute: received unsupported action type=%s target_id=%s; "
            "no concrete implementation yet.",
            action.type.name,
            action.target_id,
        )
