from __future__ import annotations

import logging
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
    logger.info(
        "[space_aces_bot] starting main loop with driver=%s",
        driver_name,
    )

    # Start the driver once before entering the main loop, if supported.
    if hasattr(driver, "start"):
        try:
            logger.info("Starting driver: %s", driver_name)
            driver.start()  # type: ignore[call-arg]
        except Exception:
            logger.exception("Error while starting driver: %s", driver_name)

    max_ticks = 20
    try:
        for _ in range(max_ticks):
            logger.info("Main loop tick %s", state.tick_counter)

            # Update game state based on what we see.
            vision.update_state(state)

            # First, let safety decide if we need to escape or repair.
            danger_action = safety.decide(state)
            if danger_action is not None:
                logger.info("Safety produced action: %s", danger_action)
                driver.execute(danger_action, state)
                state.tick_counter += 1
                time.sleep(0.3)
                continue

            # If it's safe, try to farm or fight.
            farm_action = farm.decide(state)
            primary_action = farm_action

            if primary_action is None:
                primary_action = combat.decide(state)

            if primary_action is not None:
                logger.info("Primary module produced action: %s", primary_action)
                driver.execute(primary_action, state)

            # Let navigation propose a move if needed.
            nav_action = navigation.tick(state)
            if nav_action is not None:
                logger.info("Navigation produced action: %s", nav_action)
                driver.execute(nav_action, state)

            # Tick bookkeeping and small delay between iterations.
            state.tick_counter += 1
            time.sleep(0.3)

        logger.info("[space_aces_bot] stopping main loop")
    finally:
        # Ensure the driver is properly stopped even if an error occurs.
        if hasattr(driver, "stop"):
            try:
                logger.info("Stopping driver: %s", driver_name)
                driver.stop()  # type: ignore[call-arg]
                logger.info("[space_aces_bot] driver stopped")
            except Exception:
                logger.exception("Error while stopping driver: %s", driver_name)
