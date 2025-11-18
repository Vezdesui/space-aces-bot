from __future__ import annotations

import logging
import os
from typing import Any, Dict

try:  # pragma: no cover - import guards
    import cv2  # type: ignore[import]
except Exception:  # pragma: no cover - handled gracefully at runtime
    cv2 = None  # type: ignore[assignment]

try:  # pragma: no cover - import guards
    import numpy as np  # type: ignore[import]
except Exception:  # pragma: no cover - handled gracefully at runtime
    np = None  # type: ignore[assignment]

try:  # pragma: no cover - import guards
    from PIL import ImageGrab  # type: ignore[import]
except Exception:  # pragma: no cover - handled gracefully at runtime
    ImageGrab = None  # type: ignore[assignment]

from space_aces_bot.core.game_state import GameState, Npc, Position, Resource
from space_aces_bot.core.interfaces import Vision

logger = logging.getLogger(__name__)


class DummyVision(Vision):
    """Fallback vision module that only advances ticks.

    Used when vision is explicitly disabled in configuration.
    """

    def update_state(self, state: GameState) -> None:
        logger.debug("DummyVision.update_state: vision disabled, advancing tick only.")
        state.advance_tick()

    def screenshot(self) -> Any:
        logger.debug("DummyVision.screenshot: vision disabled, returning None.")
        return None


class TemplateVision(Vision):
    """Vision module based on template matching with OpenCV.

    It captures a screen region, runs ``cv2.matchTemplate`` for known
    templates and updates ``GameState.resources`` and ``GameState.npcs``.
    """

    def __init__(self, vision_cfg: Dict[str, Any] | None = None, logger: logging.Logger | None = None) -> None:
        self.logger = logger or logging.getLogger(__name__)

        cfg: Dict[str, Any] = dict(vision_cfg or {})

        self.enabled: bool = bool(cfg.get("enabled", True))
        self.templates_path: str = cfg.get("templates_path", "assets/templates/")
        self.min_match_score: float = float(cfg.get("min_match_score", 0.8))
        self.max_detections_per_type: int = int(cfg.get("max_detections_per_type", 10))

        region_cfg: Dict[str, Any] = cfg.get("capture_region", {}) or {}
        self.capture_left: int = int(region_cfg.get("left", 0))
        self.capture_top: int = int(region_cfg.get("top", 0))
        self.capture_width: int = int(region_cfg.get("width", 1920))
        self.capture_height: int = int(region_cfg.get("height", 1080))

        self.templates: Dict[str, "np.ndarray"] = {}
        mapping: Dict[str, str] = {
            "bonus_box": "bonus_box.png",
            "cargo_box": "cargo_box.png",
            "weak_npc": "npc_weak.png",
            "medium_npc": "npc_medium.png",
        }

        if cv2 is None:
            self.logger.error(
                "TemplateVision: OpenCV (cv2) is not available; "
                "templates will not be loaded and vision will be inactive.",
            )
        else:
            for kind, filename in mapping.items():
                path = os.path.join(self.templates_path, filename)
                img = cv2.imread(path, cv2.IMREAD_COLOR)  # type: ignore[call-arg]
                if img is not None:
                    self.templates[kind] = img
                else:
                    self.logger.warning("Vision: template %s not found at %s", kind, path)

        self.logger.info(
            "TemplateVision initialized: enabled=%s, templates=%d, min_match_score=%.2f, region=(%d,%d,%d,%d)",
            self.enabled,
            len(self.templates),
            self.min_match_score,
            self.capture_left,
            self.capture_top,
            self.capture_width,
            self.capture_height,
        )

    def screenshot(self) -> Any:
        """Capture a screenshot of the configured region as a PIL image."""

        if not self.enabled:
            self.logger.debug("TemplateVision.screenshot: vision disabled, returning None.")
            return None

        if ImageGrab is None:
            self.logger.error(
                "TemplateVision.screenshot: PIL.ImageGrab is not available; "
                "cannot capture screen.",
            )
            return None

        left = self.capture_left
        top = self.capture_top
        width = self.capture_width
        height = self.capture_height
        bbox = (left, top, left + width, top + height)

        try:
            img = ImageGrab.grab(bbox=bbox)
            return img
        except Exception as exc:  # pragma: no cover - environment dependent
            self.logger.error("TemplateVision.screenshot: failed to grab screen: %s", exc)
            return None

    def update_state(self, state: GameState) -> None:
        """Update game state from the current screenshot using template matching."""

        # Maintain tick bookkeeping.
        state.advance_tick()

        if not self.enabled:
            self.logger.debug("TemplateVision.update_state: vision disabled, skipping update.")
            return

        if not state.current_map:
            self.logger.debug("TemplateVision.update_state: current_map is not set, skipping update.")
            return

        frame = self.screenshot()
        if frame is None:
            self.logger.debug("TemplateVision.update_state: no frame captured, skipping.")
            return

        if cv2 is None or np is None:
            self.logger.error(
                "TemplateVision.update_state: cv2 or numpy is not available; "
                "template matching is disabled.",
            )
            return

        img = cv2.cvtColor(np.array(frame), cv2.COLOR_RGB2BGR)  # type: ignore[arg-type]
        h, w = img.shape[:2]
        if h == 0 or w == 0:
            self.logger.warning("TemplateVision.update_state: captured empty frame (%d x %d).", w, h)
            return

        new_resources: Dict[str, Resource] = {}
        new_npcs: Dict[str, Npc] = {}
        counters: Dict[str, int] = {}

        for kind, template in self.templates.items():
            th, tw = template.shape[:2]
            if th == 0 or tw == 0:
                continue

            result = cv2.matchTemplate(img, template, cv2.TM_CCOEFF_NORMED)
            ys, xs = np.where(result >= self.min_match_score)
            if len(xs) == 0:
                continue

            scores = result[ys, xs]
            detections = sorted(
                zip(scores, xs, ys),
                key=lambda item: item[0],
                reverse=True,
            )
            detections = detections[: self.max_detections_per_type]

            for score, x, y in detections:
                cx = x + tw / 2.0
                cy = y + th / 2.0
                rel_x = cx / float(w)
                rel_y = cy / float(h)

                count = counters.get(kind, 0) + 1
                counters[kind] = count

                if kind in ("bonus_box", "cargo_box"):
                    res_id = f"res-{kind}-{count}"
                    new_resources[res_id] = Resource(
                        id=res_id,
                        position=Position(x=rel_x, y=rel_y),
                        resource_type=kind,
                        value=0,
                        kind=kind,
                    )
                elif kind in ("weak_npc", "medium_npc"):
                    npc_id = f"npc-{kind}-{count}"
                    new_npcs[npc_id] = Npc(
                        id=npc_id,
                        position=Position(x=rel_x, y=rel_y),
                        hp=100,
                        max_hp=100,
                        npc_type=kind,
                    )

        # Replace old resources with the newly detected ones.
        state.resources = new_resources

        # For simplicity, fully replace NPCs detected via vision.
        if new_npcs:
            state.npcs = new_npcs

        if new_resources or new_npcs:
            self.logger.info(
                "TemplateVision.update_state: detected %d resources, %d NPCs",
                len(new_resources),
                len(new_npcs),
            )
        else:
            self.logger.debug("TemplateVision.update_state: no objects detected.")
