"""Assembles a complete :class:`AnalysisSnapshot` for a moment in a match."""
from __future__ import annotations

from ..config import Settings
from ..schemas import AnalysisSnapshot
from ..vision.maps import GameMap, load_map
from .last_known_position import to_last_known
from .rotation import estimate_rotations
from .site_pressure import estimate_site_pressure
from .tracks import DetectionLike, build_enemy_tracks


def build_snapshot(
    detections: list[DetectionLike],
    match_id: int,
    map_name: str | None,
    at_seconds: float,
    ttl_seconds: float,
    settings: Settings,
) -> AnalysisSnapshot:
    """Compute last-known positions, rotations, and site pressure at ``at_seconds``."""
    game_map: GameMap | None = load_map(map_name) if map_name else None

    tracks = build_enemy_tracks(detections, at_seconds, ttl_seconds)
    last_known = to_last_known(tracks, at_seconds, ttl_seconds)
    rotations = estimate_rotations(tracks, game_map, at_seconds, settings)
    site_pressure = estimate_site_pressure(
        detections, game_map, at_seconds, ttl_seconds, settings
    )

    return AnalysisSnapshot(
        match_id=match_id,
        map_name=map_name,
        at_seconds=at_seconds,
        ttl_seconds=ttl_seconds,
        last_known=last_known,
        rotations=rotations,
        site_pressure=site_pressure,
    )
