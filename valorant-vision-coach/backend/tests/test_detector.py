import cv2
import numpy as np

from app.config import get_settings
from app.vision.detector import MinimapColorDetector

SETTINGS = get_settings()


def _frame_with_enemy_dot(w, h, cx, cy, r=5):
    # Default enemy gate is yellow (hue ~30); draw a yellow marker (BGR 0,255,255).
    frame = np.zeros((h, w, 3), dtype=np.uint8)
    cv2.circle(frame, (cx, cy), r, (0, 255, 255), -1)
    return frame


def test_minimap_detector_finds_enemy_marker_in_roi():
    det = MinimapColorDetector(SETTINGS)
    w, h = 1280, 720
    rx, ry, rw, rh = SETTINGS.minimap_calibration().roi_pixels(w, h)
    cx, cy = rx + rw // 2, ry + rh // 2
    frame = _frame_with_enemy_dot(w, h, cx, cy)

    dets = det.detect(frame, 0, 0.0)
    assert len(dets) >= 1
    dx, dy = dets[0].center
    assert abs(dx - cx) < 6 and abs(dy - cy) < 6
    assert dets[0].label == "mm_enemy"


def test_minimap_detector_ignores_marker_outside_roi():
    det = MinimapColorDetector(SETTINGS)
    w, h = 1280, 720
    frame = _frame_with_enemy_dot(w, h, w - 30, h - 30)
    assert det.detect(frame, 0, 0.0) == []
