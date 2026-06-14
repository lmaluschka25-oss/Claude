"""Match management, round uploads, intelligence, and media endpoints."""
from __future__ import annotations

import os
import re
import uuid
from collections import OrderedDict
from pathlib import Path

from fastapi import APIRouter, Depends, File, Form, HTTPException, Request, Response, UploadFile
from sqlalchemy.orm import Session
from starlette.responses import StreamingResponse

from ...analysis.intelligence import build_match_intelligence
from ...config import Settings
from ...logging_config import get_logger
from ...schemas import (
    DetectionOut,
    MatchCreate,
    MatchDetail,
    MatchIntelligence,
    MatchSummary,
    MatchUpdate,
    RoundOut,
)
from ...services import match_service, pipeline
from ..deps import get_session, get_settings_dep

logger = get_logger(__name__)
router = APIRouter(prefix="/matches", tags=["matches"])
rounds_router = APIRouter(prefix="/rounds", tags=["rounds"])

ALLOWED_EXTENSIONS = {".mp4", ".mov", ".mkv", ".avi", ".webm"}
CHUNK = 1024 * 1024
_VIDEO_MIME = {
    ".mp4": "video/mp4", ".webm": "video/webm", ".mov": "video/quicktime",
    ".mkv": "video/x-matroska", ".avi": "video/x-msvideo",
}

# Small LRU cache of decoded preview frames. Opening + seeking a VideoCapture
# is the slow part; tuning colour/threshold sliders re-runs only detection on
# the cached frame, so the Settings preview stays snappy instead of re-decoding
# the video on every slider tick.
_FRAME_CACHE: OrderedDict[tuple, object] = OrderedDict()
_FRAME_CACHE_MAX = 12


def _read_frame_at(path: str, t: float):
    """Decode the frame at time ``t`` (seconds), memoizing recent results."""
    import cv2

    key = (path, round(max(t, 0.0), 2))
    cached = _FRAME_CACHE.get(key)
    if cached is not None:
        _FRAME_CACHE.move_to_end(key)
        return cached.copy()
    cap = cv2.VideoCapture(path)
    if not cap.isOpened():
        return None
    cap.set(cv2.CAP_PROP_POS_MSEC, max(t, 0.0) * 1000.0)
    ok, frame = cap.read()
    cap.release()
    if not ok or frame is None:
        return None
    _FRAME_CACHE[key] = frame.copy()
    _FRAME_CACHE.move_to_end(key)
    while len(_FRAME_CACHE) > _FRAME_CACHE_MAX:
        _FRAME_CACHE.popitem(last=False)
    return frame


# ---- Matches -------------------------------------------------------------
@router.get("", response_model=list[MatchSummary])
def list_matches(session: Session = Depends(get_session)) -> list[MatchSummary]:
    return [match_service.to_summary(m) for m in match_service.list_matches(session)]


@router.post("", response_model=MatchDetail, status_code=201)
def create_match(body: MatchCreate, session: Session = Depends(get_session)) -> MatchDetail:
    match = match_service.create_match(
        session, name=body.name, map_name=body.map_name, side=body.side
    )
    return _detail(match)


@router.get("/{match_id}", response_model=MatchDetail)
def get_match(match_id: int, session: Session = Depends(get_session)) -> MatchDetail:
    return _detail(_require_match(session, match_id))


@router.patch("/{match_id}", response_model=MatchDetail)
def patch_match(
    match_id: int, body: MatchUpdate, session: Session = Depends(get_session)
) -> MatchDetail:
    match = _require_match(session, match_id)
    match_service.update_match(
        session, match, name=body.name, map_name=body.map_name, side=body.side
    )
    return _detail(match)


@router.delete("/{match_id}", status_code=204, response_model=None)
def delete_match(match_id: int, session: Session = Depends(get_session)) -> Response:
    match_service.delete_match(session, _require_match(session, match_id))
    return Response(status_code=204)


