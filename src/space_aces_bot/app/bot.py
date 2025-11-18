from __future__ import annotations

import logging
import random
import time
from pathlib import Path
from typing import Any, Mapping

from space_aces_bot.app.factory import create_default_modules
from space_aces_bot.core.config import load_config
from space_aces_bot.core.game_state import GameState, Position, Ship


def _find_config_file() -> Path:
    """Return path to the primary config file, preferring config.json."""
    project_root = Path(__file__).resolve().parents[3]
    configs_dir = project_root / "configs"

    candidates = [
        configs_dir / "config.json",
        configs_dir / "config.example.json",
    ]

    for candidate in candidates:
        if candidate.is_file():
            return candidate

    raise FileNotFoundError(
        f"Could not find configuration file in {configs_dir} "
        "(expected config.json or config.example.json)."
    )


def _setup_logging() -> None:
    """Configure root logger with optional color support."""
    root_logger = logging.getLogger()

    # Avoid reconfiguring logging if it's already set up.
    if root_logger.handlers:
        return

    root_logger.setLevel(logging.INFO)

    try:
        from colorlog import ColoredFormatter  # type: ignore[import]

        handler = logging.StreamHandler()
        formatter = ColoredFormatter(
            "%(log_color)s[%(asctime)s] [%(levelname)s] %(name)s: %(message)s",
            datefmt="%H:%M:%S",
            log_colors={
                "DEBUG": "cyan",
                "INFO": "green",
                "WARNING": "yellow",
                "ERROR": "red",
                "CRITICAL": "red,bg_white",
            },
        )
        handler.setFormatter(formatter)
        root_logger.addHandler(handler)
    except Exception:  # pragma: no cover - fallback is straightforward
        handler = logging.StreamHandler()
        formatter = logging.Formatter(
            "[%(asctime)s] [%(levelname)s] %(name)s: %(message)s", datefmt="%H:%M:%S"
        )
        handler.setFormatter(formatter)
        root_logger.addHandler(handler)


