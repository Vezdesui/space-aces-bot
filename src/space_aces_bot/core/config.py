from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, Union


def load_config(path: Union[str, Path]) -> Dict[str, Any]:
    """Load configuration from a JSON file and return it as a dict."""
    config_path = Path(path)

    if not config_path.is_file():
        raise FileNotFoundError(f"Config file not found: {config_path}")

    with config_path.open("r", encoding="utf-8") as config_file:
        data = json.load(config_file)

    if not isinstance(data, dict):
        raise ValueError(f"Config file {config_path} must contain a JSON object at the top level.")

    return data

