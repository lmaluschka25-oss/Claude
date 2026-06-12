"""Shared FastAPI dependencies."""
from __future__ import annotations

from ..config import Settings, get_settings
from ..database import get_session  # re-exported for route modules

__all__ = ["get_session", "get_settings_dep"]


def get_settings_dep() -> Settings:
    return get_settings()
