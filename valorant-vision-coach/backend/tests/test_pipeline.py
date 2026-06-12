import pytest

from app.analysis.engine import build_snapshot
from app.config import get_settings
from app.database import session_scope
from app.models import ProcessingStatus, Team
from app.services import match_service, pipeline

from .conftest import make_synthetic_video


def test_pipeline_processes_synthetic_video(tmp_path):
    video = tmp_path / "match.mp4"
    if not make_synthetic_video(video, seconds=8, fps=10):
        pytest.skip("No OpenCV video codec available in this environment.")

    with session_scope() as s:
        match = match_service.create_match(
            s, filename="match.mp4", stored_path=str(video), map_name="ascent"
        )
        match_id = match.id

    pipeline.run(match_id)

    with session_scope() as s:
        match = match_service.get_match(s, match_id)
        assert match.status == ProcessingStatus.COMPLETED
        assert match.detections_count > 0
        assert match.fps and match.duration_seconds

        detections = match_service.get_detections(s, match_id)
        enemy_located = [d for d in detections if d.team == Team.ENEMY and d.map_x is not None]
        assert enemy_located, "Expected located enemy sightings from the mock detector."
        # Callouts are resolved against the map.
        assert any(d.callout for d in enemy_located)

        snapshot = build_snapshot(
            detections,
            match_id,
            match.map_name,
            at_seconds=match.duration_seconds,
            ttl_seconds=15.0,
            settings=get_settings(),
        )
        assert snapshot.last_known or snapshot.site_pressure
