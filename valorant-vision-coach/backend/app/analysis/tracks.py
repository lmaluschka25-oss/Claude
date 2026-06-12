"""Shared primitives: turn a stream of detections into per-enemy tracks.

A "track" collapses many sightings of one enemy into the information a coach
actually reasons about at a moment ``T``: where they were last seen, how long
ago, and which way they were heading. Rotation and site-pressure analysis both
build on these.
"""
from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Protocol

from ..models import DetectionSource, Team


class DetectionLike(Protocol):
    timestamp_seconds: float
    agent_name: str | None
    team: Team
    source: DetectionSource
    confidence: float
    map_x: float | None
    map_y: float | None
    callout: str | None


@dataclass
class Sighting:
    timestamp: float
    x: float
    y: float
    callout: str | None
    confidence: float
    source: DetectionSource


@dataclass
class EnemyTrack:
    agent_name: str | None
    last: Sighting
    previous: Sighting | None  # second-most-recent located sighting, for heading

    @property
    def heading(self) -> tuple[float, float] | None:
        """Unit movement vector from ``previous`` to ``last``, if derivable."""
        if self.previous is None:
            return None
        dx = self.last.x - self.previous.x
        dy = self.last.y - self.previous.y
        norm = math.hypot(dx, dy)
        if norm < 1e-4:
            return None
        return dx / norm, dy / norm

    def age(self, at_seconds: float) -> float:
        return max(0.0, at_seconds - self.last.timestamp)


def _agent_key(agent: str | None) -> str:
    return agent or "Unknown"


def build_enemy_tracks(
    detections: list[DetectionLike], at_seconds: float, ttl_seconds: float
) -> list[EnemyTrack]:
    """Build one track per enemy agent from located sightings up to ``at_seconds``.

    Only enemy detections with resolved map coordinates and a timestamp at or
    before ``at_seconds`` are considered. Tracks whose latest sighting is older
    than ``ttl_seconds`` are dropped (the "remove old sightings" rule).
    """
    grouped: dict[str, list[Sighting]] = {}
    for det in detections:
        if det.team != Team.ENEMY:
            continue
        if det.map_x is None or det.map_y is None:
            continue
        if det.timestamp_seconds > at_seconds:
            continue
        grouped.setdefault(_agent_key(det.agent_name), []).append(
            Sighting(
                timestamp=det.timestamp_seconds,
                x=det.map_x,
                y=det.map_y,
                callout=det.callout,
                confidence=det.confidence,
                source=det.source,
            )
        )

    tracks: list[EnemyTrack] = []
    for agent, sightings in grouped.items():
        sightings.sort(key=lambda s: s.timestamp)
        last = sightings[-1]
        if at_seconds - last.timestamp > ttl_seconds:
            continue
        previous = sightings[-2] if len(sightings) >= 2 else None
        display_agent = None if agent == "Unknown" else agent
        tracks.append(EnemyTrack(agent_name=display_agent, last=last, previous=previous))

    tracks.sort(key=lambda t: t.last.timestamp, reverse=True)
    return tracks