@router.get("/{match_id}/rounds", response_model=list[RoundOut])
def list_rounds(match_id: int, session: Session = Depends(get_session)) -> list[RoundOut]:
    match = _require_match(session, match_id)
    return [RoundOut.model_validate(r) for r in match.rounds]


@router.post("/{match_id}/rounds", response_model=RoundOut, status_code=201)
async def upload_round(
    match_id: int,
    file: UploadFile = File(...),
    map_name: str | None = Form(default=None),
    session: Session = Depends(get_session),
    settings: Settings = Depends(get_settings_dep),
) -> RoundOut:
    match = _require_match(session, match_id)
    suffix = Path(file.filename or "").suffix.lower()
    if suffix not in ALLOWED_EXTENSIONS:
        raise HTTPException(status_code=400, detail=f"Unsupported file type {suffix!r}.")

    stored_path = settings.upload_dir / f"{uuid.uuid4().hex}{suffix}"
    max_bytes = settings.max_upload_mb * 1024 * 1024
    written = 0
    try:
        with stored_path.open("wb") as out:
            while chunk := await file.read(CHUNK):
                written += len(chunk)
                if written > max_bytes:
                    out.close()
                    stored_path.unlink(missing_ok=True)
                    raise HTTPException(status_code=413, detail="File too large.")
                out.write(chunk)
    finally:
        await file.close()

    rnd = match_service.create_round(
        session,
        match_id=match.id,
        filename=file.filename or stored_path.name,
        stored_path=str(stored_path),
        map_name=(map_name or match.map_name),
    )
    pipeline.submit(rnd.id)
    logger.info("Queued round %s for match %s (%s)", rnd.round_number, match.id, rnd.filename)
    return RoundOut.model_validate(rnd)


@router.get("/{match_id}/intelligence", response_model=MatchIntelligence)
def intelligence(
    match_id: int,
    round_id: int | None = None,
    session: Session = Depends(get_session),
    settings: Settings = Depends(get_settings_dep),
) -> MatchIntelligence:
    return build_match_intelligence(
        session, _require_match(session, match_id), settings, round_id=round_id
    )


# ---- Rounds --------------------------------------------------------------
@rounds_router.get("/{round_id}", response_model=RoundOut)
def get_round(round_id: int, session: Session = Depends(get_session)) -> RoundOut:
    return RoundOut.model_validate(_require_round(session, round_id))


@rounds_router.delete("/{round_id}", status_code=204, response_model=None)
def delete_round(round_id: int, session: Session = Depends(get_session)) -> Response:
    match_service.delete_round(session, _require_round(session, round_id))
    return Response(status_code=204)


@rounds_router.get("/{round_id}/detections", response_model=list[DetectionOut])
def round_detections(round_id: int, session: Session = Depends(get_session)) -> list[DetectionOut]:
    _require_round(session, round_id)
    return [DetectionOut.model_validate(d) for d in match_service.get_detections(session, round_id)]


