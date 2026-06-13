"""Tactical analysis endpoints (last-known, rotations, site pressure, snapshot)."""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from ...analysis.engine import build_snapshot
from ...analysis.last_known_position import to_last_known
from ...analysis.rotation import estimate_rotations
from ...analysis.site_pressure import estimate_site_pressure
from ...analysis.tendencies import build_tendencies
from ...analysis.tracks import build_enemy_tracks
from ...config import Settings
from ...schemas import (
    AnalysisSnapshot,
    EnemyRotation,
    LastKnownPosition,
    SitePressure,
    TendencyReport,
)
from ...services import match_service
from ...vision.maps import load_map
from ..deps import get_session, get_settings_dep

router = APIRouter(prefix="/matches/{match_id}/analysis", tags=["analysis"])

# A very large TTL used to find truly-last sightings before applying the
# requested staleness threshold for display.
_UNBOUNDED_TTL = 1e9


def _resolve_at(match, at: float | None) -> float:
    if at is not None:
        return max(0.0, at)
    return match.duration_seconds or 0.0


def _window(session: Session, match_id: int, at: float, ttl: float):
    lookback = max(ttl * 2.0, 60.0)
    return match_service.get_detections_window(session, match_id, at, lookback)


@router.get("/snapshot", response_model=AnalysisSnapshot)
def snapshot(
    match_id: int,
    at: float | None = Query(default=None, description="Match time in seconds."),
    ttl: float | None = Query(default=None, description="Sighting TTL in seconds."),
    session: Session = Depends(get_session),
    settings: Settings = Depends(get_settings_dep),
) -> AnalysisSnapshot:
    match = _require_match(session, match_id)
    at_seconds = _resolve_at(match, at)
    ttl_seconds = ttl if ttl is not None else settings.sighting_ttl_seconds
    detections = _window(session, match_id, at_seconds, ttl_seconds)
    return build_snapshot(detections, match_id, match.map_name, at_seconds, ttl_seconds, settings)


@router.get("/last-known", response_model=list[LastKnownPosition])
def last_known(
    match_id: int,
    at: float | None = None,
    ttl: float | None = None,
    include_stale: bool = False,
    session: Session = Depends(get_session),
    settings: Settings = Depends(get_settings_dep),
) -> list[LastKnownPosition]:
    match = _require_match(session, match_id)
    at_seconds = _resolve_at(match, at)
    ttl_seconds = ttl if ttl is not None else settings.sighting_ttl_seconds
    if include_stale:
        # Look back across the whole match to surface even old sightings.
        detections = match_service.get_detections(session, match_id, end=at_seconds)
        tracks = build_enemy_tracks(detections, at_seconds, _UNBOUNDED_TTL)
    else:
        detections = _window(session, match_id, at_seconds, ttl_seconds)
        tracks = build_enemy_tracks(detections, at_seconds, ttl_seconds)
    return to_last_known(tracks, at_seconds, ttl_seconds)


@router.get("/rotations", response_model=list[EnemyRotation])
def rotations(
    match_id: int,
    at: float | None = None,
    ttl: float | None = None,
    session: Session = Depends(get_session),
    settings: Settings = Depends(get_settings_dep),
) -> list[EnemyRotation]:
    match = _require_match(session, match_id)
    at_seconds = _resolve_at(match, at)
    ttl_seconds = ttl if ttl is not None else settings.sighting_ttl_seconds
    detections = _window(session, match_id, at_seconds, ttl_seconds)
    tracks = build_enemy_tracks(detections, at_seconds, ttl_seconds)
    return estimate_rotations(tracks, load_map(match.map_name), at_seconds, settings)


@router.get("/site-pressure", response_model=list[SitePressure])
def site_pressure(
    match_id: int,
    at: float | None = None,
    ttl: float | None = None,
    session: Session = Depends(get_session),
    settings: Settings = Depends(get_settings_dep),
) -> list[SitePressure]:
    match = _require_match(session, match_id)
    at_seconds = _resolve_at(match, at)
    ttl_seconds = ttl if ttl is not None else settings.sighting_ttl_seconds
    detections = _window(session, match_id, at_seconds, ttl_seconds)
    return estimate_site_pressure(
        detections, load_map(match.map_name), at_seconds, ttl_seconds, settings
    )


@router.get("/tendencies", response_model=TendencyReport)
def tendencies(
    match_id: int,
    session: Session = Depends(get_session),
) -> TendencyReport:
    """Post-match scouting report: enemy site tendencies across all rounds."""
    match = _require_match(session, match_id)
    detections = match_service.get_detections(session, match_id)
    return build_tendencies(detections, match_id, match.map_name, load_map(match.map_name))


def _require_match(session: Session, match_id: int):
    match = match_service.get_match(session, match_id)
    if match is None:
        raise HTTPException(status_code=404, detail="Match not found")
    return match
