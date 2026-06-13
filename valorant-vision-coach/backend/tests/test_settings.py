from app.analysis.intelligence import _predict
from app.config import get_settings
from app.services import calibration_store
from app.vision.detector import MinimapColorDetector

SETTINGS = get_settings()


def test_calibration_store_persists_and_applies():
    path = calibration_store._path(SETTINGS)
    try:
        saved = calibration_store.save(
            SETTINGS, {"analysis_interval": 1.0, "memory_weight": 0.6, "sat_min": 205}
        )
        assert saved["analysis_interval"] == 1.0
        # Survives a fresh load (i.e. would survive a restart).
        loaded = calibration_store.load(SETTINGS)
        assert loaded["analysis_interval"] == 1.0
        assert loaded["memory_weight"] == 0.6
        assert loaded["sat_min"] == 205
        # And is actually applied to the detector.
        det = MinimapColorDetector(SETTINGS)
        calibration_store.apply_to_detector(det, SETTINGS)
        assert det.sat_min == 205
    finally:
        if path.exists():
            path.unlink()  # keep other tests on defaults


def test_prediction_weights_change_the_distribution():
    sites = ["A", "B", "MID"]
    seq = ["A", "A", "A", "B", "B"]  # base favours A, momentum favours B
    p_memory = _predict(seq, sites, 0.9, 0.05, 0.05)
    p_recent = _predict(seq, sites, 0.05, 0.9, 0.05)
    assert abs(sum(p_memory.values()) - 1) < 1e-6
    assert abs(sum(p_recent.values()) - 1) < 1e-6
    # Memory-weighted leans A; recent-weighted leans more to B than memory does.
    assert p_memory["A"] > p_recent["A"]
    assert p_recent["B"] > p_memory["B"]
