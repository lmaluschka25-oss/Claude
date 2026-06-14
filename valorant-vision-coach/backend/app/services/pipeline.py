"""Background processing pipeline: analyze one uploaded round recording.

Each upload becomes a ``Round`` of a ``Match``. Processing detects on-screen
markers, persists detections/utilities/killfeed, derives the round's committed
site and HUD metadata, and leaves the match's aggregated intelligence to be
recomputed on read. A single worker serializes heavy model access.
"""
from __future__ import annotations

from collections import Counter
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from functools import lru_cache

from ..config import Settings
from ..config import settings as app_settings
from ..database import session_scope
from ..logging_config import get_logger
from ..models import (
    Detection,
    KillfeedEvent,
    ProcessingStatus,
    Round,
    Side,
    Team,
    UtilityDetection,
    UtilityKind,
)
from ..vision.calibration import DEFAULT_CALIBRATION
from ..vision.detector import MinimapColorDetector, build_detector
from ..vision.maps import list_maps, load_map
from ..vision.ocr import OcrEngine
from ..vision.video_processor import ProcessOutput, VideoProcessor
from . import calibration_store

logger = get_logger(__name__)

_executor = ThreadPoolExecutor(max_workers=1, thread_name_prefix="vvc-pipeline")


@lru_cache
def _get_detector(backend: str):
    return build_detector(app_settings)


@lru_cache
def _get_ocr(backend: str) -> OcrEngine:
    return OcrEngine(backend)


def _default_map(requested: str | None) -> str | None:
    if requested:
        return requested.lower()
    available = list_maps()
    return available[0] if available else None


def submit(round_id: int) -> None:
    _executor.submit(run, round_id)


def run(round_id: int, settings: Settings | None = None) -> None:
    cfg = settings or app_settings
    logger.info("Processing round %s", round_id)

    with session_scope() as session:
        rnd = session.get(Round, round_id)
        if rnd is None:
            logger.error("Round %s not found; aborting.", round_id)
            return
        rnd.status = ProcessingStatus.PROCESSING
        rnd.status_detail = "Initializing"
        rnd.progress = 0.0
        video_path = rnd.stored_path
        round_number = rnd.round_number
        match = rnd.match
        map_name = _default_map(rnd.map_name or match.map_name)
        match_side = match.side

    try:
        video_path = _normalize_video(video_path)
        ocr = _get_ocr(cfg.ocr_backend)
        game_map = load_map(map_name) if map_name else None
        store = calibration_store.load(cfg)
        metadata: dict = {}
        backend = cfg.detector_backend.lower()
        if backend == "mock":
            detector = _get_detector("mock")
            detector.set_round(round_number)
            metadata = detector.round_metadata(round_number)
            calib = DEFAULT_CALIBRATION  # mock emits markers at the default ROI
        elif backend in ("minimap", "multistage"):
            # Fresh per round so frame-tracking state is clean.
            from ..vision.multistage import MultiStageMinimapDetector

            detector = MultiStageMinimapDetector(cfg, calibration_store.calibration(cfg))
            calibration_store.apply_to_multistage(detector, cfg)
            detector.reset()
            calib = detector.calibration
        else:
            detector = _get_detector(cfg.detector_backend)
            if isinstance(detector, MinimapColorDetector):
                calibration_store.apply_to_detector(detector, cfg)
            calib = calibration_store.calibration(cfg)
        interval = float(store.get("analysis_interval", 0.5))
        conf_threshold = float(store.get("confidence_threshold", 0.0))
        processor = VideoProcessor(
            cfg, detector, ocr=ocr, game_map=game_map, calibration=calib,
            analysis_interval=interval,
        )

        def progress_cb(fraction: float, detail: str) -> None:
            with session_scope() as session:
                r = session.get(Round, round_id)
                if r is not None:
                    r.progress = round(fraction, 4)
                    r.status_detail = detail

        output = processor.process(video_path, progress_cb=progress_cb)
        if conf_threshold > 0:
            output.detections = [
                d for d in output.detections
                if d.team != Team.ENEMY or d.confidence >= conf_threshold
            ]
        _persist(round_id, output, map_name, match_side, metadata, game_map, video_path)
        logger.info("Finished round %s", round_id)
    except Exception as exc:  # noqa: BLE001
        logger.exception("Processing failed for round %s: %s", round_id, exc)
        with session_scope() as session:
            r = session.get(Round, round_id)
            if r is not None:
                r.status = ProcessingStatus.FAILED
                r.status_detail = str(exc)[:1000]


