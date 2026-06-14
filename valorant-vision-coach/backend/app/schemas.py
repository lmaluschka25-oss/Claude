"""Pydantic request/response schemas (API contract)."""
from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from .models import DetectionSource, ProcessingStatus, Side, Team, UtilityKind


class ORMModel(BaseModel):
    model_config = ConfigDict(from_attributes=True)


# ---- Matches & rounds ----------------------------------------------------
class MatchCreate(BaseModel):
    name: str | None = None
    map_name: str | None = None
    side: Side = Side.UNKNOWN


class MatchUpdate(BaseModel):
    name: str | None = None
    map_name: str | None = None
    side: Side | None = None


class CalibrationSettings(BaseModel):
    x_frac: float | None = None
    y_frac: float | None = None
    w_frac: float | None = None
    h_frac: float | None = None
    rotation: int | None = None
    flip_x: bool | None = None
    color_mode: str | None = None
    hue_min: int | None = None
    hue_max: int | None = None
    sat_min: int | None = None
    val_min: int | None = None
    min_area: float | None = None
    max_area: float | None = None
    analysis_interval: float | None = None
    confidence_threshold: float | None = None
    pattern_weight: float | None = None
    memory_weight: float | None = None
    recommendation_min_confidence: float | None = None
    timeline_detail: int | None = None
    detection_confirm_threshold: float | None = None


class MatchSummary(ORMModel):
    id: int
    name: str
    map_name: str | None
    side: Side
    created_at: datetime
    updated_at: datetime
    rounds_count: int = 0
    completed_rounds: int = 0


class RoundOut(ORMModel):
    id: int
    match_id: int
    round_number: int
    filename: str
    status: ProcessingStatus
    status_detail: str | None
    progress: float
    map_name: str | None
    map_confidence: float
    side: Side
    side_confidence: float
    score_text: str | None
    economy: str | None
    spike_planted: bool
    duration_seconds: float | None
    detections_count: int
    committed_site: str | None
    created_at: datetime
    processed_at: datetime | None


class MatchDetail(MatchSummary):
    rounds: list[RoundOut] = Field(default_factory=list)


class DetectionOut(ORMModel):
    id: int
    round_id: int
    timestamp_seconds: float
    agent_name: str | None
    team: Team
    source: DetectionSource
    confidence: float
    map_x: float | None
    map_y: float | None
    callout: str | None


class UtilityOut(ORMModel):
    id: int
    timestamp_seconds: float
    kind: UtilityKind
    agent_name: str | None
    callout: str | None
    map_x: float | None
    map_y: float | None
    confidence: float


class KillfeedOut(ORMModel):
    id: int
    timestamp_seconds: float
    killer: str | None
    victim: str | None
    weapon: str | None
    headshot: bool
    killer_team: Team


# ---- Intelligence payload (drives the dashboard) -------------------------
class MarkerOut(BaseModel):
    team: Team
    agent_name: str | None
    map_x: float
    map_y: float
    callout: str | None
    dead: bool = False
    kind: str = "player"  # "player" | "self" | "spike" | utility kind


class DetectedInfo(BaseModel):
    map_name: str | None
    map_confidence: float
    side: Side
    side_confidence: float
    round_number: int
    score_text: str | None
    round_time: str | None
    players_alive_ally: int | None
    players_alive_enemy: int | None
    spike_planted: bool
    economy: str | None


class TimelineEvent(BaseModel):
    timestamp_seconds: float
    kind: str  # move | spotted | smoke | recon | turret | rotation | kill | info
    label: str
    detail: str | None = None


class PositionProbability(BaseModel):
    site: str
    probability: float


class PatternItem(BaseModel):
    kind: str  # presence | rotation | anchor | aggression
    text: str
    detail: str | None = None
    confidence: float


class HeatCell(BaseModel):
    x: float
    y: float
    weight: float


class MatchMemory(BaseModel):
    rounds_analyzed: int
    site_presence: dict[str, float]  # site -> share [0,1]
    avg_rotation_time: float | None
    common_utility: str | None
    enemy_economy: str | None
    confidence: float


class EnemyProfile(BaseModel):
    agent_name: str | None
    note: str
    favored_site: str | None
    site_share: float
    rotation_tendency: str | None
    rounds_seen: int


class WeaponEconomy(BaseModel):
    enemy_label: str | None
    enemy_tier: str  # eco | force | full | unknown
    ally_label: str | None
    ally_tier: str


class DetectedPositionLive(BaseModel):
    agent_name: str | None
    team: Team
    callout: str | None
    age_seconds: float


class Recommendation(BaseModel):
    best_site: str | None
    mode: str = "attack"  # "attack" (hit weakest) | "defense" (stack most-hit)
    action_label: str = "Attack"  # verb shown in the hero ("Attack" / "Stack")
    success_probability: float
    confidence: float
    confidence_label: str
    reasons: list[str]
    suggested_play: list[str]


class AnalysisLogStep(BaseModel):
    step: int
    title: str
    detail: str
    status: str = "done"  # done | skipped | warning


class DetectionStats(BaseModel):
    """Feedback on whether the current detection settings are working."""

    detector_backend: str
    analysis_interval: float
    frames_analyzed: int
    enemy_markers: int
    avg_confidence: float
    status: str  # ok | low | none
    message: str


class MatchIntelligence(BaseModel):
    """Everything the analysis dashboard needs for the selected match."""

    match: MatchSummary
    current_round: RoundOut | None
    detected_info: DetectedInfo | None
    detection_stats: DetectionStats | None
    minimap_markers: list[MarkerOut]
    utilities: list[UtilityOut]
    timeline: list[TimelineEvent]
    detected_positions: list[DetectedPositionLive]
    position_probabilities: list[PositionProbability]
    patterns: list[PatternItem]
    heatmap: list[HeatCell]
    match_memory: MatchMemory
    enemy_profiles: list[EnemyProfile]
    weapon_economy: WeaponEconomy
    recommendation: Recommendation
    learnings: list[str]
    analysis_log: list[AnalysisLogStep]


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
