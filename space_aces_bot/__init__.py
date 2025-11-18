from __future__ import annotations

from pathlib import Path


_PKG_DIR = Path(__file__).resolve().parent
_SRC_PKG_DIR = _PKG_DIR.parent / "src" / "space_aces_bot"

if _SRC_PKG_DIR.is_dir():
    # Delegate submodule loading to the src/ layout.
    __path__ = [str(_SRC_PKG_DIR)]
else:
    __path__ = [str(_PKG_DIR)]

