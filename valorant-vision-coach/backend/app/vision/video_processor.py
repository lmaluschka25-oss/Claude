"""Frame-by-frame video analysis orchestration.

Reads a recorded match with OpenCV, samples frames, runs the detector and OCR,
projects minimap markers into normalized map coordinates, resolves callouts,
and segments rounds from timer resets. Produces plain dataclass records that
the pipeline service persists.

OpenCV is imported lazily so the package stays importable on minimal installs.
"""
from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field

from ..config import Settings
from ..logging_config import get_logger
from ..models import DetectionSource, Team
from .calibration import DEFAULT_CALIBRATION, MinimapCalibration
from .detector import BaseDetector, parse_label
from .maps import GameMap
from .ocr import OcrEngine

logger = get_logger(__name__)


@dataclass
class DetectionRecord:
    timestamp_seconds: float
    frame_number: int
    agent_name: str | None
    team: Team
    source: DetectionSource
    confidence: float
    map_x: float | None
    map_y: float | None
    callout: str | None
    bbox: tuple[float, float, float, float] | None


@dataclass
class KillfeedRecord:
    timestamp_seconds: float
    killer: str | None
    victim: str | None
    weapon: str | None
    headshot: bool


@dataclass
class RoundRecord:
    round_number: int
    start_seconds: float
    end_seconds: float | None
    score_text: str | None
    spike_planted: bool


@dataclass
class ProcessOutput:
    duration_seconds: float
    fps: float
    frame_count: int
    detections: list[DetectionRecord] = field(default_factory=list)
    killfeed: list[KillfeedRecord] = field(default_factory=list)
    rounds: list[RoundRecord] = field(default_factory=list)


ProgressCallback = Callable[[float, str], None]


