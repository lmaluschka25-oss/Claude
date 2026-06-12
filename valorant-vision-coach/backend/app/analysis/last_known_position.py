"""Last Known Enemy Position view.

Surfaces, for each enemy, where they were last seen and how long ago — with a
configurable TTL after which a sighting is considered stale and dropped.
"""
from __future__ import annotations

from ..schemas import LastKnownPosition
from .tracks import EnemyTrack


def to_last_known(
    tracks: list[EnemyTrack], at_seconds: float, ttl_seconds: float
) -> list[LastKnownPosition]:
    """Convert enemy tracks into last-known-position rows for the dashboard."""
    rows: list[LastKnownPosition] = []
    for track in tracks:
        age = track.age(at_seconds)
        rows.append(
            LastKnownPosition(
                agent_name=track.agent_name,
                map_x=track.last.x,
                map_y=track.last.y,
                callout=track.last.callout,
                last_seen_seconds=track.last.timestamp,
                age_seconds=round(age, 2),
                confidence=track.last.confidence,
                source=track.last.source,
                stale=age > ttl_seconds,
            )
        )
    rows.sort(key=lambda r: r.age_seconds)
    return rows
