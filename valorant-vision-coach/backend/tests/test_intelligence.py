from app.analysis.intelligence import _predict, assign_site, build_match_intelligence
from app.config import get_settings
from app.database import session_scope
from app.models import (
    Detection,
    DetectionSource,
    Match,
    ProcessingStatus,
    Round,
    Side,
    Team,
)
from app.vision.maps import load_map

SETTINGS = get_settings()


def test_assign_site():
    gm = load_map("ascent")
    assert assign_site(gm, 0.80, 0.24) == "B"
    assert assign_site(gm, 0.20, 0.22) == "A"


def test_predict_is_distribution_and_favours_majority():
    sites = ["A", "B", "MID"]
    p = _predict(["A", "A", "B", "A"], sites)
    assert abs(sum(p.values()) - 1.0) < 1e-6
    assert max(p, key=p.get) == "A"


def _add_round(session, match, n, xy, committed):
    r = Round(
        match_id=match.id, round_number=n, filename=f"r{n}.mp4", stored_path="/x",
        status=ProcessingStatus.COMPLETED, committed_site=committed, economy="Full Buy",
        map_name="ascent",
    )
    session.add(r)
    session.flush()
    for i in range(3):
        session.add(Detection(
            match_id=match.id, round_id=r.id, timestamp_seconds=float(i), frame_number=i,
            agent_name="Killjoy", team=Team.ENEMY, source=DetectionSource.MINIMAP,
            confidence=0.8, map_x=xy[0], map_y=xy[1], callout=None,
        ))


def test_build_intelligence_learns_and_recommends_weak_site():
    with session_scope() as session:
        match = Match(name="T", map_name="ascent", side=Side.ATTACK)
        session.add(match)
        session.flush()
        _add_round(session, match, 1, (0.80, 0.24), "B")  # B heavy
        _add_round(session, match, 2, (0.80, 0.24), "B")
        _add_round(session, match, 3, (0.20, 0.22), "A")
        _add_round(session, match, 4, (0.50, 0.50), "MID")
        _add_round(session, match, 5, (0.80, 0.24), "B")
        session.flush()

        intel = build_match_intelligence(session, match, SETTINGS)
        assert intel.match_memory.rounds_analyzed == 5
        assert abs(sum(p.probability for p in intel.position_probabilities) - 1.0) < 1e-2
        # B is the heavy site → recommendation should avoid B.
        assert intel.recommendation.best_site != "B"
        assert intel.recommendation.success_probability > 0.5
        # Killjoy anchors B pattern should surface.
        assert any("Killjoy" in p.text for p in intel.patterns)
        # Confidence rises with rounds (5 rounds > the 1-round baseline).
        assert intel.match_memory.confidence > 0.32
        assert intel.analysis_log and intel.analysis_log[-1].step == 7
