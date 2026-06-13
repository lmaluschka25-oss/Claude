import time

import pytest

from .conftest import make_synthetic_video


def test_health(client):
    assert client.get("/api/health").json()["status"] == "ok"


def test_system_info(client):
    body = client.get("/api/system/info").json()
    assert body["detector_backend"] == "mock"
    assert "ascent" in body["available_maps"]


def test_maps_endpoints(client):
    assert "ascent" in client.get("/api/maps").json()
    detail = client.get("/api/maps/ascent").json()
    assert detail["display_name"] == "Ascent"


def test_match_crud(client):
    resp = client.post("/api/matches", json={"map_name": "ascent", "side": "attack"})
    assert resp.status_code == 201
    match = resp.json()
    assert match["map_name"] == "ascent"
    mid = match["id"]
    assert any(m["id"] == mid for m in client.get("/api/matches").json())
    assert client.get(f"/api/matches/{mid}").json()["id"] == mid


def test_round_upload_and_intelligence(client, tmp_path):
    mid = client.post("/api/matches", json={"map_name": "ascent", "side": "attack"}).json()["id"]
    video = tmp_path / "r.mp4"
    if not make_synthetic_video(video, seconds=6, fps=10):
        pytest.skip("No OpenCV video codec available.")

    with video.open("rb") as fh:
        up = client.post(f"/api/matches/{mid}/rounds", files={"file": ("r.mp4", fh, "video/mp4")})
    assert up.status_code == 201
    round_id = up.json()["id"]

    deadline = time.time() + 60
    status = None
    while time.time() < deadline:
        status = client.get(f"/api/rounds/{round_id}").json()["status"]
        if status in {"completed", "failed"}:
            break
        time.sleep(0.5)
    assert status == "completed"

    intel = client.get(f"/api/matches/{mid}/intelligence").json()
    assert intel["match"]["id"] == mid
    assert intel["match_memory"]["rounds_analyzed"] >= 1
    assert intel["recommendation"]["best_site"] is not None
    assert intel["analysis_log"]
    # Round media + detections endpoints respond.
    assert client.get(f"/api/rounds/{round_id}/detections").status_code == 200


def test_reject_bad_upload(client):
    mid = client.post("/api/matches", json={"map_name": "bind"}).json()["id"]
    resp = client.post(
        f"/api/matches/{mid}/rounds", files={"file": ("notes.txt", b"x", "text/plain")}
    )
    assert resp.status_code == 400
