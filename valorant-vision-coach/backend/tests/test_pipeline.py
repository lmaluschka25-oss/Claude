import pytest

from app.analysis.intelligence import build_match_intelligence
from app.config import get_settings
from app.database import session_scope
from app.models import Match, ProcessingStatus, Round, Side, Team
from app.services import match_service, pipeline

from .conftest import make_synthetic_video


def test_pipeline_processes_round_and_builds_intelligence(tmp_path):
    video = tmp_path / "r.mp4"
    if not make_synthetic_video(video, seconds=8, fps=10):
        pytest.skip("No OpenCV video codec available.")

    with session_scope() as s:
        match = match_service.create_match(s, name="T", map_name="ascent", side=Side.ATTACK)
        rnd = match_service.create_round(
            s, match_id=match.id, filename="r.mp4", stored_path=str(video), map_name="ascent"
        )
        round_id, match_id = rnd.id, match.id

    pipeline.run(round_id)

    with session_scope() as s:
        rnd = s.get(Round, round_id)
        assert rnd.status == ProcessingStatus.COMPLETED
        assert rnd.detections_count > 0
        assert rnd.committed_site in ("A", "B", "MID")
        enemies = [d for d in rnd.detections if d.team == Team.ENEMY and d.map_x is not None]
        assert enemies
        # The mock backend also synthesizes utilities + killfeed + metadata.
        assert rnd.utilities
        assert rnd.killfeed
        assert rnd.score_text and rnd.economy

        intel = build_match_intelligence(s, s.get(Match, match_id), get_settings())
        assert intel.match_memory.rounds_analyzed == 1
        assert intel.detected_info is not None
        assert intel.minimap_markers
        assert intel.recommendation is not None
