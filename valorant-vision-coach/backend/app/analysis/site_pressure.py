"""Site pressure estimation.

Aggregates recent enemy sightings near each bomb site into a single ``[0, 1]``
pressure score, weighted by recency, proximity to the site, and detection
confidence. Multiple sightings of the same agent are de-duplicated to their
strongest contribution so one lingering enemy does not inflate the count.
"""
from __future__ import annotations

import math

from ..config import Settings
from ..models import Team
from ..schemas import SitePressure
from ..vision.maps import GameMap
from .tracks import DetectionLike

# Normalization constant for the soft pressure curve: pressure = 1 - exp(-raw/K).
_PRESSURE_K = 2.0


def estimate_site_pressure(
    detections: list[DetectionLike],
    game_map: GameMap | None,
    at_seconds: float,
    ttl_seconds: float,
    settings: Settings,
) -> list[SitePressure]:
    if game_map is None or not game_map.sites:
        return []

    tau = max(ttl_seconds / 2.0, 1.0)
    radius = settings.site_pressure_radius
    window_start = at_seconds - ttl_seconds

    results: list[SitePressure] = []
    for site in game_map.sites:
        centroid = game_map.site_centroid(site)
        if centroid is None:
            continue
        cx, cy = centroid

        # Best contribution per agent, plus evidence bookkeeping.
        per_agent: dict[str, float] = {}
        per_agent_conf: dict[str, float] = {}
        callouts: set[str] = set()
        n_sightings = 0

        for det in detections:
            if det.team != Team.ENEMY or det.map_x is None or det.map_y is None:
                continue
            if not (window_start <= det.timestamp_seconds <= at_seconds):
                continue
            dist = math.hypot(det.map_x - cx, det.map_y - cy)
            if dist > radius:
                continue
            recency = math.exp(-(at_seconds - det.timestamp_seconds) / tau)
            proximity = max(0.0, 1.0 - dist / radius)
            contribution = recency * proximity * det.confidence
            if contribution <= 0:
                continue
            key = det.agent_name or "Unknown"
            if contribution > per_agent.get(key, 0.0):
                per_agent[key] = contribution
                per_agent_conf[key] = det.confidence
            if det.callout:
                callouts.add(det.callout)
            n_sightings += 1

        raw = sum(per_agent.values())
        pressure = 1.0 - math.exp(-raw / _PRESSURE_K)
        # Recency/proximity-weighted headcount: each contributing agent adds up
        # to 1.0, scaled by how strong their strongest nearby sighting was.
        enemy_count = round(sum(min(1.0, v / 0.5) for v in per_agent.values()), 2)
        confidence = round(min(1.0, n_sightings / 4.0), 3)

        results.append(
            SitePressure(
                site=site,
                pressure=round(pressure, 4),
                enemy_count=enemy_count,
                confidence=confidence,
                contributing_callouts=sorted(callouts),
            )
        )

    results.sort(key=lambda s: s.pressure, reverse=True)
    return results
