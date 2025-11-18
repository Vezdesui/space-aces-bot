from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any, Dict, Mapping, Union

from dotenv import load_dotenv


# Load environment variables from a .env file located in the project root (if present).
load_dotenv()


def _resolve_default_config_path() -> Path:
    """Return the default configuration file path.

    The function looks in the current working directory for a ``configs``
    directory and prefers ``config.json`` over ``config.example.json``.
    """

    configs_dir = Path.cwd() / "configs"
    primary = configs_dir / "config.json"
    fallback = configs_dir / "config.example.json"

    if primary.is_file():
        return primary
    if fallback.is_file():
        return fallback

    raise FileNotFoundError(
        f"Could not find configuration file in {configs_dir} "
        "(expected config.json or config.example.json)."
    )


def load_config(path: Union[str, Path, None] = None) -> Dict[str, Any]:
    """Load configuration from JSON and return it as a dict.

    If *path* is ``None``, the configuration is loaded from the default
    location: ``configs/config.json`` (if it exists in the current working
    directory) or ``configs/config.example.json`` as a fallback.

    The resulting mapping is returned as-is and may contain nested sections
    such as ``\"selenium\"`` without any additional processing.
    """

    config_path: Path
    if path is None:
        config_path = _resolve_default_config_path()
    else:
        config_path = Path(path)

    if not config_path.is_file():
        raise FileNotFoundError(f"Config file not found: {config_path}")

    with config_path.open("r", encoding="utf-8") as config_file:
        data: Mapping[str, Any] = json.load(config_file)

    if not isinstance(data, dict):
        raise ValueError(f"Config file {config_path} must contain a JSON object at the top level.")

    config: Dict[str, Any] = dict(data)

    username_env = os.environ.get("SPACE_ACES_USERNAME")
    if username_env:
        config["username"] = username_env

    password_env = os.environ.get("SPACE_ACES_PASSWORD")
    if password_env:
        config["password"] = password_env

    return config
