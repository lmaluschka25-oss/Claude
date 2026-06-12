"""Reusable persistence/query helpers for matches and their derived data."""
from __future__ import annotations

import os

from sqlalchemy import select
from sqlalchemy.orm import Session

from ..models import Detection, DetectionSource, KillfeedEvent, Match, Round, Team


def list_matches(session: Session) -> list[Match]:
    return list(session.scalars(select(Match).order_by(Match.created_at.desc())))


def get_match(session: Session, match_id: int) -> Match | None:
    return session.get(Match, match_id)


def create_match(
    session: Session, *, filename: str, stored_path: str, map_name: str | None
) -> Match:
    match = Match(filename=filename, stored_path=stored_path, map_name=map_name)
    session.add(match)
    session.commit()
    session.refresh(match)
    return match


def delete_match(session: Session, match: Match) -> None:
    path = match.stored_path
    session.delete(match)
    session.commit()
    if path and os.path.exists(path):
        try:
            os.remove(path)
        except OSError:
            pass


def get_rounds(session: Session, match_id: int) -> list[Round]:
    return list(
        session.scalars(
            select(Round).where(Round.match_id == match_id).order_by(Round.round_number)
        )
    )


def get_detections(
    session: Session,
    match_id: int,
    *,
    start: float | None = None,
    end: float | None = None,
    team: Team | None = None,
    source: DetectionSource | None = None,
    limit: int | None = None,
) -> list[Detection]:
    stmt = select(Detection).where(Detection.match_id == match_id)
    if start is not None:
        stmt = stmt.where(Detection.timestamp_seconds >= start)
    if end is not None:
        stmt = stmt.where(Detection.timestamp_seconds <= end)
    if team is not None:
        stmt = stmt.where(Detection.team == team)
    if source is not None:
        stmt = stmt.where(Detection.source == source)
    stmt = stmt.order_by(Detection.timestamp_seconds)
    if limit is not None:
        stmt = stmt.limit(limit)
    return list(session.scalars(stmt))


def get_detections_window(
    session: Session, match_id: int, at_seconds: float, lookback: float
) -> list[Detection]:
    """Detections in ``[at - lookback, at]`` — the slice analysis needs."""
    return get_detections(
        session,
        match_id,
        start=max(0.0, at_seconds - lookback),
        end=at_seconds,
    )


def get_killfeed(session: Session, match_id: int) -> list[KillfeedEvent]:
    return list(
        session.scalars(
            select(KillfeedEvent)
            .where(KillfeedEvent.match_id == match_id)
            .order_by(KillfeedEvent.timestamp_seconds)
        )
    )