@rounds_router.get("/{round_id}/minimap-preview")
def minimap_preview(
    round_id: int,
    t: float = 0.0,
    mask: bool = False,
    crop: bool = False,
    clean: bool = False,
    x_frac: float | None = None,
    y_frac: float | None = None,
    w_frac: float | None = None,
    h_frac: float | None = None,
    sat_min: int | None = None,
    val_min: int | None = None,
    hue_min: int | None = None,
    hue_max: int | None = None,
    color_mode: str | None = None,
    confirm_threshold: float | None = None,
    template_threshold: float | None = None,
    session: Session = Depends(get_session),
    settings: Settings = Depends(get_settings_dep),
) -> Response:
    """A frame with the minimap ROI box + detected enemy dots (for calibration).

    Defaults to the SAVED calibration; query params override it live for tuning.
    ``crop=1`` returns just the zoomed minimap region.
    """
    rnd = _require_round(session, round_id)
    import cv2

    from ...services import calibration_store
    from ...vision.calibration import MinimapCalibration

    frame = _read_frame_at(rnd.stored_path, t)
    if frame is None:
        raise HTTPException(status_code=404, detail="Frame not readable here.")

    s = calibration_store.load(settings)  # saved settings as the base
    calib = MinimapCalibration(
        x_frac=x_frac if x_frac is not None else s["x_frac"],
        y_frac=y_frac if y_frac is not None else s["y_frac"],
        w_frac=w_frac if w_frac is not None else s["w_frac"],
        h_frac=h_frac if h_frac is not None else s["h_frac"],
        rotation=int(s["rotation"]), flip_x=bool(s["flip_x"]),
    )
    from ...vision.multistage import MultiStageMinimapDetector

    detector = MultiStageMinimapDetector(settings, calibration=calib)
    calibration_store.apply_to_multistage(detector, settings)
    detector.calibration = calib
    if color_mode:
        detector.color_mode = color_mode
    if hue_min is not None:
        detector.hue_min = hue_min
    if hue_max is not None:
        detector.hue_max = hue_max
    if sat_min is not None:
        detector.sat_floor = max(40, sat_min - 70)
    if val_min is not None:
        detector.val_floor = max(60, val_min - 60)
    if confirm_threshold is not None:
        detector.threshold = float(confirm_threshold)
    if template_threshold is not None:
        detector.template_threshold = float(template_threshold)

    fh, fw = frame.shape[:2]
    rx, ry, rw, rh = calib.roi_pixels(fw, fh)
    if not clean:
        _rx, _ry, cands = detector.debug_candidates(frame, min_total=0.3)
        cv2.rectangle(frame, (rx, ry), (rx + rw, ry + rh), (0, 255, 0), 2)
        confirmed = [c for c in cands if c["confirmed"]]
        # Amber = considered but not confirmed yet. These are exactly what to
        # click-to-teach so the detector learns to confirm them.
        candidates = sorted((c for c in cands if not c["confirmed"]),
                            key=lambda c: c["total"], reverse=True)[:25]
        for c in candidates:
            cv2.circle(frame, (int(c["cx"]), int(c["cy"])), 7, (0, 170, 255), 1)
            cv2.putText(frame, str(int(c["total"] * 100)),
                        (int(c["cx"]) + 7, int(c["cy"]) - 4),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.35, (0, 170, 255), 1)
        for c in confirmed:
            cv2.circle(frame, (int(c["cx"]), int(c["cy"])), 8, (0, 220, 0), 2)
            cv2.putText(frame, str(int(c["total"] * 100)),
                        (int(c["cx"]) + 8, int(c["cy"]) - 5),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.4, (0, 220, 0), 1)
        cv2.putText(frame, f"confirmed: {len(confirmed)}   candidates: {len(candidates)}",
                    (rx, max(ry - 8, 14)), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 255, 0), 2)

    if crop and rw > 0 and rh > 0:
        sub = frame[ry : ry + rh, rx : rx + rw]
        if sub.size and sub.shape[1] > 0:
            target = 560  # crisp zoom of just the minimap for precise teaching
            scale = target / sub.shape[1]
            frame = cv2.resize(sub, (target, max(1, int(sub.shape[0] * scale))),
                               interpolation=cv2.INTER_NEAREST)

    ok, buf = cv2.imencode(".png", frame)
    if not ok:
        raise HTTPException(status_code=500, detail="PNG encoding failed.")
    return Response(content=buf.tobytes(), media_type="image/png")


@rounds_router.post("/{round_id}/reanalyze", response_model=RoundOut, status_code=202)
def reanalyze_round(round_id: int, session: Session = Depends(get_session)) -> RoundOut:
    """Re-run analysis for a round with the current saved calibration."""
    from ...models import ProcessingStatus

    rnd = _require_round(session, round_id)
    rnd.status = ProcessingStatus.PENDING
    rnd.status_detail = "Queued for re-analysis"
    rnd.progress = 0.0
    session.commit()
    session.refresh(rnd)
    pipeline.submit(rnd.id)
    return RoundOut.model_validate(rnd)


