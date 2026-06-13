"""Object detection backends.

A detector consumes a single BGR frame and returns ``RawDetection`` boxes in
full-frame pixel coordinates. Labels carry semantics that the video processor
interprets:

* ``mm_self``            — the player's own marker on the minimap.
* ``mm_enemy``           — a *revealed* enemy marker on the player's minimap.
* ``enemy`` / ``enemy:<agent>`` — an enemy visible in the 3D viewport.
* ``ally:<agent>``       — an ally visible in the viewport (optional).

Two backends are provided:

* :class:`YoloDetector`  — real inference via Ultralytics YOLO (lazy import).
* :class:`MockDetector`  — deterministic synthetic data, so the full pipeline,
  dashboard, and tests run without trained weights or a GPU.
"""
from __future__ import annotations

import math
from abc import ABC, abstractmethod
from dataclasses import dataclass

import numpy as np

from ..config import Settings
from ..logging_config import get_logger
from .agents import normalize_agent
from .calibration import DEFAULT_CALIBRATION, MinimapCalibration

logger = get_logger(__name__)


@dataclass
class RawDetection:
    label: str
    confidence: float
    bbox: tuple[float, float, float, float]  # x, y, w, h in frame pixels

    @property
    def center(self) -> tuple[float, float]:
        x, y, w, h = self.bbox
        return x + w / 2.0, y + h / 2.0


@dataclass
class ParsedLabel:
    kind: str  # mm_self | mm_enemy | mm_ally | viewport_enemy | viewport_ally | utility
    agent: str | None
    is_enemy: bool
    util_kind: str | None = None


def parse_label(label: str) -> ParsedLabel:
    """Interpret a detector label into structured semantics.

    Vocabulary: ``mm_self``, ``mm_enemy[:agent]``, ``mm_ally[:agent]``,
    ``enemy[:agent]``, ``ally[:agent]``, ``util:<kind>[:agent]``.
    """
    raw = label.strip().lower()
    if raw in {"mm_self", "self", "player"}:
        return ParsedLabel("mm_self", None, False)
    if raw.startswith("util"):
        parts = raw.split(":")
        kind = parts[1] if len(parts) > 1 else "other"
        agent = parts[2] if len(parts) > 2 else None
        return ParsedLabel("utility", normalize_agent(agent), False, util_kind=kind)
    if raw.startswith("mm_enemy"):
        agent = raw.split(":", 1)[1] if ":" in raw else None
        return ParsedLabel("mm_enemy", normalize_agent(agent), True)
    if raw.startswith("mm_ally"):
        agent = raw.split(":", 1)[1] if ":" in raw else None
        return ParsedLabel("mm_ally", normalize_agent(agent), False)
    if raw.startswith("ally"):
        agent = raw.split(":", 1)[1] if ":" in raw else None
        return ParsedLabel("viewport_ally", normalize_agent(agent), False)
    # Default: anything else names an enemy in the viewport.
    agent = raw.split(":", 1)[1] if ":" in raw else None
    return ParsedLabel("viewport_enemy", normalize_agent(agent), True)


class BaseDetector(ABC):
    """Common detector interface."""

    ready: bool = True

    @abstractmethod
    def detect(self, frame: np.ndarray, frame_index: int, timestamp: float) -> list[RawDetection]:
        ...


