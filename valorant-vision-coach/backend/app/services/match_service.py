"""Persistence/query helpers for matches and rounds."""
from __future__ import annotations

import os

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from ..models import Detection, Match, ProcessingStatus, Round, Side
from ..schemas import MatchSummary


def list_matches(session: Session) -> list[Match]:
    return list(session.scalars(select(Match).order_by(Match.updated_at.desc())))


def get_match(session: Session, match_id: int) -> Match | None:
    return session.get(Match, match_id)


def create_match(
    session: Session, *, name: str | None, map_name: str | None, side: Side
) -> Match:
    if not name:
        count = session.scalar(select(func.count(Match.id))) or 0
        label = (map_name or "Match").title()
        name = f"{label} #{count + 1}"
    match = Match(name=name, map_name=(map_name.lower() if map_name else None), side=side)
    session.add(match)
    session.commit()
    session.refresh(match)
    return match


def update_match(
    session: Session, match: Match, *, name=None, map_name=None, side: Side | None = None
) -> Match:
    if name is not None:
        match.name = name
    if map_name is not None:
        match.map_name = map_name.lower() or None
    if side is not None:
        match.side = side
    session.commit()
    session.refresh(match)
    return match


def delete_match(session: Session, match: Match) -> None:
    paths = [r.stored_path for r in match.rounds]
    session.delete(match)
    session.commit()
    for p in paths:
        if p and os.path.exists(p):
            try:
                os.remove(p)
            except OSError:
                pass


def next_round_number(session: Session, match_id: int) -> int:
    current = session.scalar(
        select(func.max(Round.round_number)).where(Round.match_id == match_id)
    )
    return (current or 0) + 1


def create_round(
    session: Session, *, match_id: int, filename: str, stored_path: str, map_name: str | None
) -> Round:
    rnd = Round(
        match_id=match_id,
        round_number=next_round_number(session, match_id),
        filename=filename,
        stored_path=stored_path,
        map_name=map_name,
    )
    session.add(rnd)
    session.commit()
    session.refresh(rnd)
    return rnd


def get_round(session: Session, round_id: int) -> Round | None:
    return session.get(Round, round_id)


def delete_round(session: Session, rnd: Round) -> None:
    path = rnd.stored_path
    session.delete(rnd)
    session.commit()
    if path and os.path.exists(path):
        try:
            os.remove(path)
        except OSError:
            pass


def get_detections(session: Session, round_id: int) -> list[Detection]:
    return list(
        session.scalars(
            select(Detection)
            .where(Detection.round_id == round_id)
            .order_by(Detection.timestamp_seconds)
        )
    )


def to_summary(match: Match) -> MatchSummary:
    rounds = list(match.rounds)
    completed = sum(1 for r in rounds if r.status == ProcessingStatus.COMPLETED)
    return MatchSummary(
        id=match.id,
        name=match.name,
        map_name=match.map_name,
        side=match.side,
        created_at=match.created_at,
        updated_at=match.updated_at,
        rounds_count=len(rounds),
        completed_rounds=completed,
    )
