import cv2
import numpy as np

from app.config import get_settings
from app.vision.multistage import MultiStageMinimapDetector

SETTINGS = get_settings()


def _frame(cx, cy, color, r=5):
    f = np.zeros((720, 1280, 3), dtype=np.uint8)
    cv2.circle(f, (cx, cy), r, color, -1)
    return f


def _roi_center():
    rx, ry, rw, rh = SETTINGS.minimap_calibration().roi_pixels(1280, 720)
    return rx + rw // 2, ry + rh // 2


def test_multistage_confirms_persistent_enemy_blob():
    det = MultiStageMinimapDetector(SETTINGS)
    cx, cy = _roi_center()
    red = _frame(cx, cy, (0, 0, 255))  # red enemy ping (BGR)
    # Feed a few frames so the motion/persistence cue accumulates.
    dets = []
    for i in range(3):
        dets = det.detect(red, i, i * 0.5)
    assert len(dets) >= 1
    d = dets[0]
    assert d.label == "mm_enemy"
    assert d.confidence >= det.threshold
    assert d.meta and "shape" in d.meta and "template" in d.meta and "motion" in d.meta


def test_multistage_excludes_teammate_green():
    det = MultiStageMinimapDetector(SETTINGS)
    cx, cy = _roi_center()
    green = _frame(cx, cy, (0, 255, 0))  # teammate green
    for i in range(3):
        out = det.detect(green, i, i * 0.5)
    assert out == []


def _cross(cx, cy):
    f = np.zeros((720, 1280, 3), dtype=np.uint8)
    cv2.rectangle(f, (cx - 4, cy - 1), (cx + 4, cy + 1), (0, 0, 255), -1)
    cv2.rectangle(f, (cx - 1, cy - 4), (cx + 1, cy + 4), (0, 0, 255), -1)
    return f


def test_template_matching_finds_taught_icon_elsewhere():
    import shutil

    from app.vision.multistage import templates_dir

    tdir = templates_dir(SETTINGS)
    try:
        cx, cy = _roi_center()
        teacher = MultiStageMinimapDetector(SETTINGS)
        assert teacher.teach(_cross(cx, cy), cx, cy, "enemy")

        det = MultiStageMinimapDetector(SETTINGS)
        assert det._enemy_tmpl  # template loaded from disk
        rx, ry, rw, rh = SETTINGS.minimap_calibration().roi_pixels(1280, 720)
        nx, ny = rx + rw // 3, ry + rh // 2  # same icon, different place
        frame = _cross(nx, ny)
        dets = []
        for i in range(3):
            dets = det.detect(frame, i, i * 0.5)
        assert any(abs(d.center[0] - nx) < 16 and abs(d.center[1] - ny) < 16 for d in dets)
    finally:
        shutil.rmtree(tdir, ignore_errors=True)


def test_multistage_debug_reports_candidates_with_scores():
    det = MultiStageMinimapDetector(SETTINGS)
    cx, cy = _roi_center()
    rx, ry, items = det.debug_candidates(_frame(cx, cy, (0, 0, 255)))
    assert items
    it = items[0]
    assert "confirmed" in it and "total" in it
    assert set(["color", "shape", "template", "motion"]).issubset(it["scores"])