def main() -> None:
    """Entry point for the space_aces_bot application."""
    _setup_logging()
    logger = logging.getLogger(__name__)

    config_path = _find_config_file()
    config: Mapping[str, Any] = load_config(config_path)

    # Create an initial, minimal game state for the bot.
    ship = Ship(
        id="player-1",
        position=Position(x=0.0, y=0.0),
        hp=100,
        max_hp=100,
        shield=50,
        max_shield=50,
        speed=1.0,
    )

    state = GameState(ship=ship, current_map="1-1")

    modules = create_default_modules(config)
    navigation = modules["navigation"]
    vision = modules["vision"]
    combat = modules["combat"]
    farm = modules["farm"]
    safety = modules["safety"]
    driver = modules["driver"]

    driver_name = type(driver).__name__
    logger.info("[space_aces_bot] initialising driver=%s", driver_name)

    runtime_cfg = config.get("runtime", {}) or {}
    max_ticks = int(runtime_cfg.get("max_ticks", 300))
    max_seconds = float(runtime_cfg.get("max_seconds", 0))
    try:
        # Start the driver and perform login, if supported.
        if hasattr(driver, "start"):
            try:
                logger.info("Starting driver: %s", driver_name)
                driver.start()  # type: ignore[call-arg]
            except Exception:
                logger.exception("Error while starting driver: %s", driver_name)

        login_performed = False

        if hasattr(driver, "login"):
            # Credentials are expected to come from config, which may be
            # populated from .env via python-dotenv.
            username = str(config.get("username", "")).strip()
            password = str(config.get("password", "")).strip()

            if not username or not password:
                logger.error(
                    "Username or password is missing in configuration; "
                    "cannot perform login. Aborting before main loop.",
                )
                return

            logger.info("Attempting to login to Space Aces...")

            try:
                login_ok = driver.login(username, password)  # type: ignore[call-arg]
                login_performed = True
            except Exception:
                # SeleniumDriver.login should already log the traceback;
                # this handler is only a final safeguard.
                logger.exception("Unexpected error while attempting to log in.")
                logger.info("Login failed, stopping bot.")
                return

            if login_ok:
                logger.info(
                    "Login successful, starting on map '%s'.",
                    getattr(state, "current_map", "unknown"),
                )
            else:
                logger.info("Login failed, stopping bot.")
                return
        else:
            logger.info(
                "Driver %s does not support login(); starting without explicit login step.",
                driver_name,
            )

        # After a successful login, attempt to enter the in-game view.
        if hasattr(driver, "enter_game"):
            if login_performed:
                logger.info("Attempting to enter Space Aces game view...")

                try:
                    enter_ok = driver.enter_game()  # type: ignore[call-arg]
                except Exception:
                    logger.exception("Unexpected error while attempting to enter the game.")
                    logger.info("enter_game failed, stopping bot.")
                    return

                if enter_ok:
                    logger.info("enter_game successful, starting main loop.")
                else:
                    logger.info("enter_game failed, stopping bot.")
                    return
            else:
                logger.info(
                    "Driver %s supports enter_game() but login was not performed; "
                    "skipping enter_game step.",
                    driver_name,
                )
        else:
            logger.info(
                "Driver %s does not support enter_game(); starting without explicit game entry step.",
                driver_name,
            )

        stop_reason = "normal"

        logger.info(
            "[space_aces_bot] starting main loop with driver=%s",
            driver_name,
        )

        start_time = time.time()

        for _ in range(max_ticks):
            now = time.time()
            if max_seconds > 0 and (now - start_time) >= max_seconds:
                stop_reason = f"max_seconds reached: {max_seconds}"
                logger.info(
                    "Main loop time limit reached (%.1f seconds), breaking",
                    max_seconds,
                )
                break

            logger.info("Main loop tick %s", state.tick_counter)

            # Update game state based on what we see.
            vision.update_state(state)

            # Let safety assess current danger level.
            danger_level = safety.assess(state)
            if state.tick_counter % 10 == 0:
                logger.info("Safety: current danger level=%d", danger_level)

            # Decide if we need to escape or repair.
            escape_action = safety.decide(state)
            if escape_action is not None:
                logger.info("Safety produced ESCAPE action: %s", escape_action)
                if hasattr(navigation, "enter_escape_mode"):
                    navigation.enter_escape_mode()  # type: ignore[call-arg]
                    nav_mode = getattr(navigation, "_mode", "unknown")
                    logger.info("Navigation mode after ESCAPE: %s", nav_mode)

                driver.execute(escape_action, state)
                state.advance_tick()

                # Small randomised delay between iterations.
                time.sleep(random.uniform(0.15, 0.35))
                continue

            # If it's safe, ensure navigation is in patrol mode.
            if hasattr(navigation, "enter_patrol_mode"):
                navigation.enter_patrol_mode()  # type: ignore[call-arg]
                nav_mode = getattr(navigation, "_mode", "unknown")
                logger.debug("Navigation mode (patrol path): %s", nav_mode)

            # If it's safe, let Farm try to produce a high-level action.
            farm_action = farm.decide(state)
            if farm_action is not None:
                logger.info("Farm produced action: %s", farm_action)
                driver.execute(farm_action, state)
                state.advance_tick()

                time.sleep(random.uniform(0.15, 0.35))
                continue

            # If Farm did not act, let Combat control tactical behaviour.
            combat_action = combat.decide(state)
            if combat_action is not None:
                logger.info("Combat produced action: %s", combat_action)
                driver.execute(combat_action, state)
                state.advance_tick()

                time.sleep(random.uniform(0.15, 0.35))
                continue

            # Let navigation propose a move if needed.
            nav_action = navigation.tick(state)
            if nav_action is not None:
                logger.info("Navigation produced action: %s", nav_action)
                driver.execute(nav_action, state)

            # Tick bookkeeping and small randomised delay between iterations.
            state.advance_tick()
            time.sleep(random.uniform(0.15, 0.35))
        else:
            stop_reason = f"max_ticks reached: {max_ticks}"

        logger.info("[space_aces_bot] stopping main loop")
    finally:
        logger.info(
            "Main loop finished, reason=%s, total_ticks=%d",
            stop_reason,
            state.tick_counter,
        )
        # Ensure the driver is properly stopped even if an error occurs.
        if hasattr(driver, "stop"):
            try:
                logger.info("Stopping driver: %s", driver_name)
                driver.stop()  # type: ignore[call-arg]
                logger.info("[space_aces_bot] driver stopped")
            except Exception:
                logger.exception("Error while stopping driver: %s", driver_name)
