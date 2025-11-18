from __future__ import annotations

import time
from pathlib import Path

from space_aces_bot.core.config import load_config
from space_aces_bot.core.game_state import GameState


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


def main() -> None:
    """Entry point for the space_aces_bot application."""
    config_path = _find_config_file()
    # Load configuration to ensure it's valid and available to the application.
    _config = load_config(config_path)

    game_state = GameState()

    print("[space_aces_bot] skeleton running")

    for tick in range(1, 4):
        game_state.tick_counter = tick
        print(f"[space_aces_bot] tick {tick}: {game_state}")
        time.sleep(0.5)

    print("[space_aces_bot] finished.")

