"""Pydantic request/response schemas (API contract)."""
from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from .models import DetectionSource, ProcessingStatus, Team


class ORMModel(BaseModel):
    model_config = ConfigDict(from_attributes=True)


# ---- Matches -------------------------------------------------------------
class MatchSummary(ORMModel):
    id: int
    filename: str
    map_name: str | None
    status: ProcessingStatus
    progress: float
    duration_seconds: float | None
    detections_count: int
    created_at: datetime
    processed_at: datetime | None


class MatchDetail(MatchSummary):
    stored_path: str
    status_detail: str | None
    fps: float | None
    frame_count: int | None


class RoundOut(ORMModel):
    id: int
    round_number: int
    start_seconds: float
    end_seconds: float | None
    score_text: str | None
    spike_planted: bool


class DetectionOut(ORMModel):
    id: int
    timestamp_seconds: float
    frame_number: int
    agent_name: str | None
    team: Team
    source: DetectionSource
    confidence: float
    map_x: float | None
    map_y: float | None
    callout: str | None


class KillfeedOut(ORMModel):
    id: int
    timestamp_seconds: float
    killer: str | None
    victim: str | None
    weapon: str | None
    headshot: bool
    killer_team: Team


# ---- Analysis ------------------------------------------------------------
class LastKnownPosition(BaseModel):
    agent_name: str | None
    map_x: float | None
    map_y: float | None
    callout: str | None
    last_seen_seconds: float
    age_seconds: float = Field(description="Seconds elapsed since the sighting at query time.")
    confidence: float
    source: DetectionSource
    stale: bool = Field(description="True when age exceeds the requested TTL.")


class RotationCandidate(BaseModel):
    from_callout: str | None
    to_callout: str
    to_x: float
    to_y: float
    distance_norm: float
    eta_seconds: float = Field(description="Estimated travel time from last sighting location.")
    likelihood: float = Field(description="Relative likelihood in [0, 1].")
    leads_to_site: str | None


class EnemyRotation(BaseModel):
    agent_name: str | None
    origin_callout: str | None
    age_seconds: float
    candidates: list[RotationCandidate]


class SitePressure(BaseModel):
    site: str
    pressure: float = Field(description="Normalized pressure in [0, 1].")
    enemy_count: float = Field(description="Recency-weighted count of enemies near the site.")
    confidence: float
    contributing_callouts: list[str]


class AnalysisSnapshot(BaseModel):
    """Everything the dashboard needs for a single moment in the VOD."""

    match_id: int
    map_name: str | None
    at_seconds: float
    ttl_seconds: float
    last_known: list[LastKnownPosition]
    rotations: list[EnemyRotation]
    site_pressure: list[SitePressure]


# ---- Tendencies (scouting report) ---------------------------------------
class SiteFrequency(BaseModel):
    site: str
    rounds: int = Field(description="Number of rounds the enemy committed to this site.")
    share: float = Field(description="Fraction of analyzed rounds in [0, 1].")


class AgentSiteShare(BaseModel):
    site: str
    share: float


class AgentSitePreference(BaseModel):
    agent_name: str | None
    rounds_seen: int
    sites: list[AgentSiteShare]


class TendencyReport(BaseModel):
    """Aggregated enemy site tendencies across the analyzed rounds.

    A *post-match* scouting report (where did they tend to go, which site does
    each agent favor) — derived only from observed sightings, for study and
    preparation. It is not a live in-match overlay.
    """

    match_id: int
    map_name: str | None
    rounds_analyzed: int
    site_frequency: list[SiteFrequency]
    agent_site_preference: list[AgentSitePreference]


# ---- Maps ----------------------------------------------------------------
class CalloutOut(BaseModel):
    id: str
    name: str
    x: float
    y: float
    site: str | None


class MapMeta(BaseModel):
    name: str
    display_name: str
    image: str | None
    sites: list[str]
    callouts: list[CalloutOut]
    edges: list[list[str]]


# ---- System --------------------------------------------------------------
class HealthOut(BaseModel):
    status: str
    version: str


class SystemInfo(BaseModel):
    app_name: str
    version: str
    environment: str
    detector_backend: str
    detector_ready: bool
    ocr_backend: str
    ocr_ready: bool
    available_maps: list[str]