class YoloDetector(BaseDetector):
    """Ultralytics YOLO inference backend.

    The model is expected to emit the label vocabulary documented at module
    level. Loading is lazy and failure-tolerant: if weights or the library are
    missing, ``ready`` is ``False`` and detection returns nothing (the pipeline
    logs a clear warning rather than crashing).
    """

    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self._model = None
        self.ready = False
        self._load()

    def _load(self) -> None:
        model_path = self.settings.yolo_model_path
        if not model_path.exists():
            logger.warning(
                "YOLO weights not found at %s. Detection disabled — train a model "
                "(see data/models/README.md) or set VVC_DETECTOR_BACKEND=mock.",
                model_path,
            )
            return
        try:
            from ultralytics import YOLO  # lazy, heavy import
        except ImportError:
            logger.warning(
                "ultralytics is not installed. Install it or set "
                "VVC_DETECTOR_BACKEND=mock."
            )
            return
        try:
            self._model = YOLO(str(model_path))
            device = self.settings.yolo_device
            if device and device != "auto":
                self._model.to(device)
            self.ready = True
            logger.info("Loaded YOLO model from %s", model_path)
        except Exception as exc:  # pragma: no cover - depends on runtime env
            logger.exception("Failed to load YOLO model: %s", exc)

    def detect(self, frame: np.ndarray, frame_index: int, timestamp: float) -> list[RawDetection]:
        if not self.ready or self._model is None:
            return []
        results = self._model.predict(
            frame,
            conf=self.settings.yolo_confidence,
            iou=self.settings.yolo_iou,
            verbose=False,
        )
        detections: list[RawDetection] = []
        for result in results:
            names = result.names
            for box in result.boxes:
                cls_id = int(box.cls[0])
                conf = float(box.conf[0])
                x1, y1, x2, y2 = (float(v) for v in box.xyxy[0])
                label = names.get(cls_id, str(cls_id)) if isinstance(names, dict) else names[cls_id]
                detections.append(
                    RawDetection(
                        label=str(label),
                        confidence=conf,
                        bbox=(x1, y1, x2 - x1, y2 - y1),
                    )
                )
        return detections


# --- Synthetic backend ----------------------------------------------------
# A round-aware mock that produces a full, coherent scene (enemies + allies +
# self + utilities + round metadata) so the whole Match-Intelligence dashboard
# can be explored without a trained model. Enemies favour A site (with Killjoy
# anchoring B and Sova holding mid) so cross-round patterns emerge.
_ENEMY_AGENTS = ["Jett", "Omen", "Killjoy", "Sova", "Reyna"]
_ALLY_AGENTS = ["Sage", "Phoenix", "Breach", "Brimstone", "KAY/O"]
_SITE_ANCHORS = {"A": (0.20, 0.22), "B": (0.80, 0.24), "MID": (0.50, 0.50)}
# Enemy site commitment per round — A-heavy, matching the example dashboard.
_SITE_SCHEDULE = ["A", "A", "B", "A", "MID", "A", "B", "A", "A", "MID", "A", "B"]


