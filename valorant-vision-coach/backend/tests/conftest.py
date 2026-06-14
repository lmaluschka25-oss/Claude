"""Test configuration.

Environment is configured *before* the application is imported so the cached
settings singleton picks up the test database, temp upload dir, and the mock
detector. No ML dependencies, GPU, or real footage are required.
"""
from __future__ import annotations

import os
import tempfile
from pathlib import Path

import pytest

_BACKEND_DIR = Path(__file__).resolve().parent.parent
_TMP = Path(tempfile.mkdtemp(prefix="vvc-test-"))

os.environ.update(
    VVC_DETECTOR_BACKEND="mock",
    VVC_OCR_BACKEND="off",
    VVC_FRAME_SAMPLE_STRIDE="3",
    VVC_DATABASE_URL=f"sqlite:///{(_TMP / 'test.db').as_posix()}",
    VVC_UPLOAD_DIR=str(_TMP / "uploads"),
    VVC_MODELS_DIR=str(_TMP / "models"),
    VVC_MAPS_DIR=str(_BACKEND_DIR / "data" / "maps"),
)

# Imported after env is set.
from app.database import init_db  # noqa: E402


@pytest.fixture(scope="session", autouse=True)
def _setup_db():
    init_db()
    yield


@pytest.fixture
def client():
    from fastapi.testclient import TestClient

    from app.main import app

    with TestClient(app) as c:
        yield c


def make_synthetic_video(path: Path, seconds: int = 6, fps: int = 10, size=(1280, 720)) -> bool:
    """Write a short decodable video. Returns False if no codec is available."""
    import cv2
    import numpy as np

    w, h = size
    for fourcc_name, suffix in (("mp4v", ".mp4"), ("MJPG", ".avi")):
        target = path.with_suffix(suffix)
        writer = cv2.VideoWriter(str(target), cv2.VideoWriter_fourcc(*fourcc_name), fps, (w, h))
        if not writer.isOpened():
            writer.release()
            continue
        frame = np.zeros((h, w, 3), dtype=np.uint8)
        for _ in range(seconds * fps):
            writer.write(frame)
        writer.release()
        if target.exists() and target.stat().st_size > 0:
            if target != path:
                target.replace(path)
            return True
    return False
