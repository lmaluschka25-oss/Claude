from dataclasses import dataclass

from app.analysis.last_known_position import to_last_known
from app.analysis.rotation import estimate_rotations
from app.analysis.prediction import predict_next_round
from app.analysis.site_pressure import estimate_site_pressure
from app.analysis.tendencies import build_tendencies
from app.analysis.tracks import build_enemy_tracks
from app.config import get_settings
from app.models import DetectionSource, Team
from app.vision.maps import load_map


@dataclass
class D:
    timestamp_seconds: float
    map_x: float | None
    map_y: float | None
    agent_name: str | None = "Jett"
    team: Team = Team.ENEMY
    source: DetectionSource = DetectionSource.MINIMAP
    confidence: float = 0.8
    callout: str | None = None
    round_id: int | None = None


SETTINGS = get_settings()


def test_build_tracks_groups_and_drops_stale():
    dets = [
        D(0.0, 0.34, 0.56, agent_name="Jett"),
        D(5.0, 0.30, 0.40, agent_name="Jett"),
        D(1.0, 0.80, 0.24, agent_name="Sage"),  # last seen long ago
    ]
    tracks = build_enemy_tracks(dets, at_seconds=10.0, ttl_seconds=8.0)
    by_agent = {t.agent_name: t for t in tracks}
    assert "Jett" in by_agent  # last seen at t=5, age 5 < ttl 8
    assert "Sage" not in by_agent  # last seen at t=1, age 9 > ttl 8
    # Heading derived from the two Jett sightings (moving up-left).
    assert by_agent["Jett"].previous is not None
    assert by_agent["Jett"].heading is not None


def test_last_known_flags_age_and_stale():
    dets = [D(2.0, 0.5, 0.5, agent_name="Omen")]
    rows = to_last_known(build_enemy_tracks(dets, 10.0, 100.0), at_seconds=10.0, ttl_seconds=5.0)
    assert len(rows) == 1
    row = rows[0]
    assert row.agent_name == "Omen"
    assert abs(row.age_seconds - 8.0) < 1e-6
    assert row.stale is True


def test_rotation_candidates_normalized_and_reach_objective():
    game_map = load_map("ascent")
    dets = [
        D(0.0, 0.40, 0.62, agent_name="Jett"),  # near A Main / A Lobby
        D(2.0, 0.34, 0.56, agent_name="Jett"),
    ]
    tracks = build_enemy_tracks(dets, at_seconds=8.0, ttl_seconds=30.0)
    rotations = estimate_rotations(tracks, game_map, at_seconds=8.0, settings=SETTINGS)
    assert rotations
    cands = rotations[0].candidates
    assert cands
    # Likelihoods are a normalized distribution.
    assert abs(sum(c.likelihood for c in cands) - 1.0) < 1e-3
    # ETA grows with distance.
    assert all(c.eta_seconds >= 0 for c in cands)


def test_site_pressure_present_when_enemies_near_site():
    game_map = load_map("ascent")
    dets = [
        D(9.0, 0.80, 0.24, agent_name="Killjoy"),  # on B site
        D(9.5, 0.79, 0.26, agent_name="Cypher"),
    ]
    pressure = {p.site: p for p in estimate_site_pressure(dets, game_map, 10.0, 12.0, SETTINGS)}
    assert pressure["B"].pressure > 0.0
    assert pressure["A"].pressure == 0.0
    assert pressure["B"].enemy_count >= 1.0


def test_allies_do_not_create_pressure():
    game_map = load_map("ascent")
    dets = [D(9.0, 0.80, 0.24, agent_name="Sage", team=Team.ALLY)]
    pressure = {p.site: p for p in estimate_site_pressure(dets, game_map, 10.0, 12.0, SETTINGS)}
    assert pressure["B"].pressure == 0.0


def test_tendencies_site_frequency_and_agent_preference():
    game_map = load_map("ascent")  # A ~ (0.20,0.22), B ~ (0.80,0.24)
    dets = [
        D(1.0, 0.80, 0.24, agent_name="Killjoy", round_id=1),
        D(2.0, 0.78, 0.26, agent_name="Jett", round_id=1),
        D(31.0, 0.80, 0.24, agent_name="Killjoy", round_id=2),
        D(61.0, 0.20, 0.22, agent_name="Jett", round_id=3),
        D(62.0, 0.22, 0.20, agent_name="Killjoy", round_id=3),
    ]
    rep = build_tendencies(dets, 1, "ascent", game_map)
    assert rep.rounds_analyzed == 3
    freq = {s.site: s for s in rep.site_frequency}
    assert freq["B"].rounds == 2 and abs(freq["B"].share - 0.667) < 0.01
    assert freq["A"].rounds == 1
    jett = next(a for a in rep.agent_site_preference if a.agent_name == "Jett")
    assert jett.rounds_seen == 2  # seen in rounds 1 (B) and 3 (A)


@dataclass
class R:
    id: int
    round_number: int


def test_prediction_next_round():
    game_map = load_map("ascent")
    rounds = [R(1, 1), R(2, 2), R(3, 3), R(4, 4)]
    dets = [
        D(1.0, 0.80, 0.24, agent_name="Killjoy", round_id=1),
        D(2.0, 0.80, 0.24, agent_name="Jett", round_id=1),
        D(31.0, 0.80, 0.24, agent_name="Killjoy", round_id=2),
        D(61.0, 0.20, 0.22, agent_name="Jett", round_id=3),
        D(91.0, 0.80, 0.24, agent_name="Killjoy", round_id=4),
    ]
    pred = predict_next_round(dets, rounds, 1, "ascent", game_map, SETTINGS)
    assert pred.rounds_analyzed == 4
    assert pred.per_round_commitment == ["B", "B", "A", "B"]
    assert pred.predicted_sites[0].site == "B"  # base + momentum favour B
    assert abs(sum(s.probability for s in pred.predicted_sites) - 1.0) < 1e-2
    assert 0.0 < pred.confidence <= 1.0
    assert pred.last_committed_site == "B"
    assert pred.top_factor
