"""Learnable-template introspection + the /system/templates API."""
from __future__ import annotations

import shutil

import cv2
import numpy as np

from app.config import get_settings
from app.services import calibration_store
from app.vision import multistage
from app.vision.multistage import MultiStageMinimapDetector, templates_dir

SETTINGS = get_settings()


def _cross(cx=40, cy=40):
    f = np.zeros((80, 80, 3), dtype=np.uint8)
    cv2.rectangle(f, (cx - 4, cy - 1), (cx + 4, cy + 1), (0, 0, 255), -1)
    cv2.rectangle(f, (cx - 1, cy - 4), (cx + 1, cy + 4), (0, 0, 255), -1)
    return f


def test_template_introspection_list_and_delete():
    tdir = templates_dir(SETTINGS)
    try:
        det = MultiStageMinimapDetector(SETTINGS)
        assert det.teach(_cross(), 40, 40, "enemy")
        assert det.teach(_cross(), 40, 40, "false")
        listing = multistage.list_templates(SETTINGS)
        assert len(listing["enemy"]) == 1
        assert len(listing["false"]) == 1

        name = listing["enemy"][0]
        assert multistage.template_path(SETTINGS, "enemy", name) is not None
        # Path-traversal is rejected.
        assert multistage.template_path(SETTINGS, "enemy", "../evil.png") is None

        assert multistage.delete_template(SETTINGS, "enemy", name)
        assert multistage.list_templates(SETTINGS)["enemy"] == []

        removed = multistage.clear_templates(SETTINGS)
        assert removed == 1  # the lone false patch
    finally:
        shutil.rmtree(tdir, ignore_errors=True)


def test_max_templates_cap_limits_loaded_templates():
    tdir = templates_dir(SETTINGS)
    try:
        det = MultiStageMinimapDetector(SETTINGS)
        for _ in range(5):
            det.teach(_cross(), 40, 40, "enemy")
        assert len(multistage.list_templates(SETTINGS)["enemy"]) == 5
        det.max_templates = 2
        det._enemy_tmpl, det._false_tmpl = det._load_templates()
        assert len(det._enemy_tmpl) == 2  # only the newest 2 are matched
    finally:
        shutil.rmtree(tdir, ignore_errors=True)


def test_new_detection_settings_persist_and_apply():
    path = calibration_store._path(SETTINGS)
    try:
        saved = calibration_store.save(
            SETTINGS,
            {
                "detection_template_threshold": 0.7,
                "detection_motion_frames": 3,
                "detection_max_templates": 5,
            },
        )
        assert saved["detection_template_threshold"] == 0.7
        det = MultiStageMinimapDetector(SETTINGS)
        calibration_store.apply_to_multistage(det, SETTINGS)
        assert det.template_threshold == 0.7
        assert det.motion_frames == 3
        assert det._history.maxlen == 3
        assert det.max_templates == 5
    finally:
        if path.exists():
            path.unlink()


def test_templates_api_list_and_clear(client):
    tdir = templates_dir(SETTINGS)
    try:
        det = MultiStageMinimapDetector(SETTINGS)
        det.teach(_cross(), 40, 40, "enemy")
        r = client.get("/api/system/templates")
        assert r.status_code == 200
        body = r.json()
        assert body["enemy_count"] == 1
        name = body["enemy"][0]

        img = client.get(f"/api/system/templates/enemy/{name}")
        assert img.status_code == 200
        assert img.headers["content-type"] == "image/png"

        assert client.get("/api/system/templates/enemy/missing.png").status_code == 404

        cleared = client.delete("/api/system/templates")
        assert cleared.status_code == 200
        assert cleared.json()["deleted"] >= 1
        assert client.get("/api/system/templates").json()["enemy_count"] == 0
    finally:
        shutil.rmtree(tdir, ignore_errors=True)