class VideoProcessor:
    def __init__(
        self,
        settings: Settings,
        detector: BaseDetector,
        ocr: OcrEngine | None = None,
        game_map: GameMap | None = None,
        calibration: MinimapCalibration | None = None,
    ) -> None:
        self.settings = settings
        self.detector = detector
        self.ocr = ocr
        self.game_map = game_map
        self.calibration = calibration or DEFAULT_CALIBRATION

    def process(
        self, video_path: str, progress_cb: ProgressCallback | None = None
    ) -> ProcessOutput:
        import cv2  # lazy heavy import

        cap = cv2.VideoCapture(video_path)
        if not cap.isOpened():
            raise RuntimeError(f"Could not open video: {video_path}")

        fps = cap.get(cv2.CAP_PROP_FPS) or 30.0
        frame_count = int(cap.get(cv2.CAP_PROP_FRAME_COUNT) or 0)
        duration = frame_count / fps if fps else 0.0
        stride = max(1, self.settings.frame_sample_stride)
        max_frames = self.settings.max_frames or float("inf")

        out = ProcessOutput(duration_seconds=duration, fps=fps, frame_count=frame_count)
        segmenter = _RoundSegmenter()

        last_self_pos: tuple[float, float] | None = None
        last_self_ts = -999.0
        processed = 0
        frame_idx = -1

        try:
            while True:
                grabbed = cap.grab()
                if not grabbed:
                    break
                frame_idx += 1
                if frame_idx % stride != 0:
                    continue
                ok, frame = cap.retrieve()
                if not ok:
                    continue
                timestamp = frame_idx / fps if fps else float(frame_idx)
                h, w = frame.shape[:2]

                raw = self.detector.detect(frame, frame_idx, timestamp)

                # Resolve the player's own minimap position first this frame.
                for det in raw:
                    if parse_label(det.label).kind == "mm_self":
                        cx, cy = det.center
                        coords = self.calibration.to_map_coords(cx, cy, w, h)
                        if coords is not None:
                            last_self_pos = coords
                            last_self_ts = timestamp

                for det in raw:
                    parsed = parse_label(det.label)
                    if parsed.kind == "mm_self":
                        continue
                    record = self._build_detection(
                        det, parsed, timestamp, frame_idx, w, h, last_self_pos, last_self_ts
                    )
                    if record is not None:
                        out.detections.append(record)

                # OCR HUD periodically (every ~1s of video) to limit cost.
                if self.ocr is not None and self.ocr.ready and int(timestamp) != int(
                    (frame_idx - stride) / fps if fps else 0
                ):
                    self._read_hud(frame, timestamp, segmenter, out)

                processed += 1
                if progress_cb and frame_count:
                    progress_cb(
                        min(frame_idx / frame_count, 0.99),
                        f"frame {frame_idx}/{frame_count}",
                    )
                if processed >= max_frames:
                    logger.info("Reached max_frames cap (%s).", max_frames)
                    break
        finally:
            cap.release()

        out.rounds = segmenter.finalize(duration)
        if not out.rounds:
            out.rounds = [RoundRecord(1, 0.0, duration, None, False)]
        logger.info(
            "Processed %s sampled frames: %s detections, %s killfeed, %s rounds.",
            processed, len(out.detections), len(out.killfeed), len(out.rounds),
        )
        if progress_cb:
            progress_cb(1.0, "done")
        return out

    def _build_detection(
        self, det, parsed, timestamp, frame_idx, w, h, last_self_pos, last_self_ts
    ) -> DetectionRecord | None:
        team = Team.ENEMY if parsed.is_enemy else Team.ALLY
        map_x = map_y = None
        callout = None
        source = DetectionSource.VIEWPORT

        if parsed.kind == "mm_enemy":
            source = DetectionSource.MINIMAP
            cx, cy = det.center
            coords = self.calibration.to_map_coords(cx, cy, w, h)
            if coords is None:
                return None  # marker outside the minimap ROI; ignore.
            map_x, map_y = coords
        else:
            # Viewport sighting: approximate location by the player's own
            # position (engagements happen near the player). Only use a recent
            # fix to avoid stale attribution.
            if last_self_pos is not None and (timestamp - last_self_ts) <= 3.0:
                map_x, map_y = last_self_pos

        if self.game_map is not None and map_x is not None:
            nearest = self.game_map.nearest_callout(map_x, map_y)
            callout = nearest.name if nearest else None

        return DetectionRecord(
            timestamp_seconds=round(timestamp, 3),
            frame_number=frame_idx,
            agent_name=parsed.agent,
            team=team,
            source=source,
            confidence=round(float(det.confidence), 4),
            map_x=map_x,
            map_y=map_y,
            callout=callout,
            bbox=det.bbox,
        )

    def _read_hud(self, frame, timestamp, segmenter, out: ProcessOutput) -> None:
        timer = self.ocr.read_timer(frame)
        score = self.ocr.read_score(frame)
        segmenter.update(timestamp, timer, score)
        for line in self.ocr.read_killfeed(frame):
            out.killfeed.append(
                KillfeedRecord(
                    timestamp_seconds=round(timestamp, 3),
                    killer=line.killer,
                    victim=line.victim,
                    weapon=line.weapon,
                    headshot=line.headshot,
                )
            )


class _RoundSegmenter:
    """Segments rounds from timer resets.

    A jump of the round timer back upward (e.g. buy phase begins) marks the
    boundary between rounds. Without timer OCR this stays empty and the caller
    falls back to a single whole-video round.
    """

    def __init__(self) -> None:
        self._rounds: list[RoundRecord] = []
        self._prev_timer: float | None = None
        self._current_start = 0.0
        self._current_score: str | None = None

    def update(self, timestamp: float, timer: float | None, score: str | None) -> None:
        if score is not None:
            self._current_score = score
        if timer is None:
            return
        if self._prev_timer is not None and timer - self._prev_timer > 30.0:
            self._rounds.append(
                RoundRecord(
                    round_number=len(self._rounds) + 1,
                    start_seconds=self._current_start,
                    end_seconds=timestamp,
                    score_text=self._current_score,
                    spike_planted=False,
                )
            )
            self._current_start = timestamp
        self._prev_timer = timer

    def finalize(self, duration: float) -> list[RoundRecord]:
        if self._prev_timer is not None:
            self._rounds.append(
                RoundRecord(
                    round_number=len(self._rounds) + 1,
                    start_seconds=self._current_start,
                    end_seconds=duration,
                    score_text=self._current_score,
                    spike_planted=False,
                )
            )
        return self._rounds
