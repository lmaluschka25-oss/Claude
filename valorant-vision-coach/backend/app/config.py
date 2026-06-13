"""Application configuration.

All settings are environment-overridable (prefix ``VVC_``) and have sane
defaults so the app boots with zero configuration for local development.
"""
from __future__ import annotations

from functools import lru_cache
from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

# Repository layout anchors.
BACKEND_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = BACKEND_DIR / "data"


class Settings(BaseSettings):
    """Typed application settings, loaded from env / ``.env``."""

    model_config = SettingsConfigDict(
        env_prefix="VVC_",
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # ---- General ---------------------------------------------------------
    app_name: str = "Valorant Vision Coach"
    environment: str = "development"
    log_level: str = "INFO"
    cors_origins: list[str] = Field(
        default_factory=lambda: ["http://localhost:5173", "http://localhost:3000"]
    )

    # ---- Storage ---------------------------------------------------------
    database_url: str = f"sqlite:///{(DATA_DIR / 'vision_coach.db').as_posix()}"
    upload_dir: Path = DATA_DIR / "uploads"
    maps_dir: Path = DATA_DIR / "maps"
    models_dir: Path = DATA_DIR / "models"
    max_upload_mb: int = 4096  # 4 GB ceiling for a full-match recording.

    # ---- Vision pipeline -------------------------------------------------
    # Which detector backend to use: "yolo" (real model) or "mock" (synthetic,
    # for tests / demos without trained weights).
    detector_backend: str = "yolo"
    yolo_model_path: Path = DATA_DIR / "models" / "valorant.pt"
    yolo_confidence: float = 0.35
    yolo_iou: float = 0.45
    yolo_device: str = "auto"  # "auto" | "cpu" | "cuda:0" ...

    # Sample one frame every N source frames. Higher = faster, coarser timing.
    frame_sample_stride: int = 6
    # Hard cap on processed frames (safety valve for very long recordings).
    max_frames: int = 0  # 0 = unlimited

    # OCR backend for killfeed / scoreboard / timer: "easyocr" | "tesseract" | "off".
    ocr_backend: str = "easyocr"

    # ---- Minimap calibration (color-based minimap detector) -------------
    # The minimap rectangle as fractions of the frame, plus per-side
    # rotation/flip. Tune these to your HUD with the /minimap-preview endpoint.
    minimap_x_frac: float = 0.02
    minimap_y_frac: float = 0.046
    minimap_w_frac: float = 0.224
    minimap_h_frac: float = 0.396
    minimap_rotation: int = 0
    minimap_flip_x: bool = False
    # Enemy markers are matched by an HSV hue band [hue_min, hue_max] (OpenCV
    # hue 0–179). Valorant shows enemies in different tones per setup — many are
    # YELLOW (hue ~18–45), some red. Default to yellow; tune the band live in the
    # Settings tab with the color mask until only enemy dots light up.
    minimap_enemy_hue_min: int = 18
    minimap_enemy_hue_max: int = 45
    minimap_enemy_sat_min: int = 160
    minimap_enemy_val_min: int = 150
    minimap_min_area: float = 4.0
    minimap_max_area: float = 260.0

    # ---- Advanced detection / analysis settings (user-tunable, persisted) ---
    # Each maps to a real parameter and measurably changes analysis output.
    analysis_interval: float = 0.5  # seconds between analyzed frames
    confidence_threshold: float = 0.0  # drop enemy detections below this
    pattern_weight: float = 0.34  # momentum weight in next-round prediction
    memory_weight: float = 0.34  # base-rate (whole-match) weight in prediction
    recommendation_min_confidence: float = 0.0  # below → "need more data"
    timeline_detail: int = 12  # max timeline events shown

    # ---- Analysis defaults ----------------------------------------------
    # A sighting older than this (seconds) is considered stale and dropped
    # from the "last known position" view. Overridable per request.
    sighting_ttl_seconds: float = 12.0
    # Approximate player movement speed in *normalized map units* per second
    # (the map is normalized to a 0..1 square). Used to bound rotation reach.
    movement_speed_norm: float = 0.13
    # Site-pressure radius (normalized units) around a site centroid.
    site_pressure_radius: float = 0.22

    def minimap_calibration(self):
        """Build a MinimapCalibration from the configured fractions."""
        from .vision.calibration import MinimapCalibration

        return MinimapCalibration(
            x_frac=self.minimap_x_frac,
            y_frac=self.minimap_y_frac,
            w_frac=self.minimap_w_frac,
            h_frac=self.minimap_h_frac,
            rotation=self.minimap_rotation,
            flip_x=self.minimap_flip_x,
        )

    @property
    def sqlite_path(self) -> Path | None:
        if self.database_url.startswith("sqlite:///"):
            return Path(self.database_url.replace("sqlite:///", "", 1))
        return None

    def ensure_dirs(self) -> None:
        """Create writable directories the app depends on."""
        for path in (DATA_DIR, self.upload_dir, self.models_dir):
            path.mkdir(parents=True, exist_ok=True)
        if self.sqlite_path is not None:
            self.sqlite_path.parent.mkdir(parents=True, exist_ok=True)


@lru_cache
def get_settings() -> Settings:
    """Return a cached settings singleton."""
    settings = Settings()
    settings.ensure_dirs()
    return settings


settings = get_settings()
