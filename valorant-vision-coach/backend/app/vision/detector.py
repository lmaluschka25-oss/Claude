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
    kind: str  # "mm_self" | "mm_enemy" | "viewport_enemy" | "viewport_ally"
    agent: str | None
    is_enemy: bool


def parse_label(label: str) -> ParsedLabel:
    """Interpret a detector label into structured semantics."""
    raw = label.strip().lower()
    if raw in {"mm_self", "self", "player"}:
        return ParsedLabel("mm_self", None, False)
    if raw.startswith("mm_enemy") or raw == "mm_enemy":
        agent = raw.split(":", 1)[1] if ":" in raw else None
        return ParsedLabel("mm_enemy", normalize_agent(agent), True)
    if raw.startswith("ally"):
        agent = raw.split(":", 1)[1] if ":" in raw else None
        return ParsedLabel("viewport_ally", normalize_agent(agent), False)
    # Default: anything else that names an enemy in the viewport.
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
# A couple of enemy "tracks" expressed as normalized map waypoints. The mock
# walks enemies along these routes so last-known-position, rotation, and
# site-pressure analysis all receive realistic, continuous signal.
_ENEMY_TRACKS: list[dict] = [
    {
        "agent": "Jett",
        "appear": 4.0,
        "waypoints": [(0.50, 0.85), (0.50, 0.62), (0.40, 0.45), (0.22, 0.30), (0.18, 0.20)],
        "duration": 26.0,
    },
    {
        "agent": "Sova",
        "appear": 9.0,
        "waypoints": [(0.52, 0.88), (0.62, 0.66), (0.74, 0.52), (0.82, 0.34), (0.80, 0.22)],
        "duration": 30.0,
    },
    {
        "agent": "Killjoy",
        "appear": 2.0,
        "waypoints": [(0.80, 0.24), (0.80, 0.26), (0.78, 0.28)],  # holding a site
        "duration": 40.0,
    },
]


class MockDetector(BaseDetector):
    """Deterministic synthetic detector for demos and tests.

    It emits a steady ``mm_self`` marker plus revealed ``mm_enemy`` markers that
    travel along predefined routes, projecting normalized map coordinates back
    into minimap pixels through the calibration so the downstream transform is
    genuinely exercised.
    """

    ready = True

    def __init__(self, calibration: MinimapCalibration | None = None) -> None:
        self.calibration = calibration or DEFAULT_CALIBRATION

    def _map_to_pixel(self, u: float, v: float, w: int, h: int) -> tuple[float, float]:
        rx, ry, rw, rh = self.calibration.roi_pixels(w, h)
        return rx + u * rw, ry + v * rh

    @staticmethod
    def _walk(track: dict, t: float) -> tuple[float, float] | None:
        appear = track["appear"]
        duration = track["duration"]
        if t < appear or t > appear + duration:
            return None
        pts = track["waypoints"]
        if len(pts) == 1:
            return pts[0]
        frac = (t - appear) / duration
        seg = frac * (len(pts) - 1)
        i = min(int(seg), len(pts) - 2)
        local = seg - i
        (x0, y0), (x1, y1) = pts[i], pts[i + 1]
        return x0 + (x1 - x0) * local, y0 + (y1 - y0) * local

    def detect(self, frame: np.ndarray, frame_index: int, timestamp: float) -> list[RawDetection]:
        h, w = frame.shape[:2]
        out: list[RawDetection] = []

        # Player marker drifts slowly near defender spawn / mid.
        su = 0.5 + 0.05 * math.sin(timestamp / 7.0)
        sv = 0.78 + 0.03 * math.cos(timestamp / 5.0)
        spx, spy = self._map_to_pixel(su, sv, w, h)
        out.append(RawDetection("mm_self", 0.99, (spx - 6, spy - 6, 12, 12)))

        for track in _ENEMY_TRACKS:
            pos = self._walk(track, timestamp)
            if pos is None:
                continue
            # Reveals flicker: visible ~70% of the time once active.
            if (int(timestamp * 2) + hash(track["agent"]) % 3) % 10 < 3:
                continue
            u, v = pos
            px, py = self._map_to_pixel(u, v, w, h)
            conf = 0.6 + 0.2 * math.sin(timestamp + len(track["agent"]))
            out.append(
                RawDetection(
                    f"mm_enemy:{track['agent']}",
                    round(min(max(conf, 0.4), 0.95), 3),
                    (px - 6, py - 6, 12, 12),
                )
            )
        return out


def build_detector(settings: Settings) -> BaseDetector:
    """Construct the configured detector backend."""
    backend = settings.detector_backend.lower()
    if backend == "mock":
        logger.info("Using MockDetector (synthetic detections).")
        return MockDetector()
    detector = YoloDetector(settings)
    if not detector.ready:
        logger.warning(
            "YOLO backend is not ready; falling back to MockDetector so the "
            "pipeline still produces output. Provide weights for real analysis."
        )
        return MockDetector()
    return detector
