"""Background processing pipeline.

Submits each uploaded match to a single-worker thread pool (so heavy YOLO
inference is serialized and thread-safe), streams progress into the database,
and persists detections, killfeed events, and rounds. For higher throughput
swap the executor for a Celery/RQ worker — the ``run`` entry point is unchanged.
"""
from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from functools import lru_cache

from ..config import Settings
from ..config import settings as app_settings
from ..database import session_scope
from ..logging_config import get_logger
from ..models import Detection, KillfeedEvent, Match, ProcessingStatus, Round
from ..vision.detector import build_detector
from ..vision.maps import list_maps, load_map
from ..vision.ocr import OcrEngine
from ..vision.video_processor import ProcessOutput, VideoProcessor

logger = get_logger(__name__)

# Single worker: serializes GPU/model access and keeps memory bounded.
_executor = ThreadPoolExecutor(max_workers=1, thread_name_prefix="vvc-pipeline")


@lru_cache
def _get_detector(backend: str):
    # ``backend`` participates in the cache key so a config change rebuilds it.
    return build_detector(app_settings)


@lru_cache
def _get_ocr(backend: str) -> OcrEngine:
    return OcrEngine(backend)


def _default_map(requested: str | None) -> str | None:
    if requested:
        return requested.lower()
    available = list_maps()
    return available[0] if available else None


def submit(match_id: int) -> None:
    """Queue a match for processing in the background."""
    _executor.submit(run, match_id)


def run(match_id: int, settings: Settings | None = None) -> None:
    """Process one match end to end. Safe to call directly (e.g. in tests)."""
    cfg = settings or app_settings
    logger.info("Starting processing for match %s", match_id)

    with session_scope() as session:
        match = session.get(Match, match_id)
        if match is None:
            logger.error("Match %s not found; aborting.", match_id)
            return
        match.status = ProcessingStatus.PROCESSING
        match.status_detail = "Initializing"
        match.progress = 0.0
        video_path = match.stored_path
        map_name = _default_map(match.map_name)
        match.map_name = map_name

    try:
        detector = _get_detector(cfg.detector_backend)
        ocr = _get_ocr(cfg.ocr_backend)
        game_map = load_map(map_name) if map_name else None
        processor = VideoProcessor(cfg, detector, ocr=ocr, game_map=game_map)

        def progress_cb(fraction: float, detail: str) -> None:
            with session_scope() as session:
                m = session.get(Match, match_id)
                if m is not None:
                    m.progress = round(fraction, 4)
                    m.status_detail = detail

        output = processor.process(video_path, progress_cb=progress_cb)
        _persist(match_id, output)
        logger.info("Finished processing match %s", match_id)
    except Exception as exc:  # noqa: BLE001 - we want to record any failure
        logger.exception("Processing failed for match %s: %s", match_id, exc)
        with session_scope() as session:
            m = session.get(Match, match_id)
            if m is not None:
                m.status = ProcessingStatus.FAILED
                m.status_detail = str(exc)[:1000]


def _persist(match_id: int, output: ProcessOutput) -> None:
    with session_scope() as session:
        match = session.get(Match, match_id)
        if match is None:
            return
        match.duration_seconds = output.duration_seconds
        match.fps = output.fps
        match.frame_count = output.frame_count

        round_id_by_number: dict[int, int] = {}
        for r in output.rounds:
            row = Round(
                match_id=match_id,
                round_number=r.round_number,
                start_seconds=r.start_seconds,
                end_seconds=r.end_seconds,
                score_text=r.score_text,
                spike_planted=r.spike_planted,
            )
            session.add(row)
            session.flush()
            round_id_by_number[r.round_number] = row.id

        def round_for(ts: float) -> int | None:
            for r in output.rounds:
                end = r.end_seconds if r.end_seconds is not None else float("inf")
                if r.start_seconds <= ts <= end:
                    return round_id_by_number.get(r.round_number)
            return None

        for d in output.detections:
            bbox = d.bbox or (None, None, None, None)
            session.add(
                Detection(
                    match_id=match_id,
                    round_id=round_for(d.timestamp_seconds),
                    timestamp_seconds=d.timestamp_seconds,
                    frame_number=d.frame_number,
                    agent_name=d.agent_name,
                    team=d.team,
                    source=d.source,
                    confidence=d.confidence,
                    map_x=d.map_x,
                    map_y=d.map_y,
                    callout=d.callout,
                    bbox_x=bbox[0],
                    bbox_y=bbox[1],
                    bbox_w=bbox[2],
                    bbox_h=bbox[3],
                )
            )

        for k in output.killfeed:
            session.add(
                KillfeedEvent(
                    match_id=match_id,
                    round_id=round_for(k.timestamp_seconds),
                    timestamp_seconds=k.timestamp_seconds,
                    killer=k.killer,
                    victim=k.victim,
                    weapon=k.weapon,
                    headshot=k.headshot,
                )
            )

        match.detections_count = len(output.detections)
        match.status = ProcessingStatus.COMPLETED
        match.status_detail = "Completed"
        match.progress = 1.0
        match.processed_at = datetime.now(timezone.utc)
