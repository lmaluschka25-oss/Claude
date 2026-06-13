"""Frame-by-frame analysis of a single recording (one round).

Reads a recording with OpenCV, samples frames, runs the detector and (optional)
OCR, projects minimap markers into normalized map coordinates, resolves
callouts, and returns plain dataclass records: detections, utilities, killfeed.
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
class UtilityRecord:
    timestamp_seconds: float
    kind: str
    agent_name: str | None
    map_x: float | None
    map_y: float | None
    callout: str | None
    confidence: float


@dataclass
class KillfeedRecord:
    timestamp_seconds: float
    killer: str | None
    victim: str | None
    weapon: str | None
    headshot: bool
    killer_team: Team = Team.UNKNOWN


@dataclass
class ProcessOutput:
    duration_seconds: float
    fps: float
    frame_count: int
    detections: list[DetectionRecord] = field(default_factory=list)
    utilities: list[UtilityRecord] = field(default_factory=list)
    killfeed: list[KillfeedRecord] = field(default_factory=list)
    score_text: str | None = None
    round_time: str | None = None
    spike_planted: bool = False


ProgressCallback = Callable[[float, str], None]


class VideoProcessor:
    def __init__(
        self,
        settings: Settings,
        detector: BaseDetector,
        ocr: OcrEngine | None = None,
        game_map: GameMap | None = None,
        calibration: MinimapCalibration | None = None,
        analysis_interval: float | None = None,
    ) -> None:
        self.settings = settings
        self.detector = detector
        self.ocr = ocr
        self.game_map = game_map
        self.calibration = calibration or DEFAULT_CALIBRATION
        self.analysis_interval = analysis_interval

    def _callout(self, x: float | None, y: float | None) -> str | None:
        if self.game_map is None or x is None:
            return None
        nearest = self.game_map.nearest_callout(x, y)
        return nearest.name if nearest else None

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
        if self.analysis_interval and self.analysis_interval > 0 and fps:
            stride = max(1, round(self.analysis_interval * fps))
        else:
            stride = max(1, self.settings.frame_sample_stride)
        max_frames = self.settings.max_frames or float("inf")

        out = ProcessOutput(duration_seconds=duration, fps=fps, frame_count=frame_count)
        last_self: tuple[float, float] | None = None
        last_self_ts = -999.0
        processed = 0
        frame_idx = -1

        try:
            while True:
                if not cap.grab():
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

                # Resolve the player's own minimap position first, and record it
                # as a "You" marker (ally team) for the minimap view.
                for det in raw:
                    if parse_label(det.label).kind == "mm_self":
                        coords = self.calibration.to_map_coords(*det.center, w, h)
                        if coords is not None:
                            last_self, last_self_ts = coords, timestamp
                            out.detections.append(
                                DetectionRecord(
                                    timestamp_seconds=round(timestamp, 3),
                                    frame_number=frame_idx,
                                    agent_name="You",
                                    team=Team.ALLY,
                                    source=DetectionSource.MINIMAP,
                                    confidence=0.99,
                                    map_x=coords[0],
                                    map_y=coords[1],
                                    callout=self._callout(*coords),
                                    bbox=det.bbox,
                                )
                            )

                for det in raw:
                    parsed = parse_label(det.label)
                    if parsed.kind == "mm_self":
                        continue
                    self._consume(det, parsed, timestamp, frame_idx, w, h, last_self, last_self_ts, out)

                if self.ocr is not None and self.ocr.ready:
                    self._read_hud(frame, timestamp, out)

                processed += 1
                if progress_cb and frame_count:
                    progress_cb(
                        min(frame_idx / frame_count, 0.99), f"frame {frame_idx}/{frame_count}"
                    )
                if processed >= max_frames:
                    break
        finally:
            cap.release()

        # webm/streamed files often report a wrong frame count — derive the real
        # duration from the frames we actually iterated.
        total = frame_idx + 1
        if total > 0 and fps:
            out.frame_count = total
            out.duration_seconds = round(total / fps, 3)

        logger.info(
            "Processed %s frames: %s detections, %s utilities, %s killfeed.",
            processed, len(out.detections), len(out.utilities), len(out.killfeed),
        )
        if progress_cb:
            progress_cb(1.0, "done")
        return out

    def _consume(self, det, parsed, timestamp, frame_idx, w, h, last_self, last_self_ts, out):
        if parsed.kind == "utility":
            coords = self.calibration.to_map_coords(*det.center, w, h)
            if coords is None and last_self is not None and (timestamp - last_self_ts) <= 3.0:
                coords = last_self
            mx, my = coords if coords else (None, None)
            out.utilities.append(
                UtilityRecord(
                    timestamp_seconds=round(timestamp, 3),
                    kind=parsed.util_kind or "other",
                    agent_name=parsed.agent,
                    map_x=mx,
                    map_y=my,
                    callout=self._callout(mx, my),
                    confidence=round(float(det.confidence), 4),
                )
            )
            return

        team = Team.ENEMY if parsed.is_enemy else Team.ALLY
        if parsed.kind in ("mm_enemy", "mm_ally"):
            source = DetectionSource.MINIMAP
            coords = self.calibration.to_map_coords(*det.center, w, h)
            if coords is None:
                return
            mx, my = coords
        else:  # viewport sighting — localize by the player's own position
            source = DetectionSource.VIEWPORT
            if last_self is not None and (timestamp - last_self_ts) <= 3.0:
                mx, my = last_self
            else:
                mx, my = None, None

        out.detections.append(
            DetectionRecord(
                timestamp_seconds=round(timestamp, 3),
                frame_number=frame_idx,
                agent_name=parsed.agent,
                team=team,
                source=source,
                confidence=round(float(det.confidence), 4),
                map_x=mx,
                map_y=my,
                callout=self._callout(mx, my),
                bbox=det.bbox,
            )
        )

    def _read_hud(self, frame, timestamp, out: ProcessOutput) -> None:
        if int(timestamp) == int(timestamp - 0.5):  # ~once per second of video
            return
        score = self.ocr.read_score(frame)
        if score:
            out.score_text = score
        timer = self.ocr.read_timer(frame)
        if timer is not None:
            out.round_time = f"{int(timer) // 60}:{int(timer) % 60:02d}"
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
