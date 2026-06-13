"""Health and system-info endpoints."""
from __future__ import annotations

from fastapi import APIRouter, Depends

from ... import __version__
from ...config import Settings
from ...schemas import CalibrationSettings, HealthOut, SystemInfo
from ...services import calibration_store
from ...services.pipeline import _get_detector, _get_ocr
from ...vision.maps import list_maps
from ..deps import get_settings_dep

router = APIRouter(tags=["system"])


@router.get("/health", response_model=HealthOut)
def health() -> HealthOut:
    return HealthOut(status="ok", version=__version__)


@router.get("/system/info", response_model=SystemInfo)
def system_info(settings: Settings = Depends(get_settings_dep)) -> SystemInfo:
    detector = _get_detector(settings.detector_backend)
    ocr = _get_ocr(settings.ocr_backend)
    return SystemInfo(
        app_name=settings.app_name,
        version=__version__,
        environment=settings.environment,
        detector_backend=settings.detector_backend,
        detector_ready=getattr(detector, "ready", False),
        ocr_backend=settings.ocr_backend,
        ocr_ready=getattr(ocr, "ready", False),
        available_maps=list_maps(),
    )


@router.get("/system/calibration")
def get_calibration(settings: Settings = Depends(get_settings_dep)) -> dict:
    """Current effective minimap calibration (saved overrides over defaults)."""
    return calibration_store.load(settings)


@router.put("/system/calibration")
def put_calibration(
    body: CalibrationSettings, settings: Settings = Depends(get_settings_dep)
) -> dict:
    """Persist calibration changes (applies to future processing + previews)."""
    return calibration_store.save(settings, body.model_dump(exclude_none=True))


@router.delete("/system/calibration")
def reset_calibration(settings: Settings = Depends(get_settings_dep)) -> dict:
    """Reset all detection settings to defaults (auto color, etc.)."""
    return calibration_store.reset(settings)