class MockDetector(BaseDetector):
    """Deterministic synthetic detector for demos and tests."""

    ready = True

    def __init__(self, calibration: MinimapCalibration | None = None) -> None:
        self.calibration = calibration or DEFAULT_CALIBRATION
        self.round_number = 1

    def set_round(self, round_number: int) -> None:
        self.round_number = max(1, round_number)

    def committed_site(self) -> str:
        return _SITE_SCHEDULE[(self.round_number - 1) % len(_SITE_SCHEDULE)]

    def _map_to_pixel(self, u: float, v: float, w: int, h: int) -> tuple[float, float]:
        rx, ry, rw, rh = self.calibration.roi_pixels(w, h)
        return rx + u * rw, ry + v * rh

    def _enemy_targets(self) -> dict[str, tuple[float, float]]:
        ax, ay = _SITE_ANCHORS[self.committed_site()]
        targets = {a: (ax, ay) for a in ("Jett", "Omen", "Reyna")}
        targets["Killjoy"] = _SITE_ANCHORS["B"]  # anchors B
        targets["Sova"] = _SITE_ANCHORS["MID"]  # holds mid
        return targets

    def _marker(self, label: str, conf: float, u: float, v: float, w: int, h: int) -> RawDetection:
        px, py = self._map_to_pixel(min(max(u, 0.02), 0.98), min(max(v, 0.02), 0.98), w, h)
        return RawDetection(label, round(conf, 3), (px - 6, py - 6, 12, 12))

    def detect(self, frame: np.ndarray, frame_index: int, timestamp: float) -> list[RawDetection]:
        h, w = frame.shape[:2]
        out: list[RawDetection] = []
        ease = min(1.0, timestamp / 20.0)

        # Player marker.
        out.append(
            self._marker(
                "mm_self", 0.99,
                0.5 + 0.03 * math.sin(timestamp / 5.0),
                0.72 + 0.02 * math.cos(timestamp / 4.0), w, h,
            )
        )

        # Enemies ease from the defender side toward their per-round target.
        for i, (agent, (tx, ty)) in enumerate(self._enemy_targets().items()):
            sx, sy = (tx, ty) if agent == "Killjoy" else (0.5, 0.12)
            u = sx + (tx - sx) * ease + 0.012 * math.sin(timestamp + i)
            v = sy + (ty - sy) * ease + 0.012 * math.cos(timestamp + i)
            if (int(timestamp) + i) % 7 == 0:  # reveal flicker
                continue
            conf = 0.55 + 0.25 * abs(math.sin(timestamp * 0.5 + i))
            out.append(self._marker(f"mm_enemy:{agent}", conf, u, v, w, h))

        # Teammates push from attacker spawn toward the contested site.
        ax, ay = _SITE_ANCHORS[self.committed_site()]
        for i, agent in enumerate(_ALLY_AGENTS):
            sx, sy = 0.5 + (i - 2) * 0.03, 0.9
            u = sx + (ax - sx) * ease
            v = sy + (ay - sy) * ease
            out.append(self._marker(f"mm_ally:{agent}", 0.95, u, v, w, h))

        # Utilities become active a few seconds in.
        if timestamp > 6.0:
            for kind, agent, (ux, uy) in (
                ("smoke", "Omen", (ax, ay)),
                ("recon", "Sova", _SITE_ANCHORS["MID"]),
                ("turret", "Killjoy", _SITE_ANCHORS["B"]),
            ):
                out.append(self._marker(f"util:{kind}:{agent}", 0.8, ux, uy, w, h))
        return out

    def round_metadata(self, round_number: int) -> dict:
        """Synthetic per-round HUD metadata (OCR is off for the mock backend)."""
        a = min(13, 3 + round_number // 2)
        b = min(13, 1 + round_number // 3)
        economy = "Eco" if round_number % 4 == 2 else "Full Buy"
        killfeed = [
            {"t": 17.0, "killer": "Omen", "victim": "Sage", "weapon": "Vandal",
             "headshot": True, "killer_team": "enemy"},
            {"t": 24.0, "killer": "Phoenix", "victim": "Reyna", "weapon": "Phantom",
             "headshot": False, "killer_team": "ally"},
        ]
        return {
            "side": "attack",
            "economy": economy,
            "score_text": f"{a}-{b}",
            "round_time": "1:12",
            "spike_planted": False,
            "killfeed": killfeed,
        }


class MinimapColorDetector(BaseDetector):
    """Classical computer-vision detector for revealed enemies on the minimap.

    No trained model required: it crops the minimap region (from calibration)
    and finds red enemy markers by HSV color segmentation, returning each blob
    centroid as an ``mm_enemy`` detection in full-frame pixels. Agent identity
    is not recovered (markers carry no name), but positions are real — enough to
    drive the map-based site analysis. Enemies appear on your minimap only when
    legitimately revealed in-game, so this reads nothing hidden.
    """

    ready = True

    def __init__(self, settings: Settings, calibration: MinimapCalibration | None = None) -> None:
        self.settings = settings
        self.calibration = calibration or settings.minimap_calibration()
        self.color_mode = getattr(settings, "minimap_color_mode", "auto")
        self.sat_min = settings.minimap_enemy_sat_min
        self.val_min = settings.minimap_enemy_val_min
        self.hue_min = settings.minimap_enemy_hue_min
        self.hue_max = settings.minimap_enemy_hue_max
        self.min_area = settings.minimap_min_area
        self.max_area = settings.minimap_max_area

    def _build_mask(self, hsv):
        """Binary mask of enemy-coloured pixels per the selected color mode."""
        import cv2

        s, v = self.sat_min, self.val_min

        def band(lo_h, hi_h):
            return cv2.inRange(hsv, np.array([lo_h, s, v]), np.array([hi_h, 255, 255]))

        mode = (self.color_mode or "auto").lower()
        if mode == "red":
            mask = band(0, 10) | band(168, 179)
        elif mode == "yellow":
            mask = band(15, 40)
        elif mode == "custom":
            mask = band(self.hue_min, self.hue_max)
        else:  # auto: saturated red OR yellow (the two common enemy tones)
            mask = band(0, 10) | band(168, 179) | band(15, 40)
        return mask

    def _roi_mask(self, frame: np.ndarray):
        """Return the minimap ROI box and the binary enemy-marker mask within it."""
        import cv2

        h, w = frame.shape[:2]
        rx, ry, rw, rh = self.calibration.roi_pixels(w, h)
        roi = frame[ry : ry + rh, rx : rx + rw]
        if roi.size == 0:
            return rx, ry, rw, rh, None

        hsv = cv2.cvtColor(roi, cv2.COLOR_BGR2HSV)
        mask = self._build_mask(hsv)
        kernel = np.ones((2, 2), np.uint8)
        mask = cv2.morphologyEx(mask, cv2.MORPH_OPEN, kernel)
        mask = cv2.morphologyEx(mask, cv2.MORPH_CLOSE, kernel)
        return rx, ry, rw, rh, mask

    def find_enemies(self, frame: np.ndarray) -> list[RawDetection]:
        """Return enemy-marker detections (also used by the calibration preview)."""
        import cv2

        rx, ry, _, _, mask = self._roi_mask(frame)
        if mask is None:
            return []
        contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        detections: list[RawDetection] = []
        for c in contours:
            area = cv2.contourArea(c)
            if not (self.min_area <= area <= self.max_area):
                continue
            # Enemy markers are compact/round; reject elongated map artifacts.
            circ = 1.0
            if area >= 10:
                peri = cv2.arcLength(c, True)
                if peri <= 0:
                    continue
                circ = 4.0 * math.pi * area / (peri * peri)
                if circ < 0.45:
                    continue
            m = cv2.moments(c)
            if m["m00"] == 0:
                continue
            cx = rx + m["m10"] / m["m00"]
            cy = ry + m["m01"] / m["m00"]
            # Roundness + size → confidence.
            conf = max(0.45, min(0.95, 0.45 + 0.3 * circ + area / (self.max_area * 3.0)))
            detections.append(RawDetection("mm_enemy", round(conf, 3), (cx - 5, cy - 5, 10, 10)))
        return detections

    def mask_overlay(self, frame: np.ndarray) -> np.ndarray:
        """Return a copy of the frame with color-matched pixels tinted cyan."""
        rx, ry, rw, rh, mask = self._roi_mask(frame)
        out = frame.copy()
        if mask is not None:
            region = out[ry : ry + rh, rx : rx + rw]
            region[mask > 0] = (255, 255, 0)
        return out

    def detect(self, frame: np.ndarray, frame_index: int, timestamp: float) -> list[RawDetection]:
        return self.find_enemies(frame)


def build_detector(settings: Settings) -> BaseDetector:
    """Construct the configured detector backend."""
    backend = settings.detector_backend.lower()
    if backend == "mock":
        logger.info("Using MockDetector (synthetic detections).")
        return MockDetector()
    if backend == "minimap":
        logger.info("Using MinimapColorDetector (classical CV on the minimap).")
        return MinimapColorDetector(settings)
    detector = YoloDetector(settings)
    if not detector.ready:
        logger.warning(
            "YOLO backend is not ready; falling back to MockDetector so the "
            "pipeline still produces output. Provide weights for real analysis."
        )
        return MockDetector()
    return detector
