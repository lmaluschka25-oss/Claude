"""Match upload, listing, status, and derived-data endpoints."""
from __future__ import annotations

import uuid
from pathlib import Path

from fastapi import APIRouter, Depends, File, Form, HTTPException, Response, UploadFile
from sqlalchemy.orm import Session

from ...config import Settings
from ...logging_config import get_logger
from ...models import DetectionSource, Team
from ...schemas import (
    DetectionOut,
    KillfeedOut,
    MatchDetail,
    MatchSummary,
    RoundOut,
)
from ...services import match_service, pipeline
from ..deps import get_session, get_settings_dep

logger = get_logger(__name__)
router = APIRouter(prefix="/matches", tags=["matches"])

ALLOWED_EXTENSIONS = {".mp4", ".mov", ".mkv", ".avi", ".webm"}
CHUNK = 1024 * 1024  # 1 MiB


@router.get("", response_model=list[MatchSummary])
def list_matches(session: Session = Depends(get_session)) -> list[MatchSummary]:
    return [MatchSummary.model_validate(m) for m in match_service.list_matches(session)]


@router.post("", response_model=MatchDetail, status_code=201)
async def upload_match(
    file: UploadFile = File(...),
    map_name: str | None = Form(default=None),
    session: Session = Depends(get_session),
    settings: Settings = Depends(get_settings_dep),
) -> MatchDetail:
    suffix = Path(file.filename or "").suffix.lower()
    if suffix not in ALLOWED_EXTENSIONS:
        raise HTTPException(
            status_code=400,
            detail=f"Unsupported file type {suffix!r}. Allowed: {sorted(ALLOWED_EXTENSIONS)}",
        )

    stored_name = f"{uuid.uuid4().hex}{suffix}"
    stored_path = settings.upload_dir / stored_name
    max_bytes = settings.max_upload_mb * 1024 * 1024
    written = 0
    try:
        with stored_path.open("wb") as out:
            while chunk := await file.read(CHUNK):
                written += len(chunk)
                if written > max_bytes:
                    out.close()
                    stored_path.unlink(missing_ok=True)
                    raise HTTPException(
                        status_code=413,
                        detail=f"File exceeds limit of {settings.max_upload_mb} MB.",
                    )
                out.write(chunk)
    finally:
        await file.close()

    match = match_service.create_match(
        session,
        filename=file.filename or stored_name,
        stored_path=str(stored_path),
        map_name=map_name,
    )
    pipeline.submit(match.id)
    logger.info("Queued match %s (%s, %.1f MB)", match.id, match.filename, written / 1e6)
    return MatchDetail.model_validate(match)


@router.get("/{match_id}", response_model=MatchDetail)
def get_match(match_id: int, session: Session = Depends(get_session)) -> MatchDetail:
    match = match_service.get_match(session, match_id)
    if match is None:
        raise HTTPException(status_code=404, detail="Match not found")
    return MatchDetail.model_validate(match)


@router.delete("/{match_id}", status_code=204, response_model=None)
def delete_match(match_id: int, session: Session = Depends(get_session)) -> Response:
    match = match_service.get_match(session, match_id)
    if match is None:
        raise HTTPException(status_code=404, detail="Match not found")
    match_service.delete_match(session, match)
    return Response(status_code=204)


@router.get("/{match_id}/rounds", response_model=list[RoundOut])
def get_rounds(match_id: int, session: Session = Depends(get_session)) -> list[RoundOut]:
    _require_match(session, match_id)
    return [RoundOut.model_validate(r) for r in match_service.get_rounds(session, match_id)]


@router.get("/{match_id}/detections", response_model=list[DetectionOut])
def get_detections(
    match_id: int,
    start: float | None = None,
    end: float | None = None,
    team: Team | None = None,
    source: DetectionSource | None = None,
    limit: int = 5000,
    session: Session = Depends(get_session),
) -> list[DetectionOut]:
    _require_match(session, match_id)
    rows = match_service.get_detections(
        session, match_id, start=start, end=end, team=team, source=source, limit=limit
    )
    return [DetectionOut.model_validate(d) for d in rows]


@router.get("/{match_id}/killfeed", response_model=list[KillfeedOut])
def get_killfeed(match_id: int, session: Session = Depends(get_session)) -> list[KillfeedOut]:
    _require_match(session, match_id)
    return [KillfeedOut.model_validate(k) for k in match_service.get_killfeed(session, match_id)]


@router.get("/{match_id}/minimap-preview")
def minimap_preview(
    match_id: int,
    t: float = 0.0,
    session: Session = Depends(get_session),
    settings: Settings = Depends(get_settings_dep),
) -> Response:
    """Return a PNG of one frame with the minimap ROI box + detected enemy dots.

    Use this to calibrate: the green box should sit exactly on the minimap and
    the red circles on the enemy markers. Adjust the VVC_MINIMAP_* settings until
    it lines up.
    """
    match = _require_match(session, match_id)
    import cv2  # lazy heavy import

    from ...vision.detector import MinimapColorDetector

    cap = cv2.VideoCapture(match.stored_path)
    if not cap.isOpened():
        raise HTTPException(status_code=500, detail="Video konnte nicht geöffnet werden.")
    cap.set(cv2.CAP_PROP_POS_MSEC, max(t, 0.0) * 1000.0)
    ok, frame = cap.read()
    cap.release()
    if not ok or frame is None:
        raise HTTPException(status_code=404, detail="Frame an dieser Stelle nicht lesbar.")

    h, w = frame.shape[:2]
    rx, ry, rw, rh = settings.minimap_calibration().roi_pixels(w, h)
    detector = MinimapColorDetector(settings)
    dets = detector.find_enemies(frame)

    cv2.rectangle(frame, (rx, ry), (rx + rw, ry + rh), (0, 255, 0), 2)
    for d in dets:
        cx, cy = d.center
        cv2.circle(frame, (int(cx), int(cy)), 9, (0, 0, 255), 2)
    cv2.putText(
        frame, f"enemies: {len(dets)}", (rx, max(ry - 8, 14)),
        cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 255, 0), 2,
    )

    ok, buf = cv2.imencode(".png", frame)
    if not ok:
        raise HTTPException(status_code=500, detail="PNG-Encoding fehlgeschlagen.")
    return Response(content=buf.tobytes(), media_type="image/png")


def _require_match(session: Session, match_id: int):
    match = match_service.get_match(session, match_id)
    if match is None:
        raise HTTPException(status_code=404, detail="Match not found")
    return match