def _normalize_video(path: str) -> str:
    """Transcode browser/webm recordings to a seekable mp4 (fixes wrong duration
    and broken seeking). No-op for mp4 or when ffmpeg is unavailable."""
    import os
    import shutil
    import subprocess

    if path.lower().endswith(".mp4"):
        return path
    ffmpeg = shutil.which("ffmpeg")
    if not ffmpeg:
        logger.warning("ffmpeg not found — cannot normalize %s; seeking may be off.", path)
        return path
    out = os.path.splitext(path)[0] + ".norm.mp4"
    try:
        subprocess.run(
            [ffmpeg, "-y", "-i", path, "-c:v", "libx264", "-preset", "veryfast",
             "-pix_fmt", "yuv420p", "-an", "-movflags", "+faststart", out],
            check=True, capture_output=True, timeout=900,
        )
        if os.path.exists(out) and os.path.getsize(out) > 0:
            try:
                os.remove(path)
            except OSError:
                pass
            logger.info("Normalized recording → %s", out)
            return out
    except Exception as exc:  # noqa: BLE001
        logger.warning("ffmpeg normalize failed (%s); using original.", exc)
    return path


def _committed_site(output: ProcessOutput, game_map) -> str | None:
    if game_map is None:
        return None
    from ..analysis.intelligence import assign_site

    scores: Counter[str] = Counter()
    for d in output.detections:
        if d.team != Team.ENEMY or d.map_x is None or d.map_y is None:
            continue
        site = assign_site(game_map, d.map_x, d.map_y)
        if site:
            scores[site] += max(d.confidence, 0.1)
    return scores.most_common(1)[0][0] if scores else None


def _persist(
    round_id, output: ProcessOutput, map_name, match_side, metadata, game_map, video_path
) -> None:
    from ..models import Detection as _Det
    from ..models import KillfeedEvent as _Kf
    from ..models import UtilityDetection as _Ut

    with session_scope() as session:
        rnd = session.get(Round, round_id)
        if rnd is None:
            return
        match_id = rnd.match_id

        # Idempotent: clear any prior results so re-analysis doesn't duplicate.
        for model in (_Det, _Ut, _Kf):
            session.query(model).filter(model.round_id == round_id).delete()

        rnd.stored_path = video_path
        rnd.duration_seconds = output.duration_seconds
        rnd.fps = output.fps
        rnd.frame_count = output.frame_count
        rnd.map_name = map_name
        rnd.map_confidence = 0.99 if map_name else 0.0

        side_str = metadata.get("side")
        if side_str:
            rnd.side = Side(side_str)
            rnd.side_confidence = 0.9
        else:
            rnd.side = match_side
        rnd.score_text = output.score_text or metadata.get("score_text")
        rnd.round_time = output.round_time or metadata.get("round_time")
        rnd.economy = metadata.get("economy")
        rnd.spike_planted = output.spike_planted or bool(metadata.get("spike_planted"))

        for d in output.detections:
            bbox = d.bbox or (None, None, None, None)
            session.add(Detection(
                match_id=match_id, round_id=round_id,
                timestamp_seconds=d.timestamp_seconds, frame_number=d.frame_number,
                agent_name=d.agent_name, team=d.team, source=d.source, confidence=d.confidence,
                map_x=d.map_x, map_y=d.map_y, callout=d.callout,
                bbox_x=bbox[0], bbox_y=bbox[1], bbox_w=bbox[2], bbox_h=bbox[3],
            ))
        for u in output.utilities:
            try:
                kind = UtilityKind(u.kind)
            except ValueError:
                kind = UtilityKind.OTHER
            session.add(UtilityDetection(
                match_id=match_id, round_id=round_id, timestamp_seconds=u.timestamp_seconds,
                kind=kind, agent_name=u.agent_name, map_x=u.map_x, map_y=u.map_y,
                callout=u.callout, confidence=u.confidence,
            ))

        killfeed = list(output.killfeed)
        if not killfeed and metadata.get("killfeed"):
            for k in metadata["killfeed"]:
                session.add(KillfeedEvent(
                    match_id=match_id, round_id=round_id, timestamp_seconds=k["t"],
                    killer=k.get("killer"), victim=k.get("victim"), weapon=k.get("weapon"),
                    headshot=bool(k.get("headshot")),
                    killer_team=Team(k.get("killer_team", "unknown")),
                ))
        else:
            for k in killfeed:
                session.add(KillfeedEvent(
                    match_id=match_id, round_id=round_id, timestamp_seconds=k.timestamp_seconds,
                    killer=k.killer, victim=k.victim, weapon=k.weapon, headshot=k.headshot,
                    killer_team=k.killer_team,
                ))

        rnd.detections_count = len(output.detections)
        rnd.committed_site = _committed_site(output, game_map)
        rnd.status = ProcessingStatus.COMPLETED
        rnd.status_detail = "Completed"
        rnd.progress = 1.0
        rnd.processed_at = datetime.now(timezone.utc)