@rounds_router.post("/{round_id}/teach")
def teach_round(
    round_id: int,
    t: float = 0.0,
    x: float = 0.5,
    y: float = 0.5,
    label: str = "enemy",
    roi: bool = False,
    session: Session = Depends(get_session),
    settings: Settings = Depends(get_settings_dep),
) -> dict:
    """Save a template at (x,y) as a confirmed enemy / false positive.

    ``roi=1`` ⇒ (x,y) are normalized within the minimap box (matches the zoomed
    teach view); otherwise they are normalized over the whole frame. Feeds the
    learnable template store used by the multi-stage detector.
    """
    rnd = _require_round(session, round_id)
    from ...services import calibration_store
    from ...vision import multistage
    from ...vision.multistage import MultiStageMinimapDetector

    frame = _read_frame_at(rnd.stored_path, t)
    if frame is None:
        raise HTTPException(status_code=404, detail="Frame not readable here.")
    fh, fw = frame.shape[:2]
    calib = calibration_store.calibration(settings)
    if roi:
        rx, ry, rw, rh = calib.roi_pixels(fw, fh)
        px, py = rx + x * rw, ry + y * rh
    else:
        px, py = x * fw, y * fh
    det = MultiStageMinimapDetector(settings, calibration=calib)
    saved = det.teach(frame, px, py, "false" if label == "false" else "enemy")
    counts = multistage.list_templates(settings)
    return {
        "saved": bool(saved), "label": label,
        "px": round(px, 1), "py": round(py, 1),
        "enemy_count": len(counts["enemy"]), "false_count": len(counts["false"]),
    }


@rounds_router.get("/{round_id}/video")
def round_video(
    round_id: int, request: Request, session: Session = Depends(get_session)
) -> Response:
    """Stream the stored recording, with HTTP range support for <video>."""
    rnd = _require_round(session, round_id)
    path = rnd.stored_path
    if not os.path.exists(path):
        raise HTTPException(status_code=404, detail="Recording not found.")
    file_size = os.path.getsize(path)
    media = _VIDEO_MIME.get(Path(path).suffix.lower(), "application/octet-stream")
    range_header = request.headers.get("range")

    if range_header:
        m = re.match(r"bytes=(\d+)-(\d*)", range_header)
        start = int(m.group(1)) if m else 0
        end = int(m.group(2)) if (m and m.group(2)) else file_size - 1
        end = min(end, file_size - 1)
        length = end - start + 1

        def iter_range():
            with open(path, "rb") as f:
                f.seek(start)
                remaining = length
                while remaining > 0:
                    chunk = f.read(min(CHUNK, remaining))
                    if not chunk:
                        break
                    remaining -= len(chunk)
                    yield chunk

        headers = {
            "Content-Range": f"bytes {start}-{end}/{file_size}",
            "Accept-Ranges": "bytes",
            "Content-Length": str(length),
        }
        return StreamingResponse(iter_range(), status_code=206, headers=headers, media_type=media)

    def iter_all():
        with open(path, "rb") as f:
            while chunk := f.read(CHUNK):
                yield chunk

    return StreamingResponse(
        iter_all(), headers={"Accept-Ranges": "bytes", "Content-Length": str(file_size)},
        media_type=media,
    )


# ---- helpers -------------------------------------------------------------
def _require_match(session: Session, match_id: int):
    match = match_service.get_match(session, match_id)
    if match is None:
        raise HTTPException(status_code=404, detail="Match not found")
    return match


def _require_round(session: Session, round_id: int):
    rnd = match_service.get_round(session, round_id)
    if rnd is None:
        raise HTTPException(status_code=404, detail="Round not found")
    return rnd


def _detail(match) -> MatchDetail:
    summary = match_service.to_summary(match)
    return MatchDetail(
        **summary.model_dump(),
        rounds=[RoundOut.model_validate(r) for r in match.rounds],
    )
