"""Health and system-info endpoints."""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Response

from ... import __version__
from ...config import Settings
from ...schemas import CalibrationSettings, HealthOut, SystemInfo
from ...services import calibration_store
from ...services.pipeline import _get_detector, _get_ocr
from ...vision import multistage
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


# ---- Learned templates (what the detector knows from your training) ------
@router.get("/system/templates")
def get_templates(settings: Settings = Depends(get_settings_dep)) -> dict:
    """List every patch the user has taught, split into enemy / false."""
    t = multistage.list_templates(settings)
    return {
        "enemy": t["enemy"],
        "false": t["false"],
        "enemy_count": len(t["enemy"]),
        "false_count": len(t["false"]),
        "active_cap": settings.detection_max_templates,
    }


@router.get("/system/templates/{label}/{name}")
def get_template_image(
    label: str, name: str, settings: Settings = Depends(get_settings_dep)
) -> Response:
    """Serve a taught patch as a magnified PNG so it's visible in the gallery."""
    import cv2

    path = multistage.template_path(settings, label, name)
    if path is None:
        raise HTTPException(status_code=404, detail="Template not found.")
    img = cv2.imread(str(path), cv2.IMREAD_GRAYSCALE)
    if img is None:
        raise HTTPException(status_code=404, detail="Template unreadable.")
    big = cv2.resize(img, (64, 64), interpolation=cv2.INTER_NEAREST)
    ok, buf = cv2.imencode(".png", big)
    if not ok:
        raise HTTPException(status_code=500, detail="PNG encoding failed.")
    return Response(content=buf.tobytes(), media_type="image/png")


@router.delete("/system/templates/{label}/{name}")
def delete_template_image(
    label: str, name: str, settings: Settings = Depends(get_settings_dep)
) -> dict:
    """Forget one taught patch (e.g. a mistake)."""
    if not multistage.delete_template(settings, label, name):
        raise HTTPException(status_code=404, detail="Template not found.")
    return {"deleted": True, "label": label, "name": name}


@router.delete("/system/templates")
def clear_templates(settings: Settings = Depends(get_settings_dep)) -> dict:
    """Forget everything the detector learned from training."""
    return {"deleted": multistage.clear_templates(settings)}
