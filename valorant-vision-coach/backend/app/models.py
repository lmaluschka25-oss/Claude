"""ORM models.

Data model overview
-------------------
``Match``          one uploaded recording + its processing status.
``Round``          a detected round within a match (best-effort segmentation).
``Detection``      a single on-screen observation of an agent/enemy at a time.
``KillfeedEvent``  a parsed killfeed line (killer, victim, weapon, headshot).

Every row is derived purely from pixels that were visible on the player's
screen. No field originates from game memory, packets, or hidden state.
"""
from __future__ import annotations

import enum
from datetime import datetime, timezone

from sqlalchemy import (
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


class DetectionSource(str, enum.Enum):
    # Enemy/agent recognized in the main 3D viewport (the player saw them).
    VIEWPORT = "viewport"
    # A revealed dot on the player's own minimap (legitimately visible).
    MINIMAP = "minimap"


class Match(Base):
    __tablename__ = "matches"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    filename: Mapped[str] = mapped_column(String(512))
    stored_path: Mapped[str] = mapped_column(String(1024))
    map_name: Mapped[str | None] = mapped_column(String(64), nullable=True)
    status: Mapped[ProcessingStatus] = mapped_column(
        Enum(ProcessingStatus), default=ProcessingStatus.PENDING, index=True
    )
    status_detail: Mapped[str | None] = mapped_column(Text, nullable=True)
    progress: Mapped[float] = mapped_column(Float, default=0.0)  # 0..1

    duration_seconds: Mapped[float | None] = mapped_column(Float, nullable=True)
    fps: Mapped[float | None] = mapped_column(Float, nullable=True)
    frame_count: Mapped[int | None] = mapped_column(Integer, nullable=True)
    detections_count: Mapped[int] = mapped_column(Integer, default=0)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)
    processed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    rounds: Mapped[list[Round]] = relationship(
        back_populates="match", cascade="all, delete-orphan"
    )
    detections: Mapped[list[Detection]] = relationship(
        back_populates="match", cascade="all, delete-orphan"
    )
    killfeed: Mapped[list[KillfeedEvent]] = relationship(
        back_populates="match", cascade="all, delete-orphan"
    )


class Round(Base):
    __tablename__ = "rounds"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    match_id: Mapped[int] = mapped_column(ForeignKey("matches.id", ondelete="CASCADE"), index=True)
    round_number: Mapped[int] = mapped_column(Integer)
    start_seconds: Mapped[float] = mapped_column(Float)
    end_seconds: Mapped[float | None] = mapped_column(Float, nullable=True)
    # Scoreboard at round start, if read: "7-5" style, plus spike-planted flag.
    score_text: Mapped[str | None] = mapped_column(String(16), nullable=True)
    spike_planted: Mapped[bool] = mapped_column(default=False)

    match: Mapped[Match] = relationship(back_populates="rounds")


class Detection(Base):
    __tablename__ = "detections"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    match_id: Mapped[int] = mapped_column(ForeignKey("matches.id", ondelete="CASCADE"), index=True)
    round_id: Mapped[int | None] = mapped_column(
        ForeignKey("rounds.id", ondelete="SET NULL"), nullable=True, index=True
    )

    timestamp_seconds: Mapped[float] = mapped_column(Float, index=True)
    frame_number: Mapped[int] = mapped_column(Integer)

    agent_name: Mapped[str | None] = mapped_column(String(64), nullable=True)
    team: Mapped[Team] = mapped_column(Enum(Team), default=Team.UNKNOWN)
    source: Mapped[DetectionSource] = mapped_column(
        Enum(DetectionSource), default=DetectionSource.VIEWPORT
    )
    confidence: Mapped[float] = mapped_column(Float)

    # Normalized map coordinates in [0, 1]; null when location could not be
    # resolved (e.g. enemy seen in viewport but player position unknown).
    map_x: Mapped[float | None] = mapped_column(Float, nullable=True)
    map_y: Mapped[float | None] = mapped_column(Float, nullable=True)
    # Nearest named callout, resolved from map metadata.
    callout: Mapped[str | None] = mapped_column(String(64), nullable=True)

    # Raw screen-space bounding box (pixels): x, y, w, h.
    bbox_x: Mapped[float | None] = mapped_column(Float, nullable=True)
    bbox_y: Mapped[float | None] = mapped_column(Float, nullable=True)
    bbox_w: Mapped[float | None] = mapped_column(Float, nullable=True)
    bbox_h: Mapped[float | None] = mapped_column(Float, nullable=True)

    match: Mapped[Match] = relationship(back_populates="detections")


class KillfeedEvent(Base):
    __tablename__ = "killfeed_events"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    match_id: Mapped[int] = mapped_column(ForeignKey("matches.id", ondelete="CASCADE"), index=True)
    round_id: Mapped[int | None] = mapped_column(
        ForeignKey("rounds.id", ondelete="SET NULL"), nullable=True
    )
    timestamp_seconds: Mapped[float] = mapped_column(Float, index=True)
    killer: Mapped[str | None] = mapped_column(String(64), nullable=True)
    victim: Mapped[str | None] = mapped_column(String(64), nullable=True)
    weapon: Mapped[str | None] = mapped_column(String(64), nullable=True)
    headshot: Mapped[bool] = mapped_column(default=False)
    killer_team: Mapped[Team] = mapped_column(Enum(Team), default=Team.UNKNOWN)

    match: Mapped[Match] = relationship(back_populates="killfeed")
