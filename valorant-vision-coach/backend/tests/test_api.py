import time

import pytest

from .conftest import make_synthetic_video


def test_health(client):
    resp = client.get("/api/health")
    assert resp.status_code == 200
    assert resp.json()["status"] == "ok"


def test_system_info(client):
    resp = client.get("/api/system/info")
    assert resp.status_code == 200
    body = resp.json()
    assert body["detector_backend"] == "mock"
    assert "ascent" in body["available_maps"]


def test_maps_endpoints(client):
    assert "ascent" in client.get("/api/maps").json()
    detail = client.get("/api/maps/ascent").json()
    assert detail["display_name"] == "Ascent"
    assert any(c["id"] == "a_site" for c in detail["callouts"])
    assert detail["edges"]


def test_unknown_map_404(client):
    assert client.get("/api/maps/nonexistent").status_code == 404


def test_list_matches_is_list(client):
    resp = client.get("/api/matches")
    assert resp.status_code == 200
    assert isinstance(resp.json(), list)


def test_upload_reject_bad_extension(client):
    resp = client.post(
        "/api/matches",
        files={"file": ("notes.txt", b"hello", "text/plain")},
    )
    assert resp.status_code == 400


def test_upload_and_process_flow(client, tmp_path):
    video = tmp_path / "match.mp4"
    if not make_synthetic_video(video, seconds=6, fps=10):
        pytest.skip("No OpenCV video codec available in this environment.")

    with video.open("rb") as fh:
        resp = client.post(
            "/api/matches",
            files={"file": ("match.mp4", fh, "video/mp4")},
            data={"map_name": "ascent"},
        )
    assert resp.status_code == 201
    match_id = resp.json()["id"]

    # The pipeline runs in a background worker; poll for completion.
    deadline = time.time() + 60
    status = None
    while time.time() < deadline:
        status = client.get(f"/api/matches/{match_id}").json()["status"]
        if status in {"completed", "failed"}:
            break
        time.sleep(0.5)
    assert status == "completed"

    snapshot = client.get(f"/api/matches/{match_id}/analysis/snapshot?ttl=15").json()
    assert snapshot["match_id"] == match_id
    assert snapshot["map_name"] == "ascent"
    # Analysis produced at least one of the views.
    assert snapshot["last_known"] or snapshot["site_pressure"] or snapshot["rotations"]
