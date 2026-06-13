"""ORM models for the Match Intelligence platform.

Domain model
------------
``Match``             one competitive match (a map, a side, a growing memory).
``Round``             one *uploaded recording* = one round belonging to a match.
``Detection``         an on-screen sighting of an agent/enemy/ally in a round.
``UtilityDetection``  an on-screen utility marker (smoke, recon, turret, …).
``KillfeedEvent``     a parsed killfeed line.

A match accumulates rounds; intelligence (memory, patterns, predictions) is
aggregated across every round in the match. Every row is derived purely from
pixels visible on the player's own screen — never game memory, packets, or
hidden state.
"""
from __future__ import annotations

import enum
from datetime import datetime, timezone

from sqlalchemy import (
    Boolean,
    DateTime,
    Enum,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .database import Base


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class ProcessingStatus(str, enum.Enum):
    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"


class Team(str, enum.Enum):
    ALLY = "ally"
    ENEMY = "enemy"
    UNKNOWN = "unknown"


class Side(str, enum.Enum):
    ATTACK = "attack"
    DEFENSE = "defense"
    UNKNOWN = "unknown"


class DetectionSource(str, enum.Enum):
    VIEWPORT = "viewport"  # seen in the 3D view
    MINIMAP = "minimap"  # a revealed marker on the player's own minimap


class UtilityKind(str, enum.Enum):
    SMOKE = "smoke"
    RECON = "recon"
    TURRET = "turret"
    TRAP = "trap"
    FLASH = "flash"
    MOLLY = "molly"
    WALL = "wall"
    OTHER = "other"


class Match(Base):
    """A competitive match — the unit that owns rounds and accumulates memory."""

    __tablename__ = "matches"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(128))
    map_name: Mapped[str | None] = mapped_column(String(64), nullable=True)
    side: Mapped[Side] = mapped_column(Enum(Side), default=Side.UNKNOWN)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_utcnow, onupdate=_utcnow
    )

    rounds: Mapped[list[Round]] = relationship(
        back_populates="match",
        cascade="all, delete-orphan",
        order_by="Round.round_number",
    )


class Round(Base):
    """One uploaded recording, analyzed as a single round of its match."""

    __tablename__ = "rounds"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    match_id: Mapped[int] = mapped_column(ForeignKey("matches.id", ondelete="CASCADE"), index=True)
    round_number: Mapped[int] = mapped_column(Integer)

    filename: Mapped[str] = mapped_column(String(512))
    stored_path: Mapped[str] = mapped_column(String(1024))

    status: Mapped[ProcessingStatus] = mapped_column(
        Enum(ProcessingStatus), default=ProcessingStatus.PENDING, index=True
    )
    status_detail: Mapped[str | None] = mapped_column(Text, nullable=True)
    progress: Mapped[float] = mapped_column(Float, default=0.0)

    # Auto-detected per round (best effort); fall back to the match's values.
    map_name: Mapped[str | None] = mapped_column(String(64), nullable=True)
    map_confidence: Mapped[float] = mapped_column(Float, default=0.0)
    side: Mapped[Side] = mapped_column(Enum(Side), default=Side.UNKNOWN)
    side_confidence: Mapped[float] = mapped_column(Float, default=0.0)
    score_text: Mapped[str | None] = mapped_column(String(16), nullable=True)
    round_time: Mapped[str | None] = mapped_column(String(16), nullable=True)
    economy: Mapped[str | None] = mapped_column(String(32), nullable=True)
    spike_planted: Mapped[bool] = mapped_column(Boolean, default=False)

    duration_seconds: Mapped[float | None] = mapped_column(Float, nullable=True)
    fps: Mapped[float | None] = mapped_column(Float, nullable=True)
    frame_count: Mapped[int | None] = mapped_column(Integer, nullable=True)
    detections_count: Mapped[int] = mapped_column(Integer, default=0)

    committed_site: Mapped[str | None] = mapped_column(String(16), nullable=True)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)
    processed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    match: Mapped[Match] = relationship(back_populates="rounds")
    detections: Mapped[list[Detection]] = relationship(
        back_populates="round", cascade="all, delete-orphan"
    )
    utilities: Mapped[list[UtilityDetection]] = relationship(
        back_populates="round", cascade="all, delete-orphan"
    )
    killfeed: Mapped[list[KillfeedEvent]] = relationship(
        back_populates="round", cascade="all, delete-orphan"
    )


class Detection(Base):
    __tablename__ = "detections"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    match_id: Mapped[int] = mapped_column(ForeignKey("matches.id", ondelete="CASCADE"), index=True)
    round_id: Mapped[int] = mapped_column(ForeignKey("rounds.id", ondelete="CASCADE"), index=True)

    timestamp_seconds: Mapped[float] = mapped_column(Float, index=True)
    frame_number: Mapped[int] = mapped_column(Integer)

    agent_name: Mapped[str | None] = mapped_column(String(64), nullable=True)
    team: Mapped[Team] = mapped_column(Enum(Team), default=Team.UNKNOWN)
    source: Mapped[DetectionSource] = mapped_column(
        Enum(DetectionSource), default=DetectionSource.VIEWPORT
    )
    confidence: Mapped[float] = mapped_column(Float)

    map_x: Mapped[float | None] = mapped_column(Float, nullable=True)
    map_y: Mapped[float | None] = mapped_column(Float, nullable=True)
    callout: Mapped[str | None] = mapped_column(String(64), nullable=True)

    bbox_x: Mapped[float | None] = mapped_column(Float, nullable=True)
    bbox_y: Mapped[float | None] = mapped_column(Float, nullable=True)
    bbox_w: Mapped[float | None] = mapped_column(Float, nullable=True)
    bbox_h: Mapped[float | None] = mapped_column(Float, nullable=True)

    round: Mapped[Round] = relationship(back_populates="detections")


class UtilityDetection(Base):
    __tablename__ = "utility_detections"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    match_id: Mapped[int] = mapped_column(ForeignKey("matches.id", ondelete="CASCADE"), index=True)
    round_id: Mapped[int] = mapped_column(ForeignKey("rounds.id", ondelete="CASCADE"), index=True)

    timestamp_seconds: Mapped[float] = mapped_column(Float, index=True)
    kind: Mapped[UtilityKind] = mapped_column(Enum(UtilityKind), default=UtilityKind.OTHER)
    agent_name: Mapped[str | None] = mapped_column(String(64), nullable=True)
    confidence: Mapped[float] = mapped_column(Float, default=0.5)

    map_x: Mapped[float | None] = mapped_column(Float, nullable=True)
    map_y: Mapped[float | None] = mapped_column(Float, nullable=True)
    callout: Mapped[str | None] = mapped_column(String(64), nullable=True)

    round: Mapped[Round] = relationship(back_populates="utilities")


class KillfeedEvent(Base):
    __tablename__ = "killfeed_events"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    match_id: Mapped[int] = mapped_column(ForeignKey("matches.id", ondelete="CASCADE"), index=True)
    round_id: Mapped[int] = mapped_column(ForeignKey("rounds.id", ondelete="CASCADE"), index=True)

    timestamp_seconds: Mapped[float] = mapped_column(Float, index=True)
    killer: Mapped[str | None] = mapped_column(String(64), nullable=True)
    victim: Mapped[str | None] = mapped_column(String(64), nullable=True)
    weapon: Mapped[str | None] = mapped_column(String(64), nullable=True)
    headshot: Mapped[bool] = mapped_column(Boolean, default=False)
    killer_team: Mapped[Team] = mapped_column(Enum(Team), default=Team.UNKNOWN)

    round: Mapped[Round] = relationship(back_populates="killfeed")
