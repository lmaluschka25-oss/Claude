"""Persisted minimap calibration — editable at runtime from the Settings UI.

Stored as a small JSON file in the writable data dir so changes survive
restarts and apply to processing without editing ``.env`` or rebuilding.
Values fall back to the config defaults when unset.
"""
from __future__ import annotations

import json

from ..config import Settings

FIELDS = (
    "x_frac", "y_frac", "w_frac", "h_frac", "rotation", "flip_x",
    "color_mode", "hue_min", "hue_max", "sat_min", "val_min", "min_area", "max_area",
    "analysis_interval", "confidence_threshold", "pattern_weight",
    "memory_weight", "recommendation_min_confidence", "timeline_detail",
    "detection_confirm_threshold",
)


def _path(settings: Settings):
    return settings.upload_dir.parent / "calibration.json"


def defaults(settings: Settings) -> dict:
    return {
        "x_frac": settings.minimap_x_frac,
        "y_frac": settings.minimap_y_frac,
        "w_frac": settings.minimap_w_frac,
        "h_frac": settings.minimap_h_frac,
        "rotation": settings.minimap_rotation,
        "flip_x": settings.minimap_flip_x,
        "color_mode": settings.minimap_color_mode,
        "hue_min": settings.minimap_enemy_hue_min,
        "hue_max": settings.minimap_enemy_hue_max,
        "sat_min": settings.minimap_enemy_sat_min,
        "val_min": settings.minimap_enemy_val_min,
        "min_area": settings.minimap_min_area,
        "max_area": settings.minimap_max_area,
        "analysis_interval": settings.analysis_interval,
        "confidence_threshold": settings.confidence_threshold,
        "pattern_weight": settings.pattern_weight,
        "memory_weight": settings.memory_weight,
        "recommendation_min_confidence": settings.recommendation_min_confidence,
        "timeline_detail": settings.timeline_detail,
        "detection_confirm_threshold": settings.detection_confirm_threshold,
    }


def load(settings: Settings) -> dict:
    data = defaults(settings)
    path = _path(settings)
    if path.exists():
        try:
            stored = json.loads(path.read_text(encoding="utf-8"))
            data.update({k: v for k, v in stored.items() if k in FIELDS})
        except Exception:  # noqa: BLE001 - corrupt file → defaults
            pass
    return data


def save(settings: Settings, updates: dict) -> dict:
    data = load(settings)
    data.update({k: v for k, v in updates.items() if k in FIELDS and v is not None})
    path = _path(settings)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2), encoding="utf-8")
    return data


def reset(settings: Settings) -> dict:
    """Delete saved overrides → back to config defaults."""
    path = _path(settings)
    if path.exists():
        try:
            path.unlink()
        except OSError:
            pass
    return defaults(settings)


def calibration(settings: Settings):
    from ..vision.calibration import MinimapCalibration

    d = load(settings)
    return MinimapCalibration(
        x_frac=float(d["x_frac"]), y_frac=float(d["y_frac"]),
        w_frac=float(d["w_frac"]), h_frac=float(d["h_frac"]),
        rotation=int(d["rotation"]), flip_x=bool(d["flip_x"]),
    )


def apply_to_multistage(detector, settings: Settings) -> None:
    """Push saved color/area/threshold onto a MultiStageMinimapDetector."""
    d = load(settings)
    detector.calibration = calibration(settings)
    detector.color_mode = str(d.get("color_mode", "auto"))
    detector.hue_min = int(d["hue_min"])
    detector.hue_max = int(d["hue_max"])
    detector.sat_floor = max(50, int(d["sat_min"]) - 70)
    detector.val_floor = max(70, int(d["val_min"]) - 60)
    detector.min_area = float(d["min_area"])
    detector.max_area = float(d["max_area"])
    detector.threshold = float(d.get("detection_confirm_threshold", detector.threshold))


def apply_to_detector(detector, settings: Settings) -> None:
    """Push the stored calibration + color band onto a MinimapColorDetector."""
    d = load(settings)
    detector.calibration = calibration(settings)
    detector.color_mode = str(d.get("color_mode", "auto"))
    detector.hue_min = int(d["hue_min"])
    detector.hue_max = int(d["hue_max"])
    detector.sat_min = int(d["sat_min"])
    detector.val_min = int(d["val_min"])
    detector.min_area = float(d["min_area"])
    detector.max_area = float(d["max_area"])
