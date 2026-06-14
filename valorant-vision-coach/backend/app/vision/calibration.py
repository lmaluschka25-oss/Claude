"""Minimap calibration: mapping minimap pixels to normalized map coordinates.

Valorant draws the minimap in a screen corner. To turn a pixel on the minimap
into a ``[0,1]`` map coordinate we need a one-time calibration: the minimap's
rectangle within the frame, plus any rotation/flip the map applies per side.

Defaults below match a common 16:9 layout with the minimap in the top-left.
Override per recording via the calibration fields if your HUD differs.
"""
from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class MinimapCalibration:
    """Minimap region expressed as fractions of frame width/height.

    ``rotation`` is applied (degrees, clockwise, multiples of 90) and ``flip_x``
    mirrors horizontally — both let one calibration serve attacker/defender
    orientations without re-deriving the rectangle.
    """

    x_frac: float = 0.012
    y_frac: float = 0.012
    w_frac: float = 0.182
    h_frac: float = 0.324  # ~square region on a 16:9 frame
    rotation: int = 0
    flip_x: bool = False

    def roi_pixels(self, frame_w: int, frame_h: int) -> tuple[int, int, int, int]:
        """Return the minimap ROI as ``(x, y, w, h)`` in pixels."""
        x = int(self.x_frac * frame_w)
        y = int(self.y_frac * frame_h)
        w = int(self.w_frac * frame_w)
        h = int(self.h_frac * frame_h)
        return x, y, w, h

    def to_map_coords(
        self, px: float, py: float, frame_w: int, frame_h: int
    ) -> tuple[float, float] | None:
        """Convert a frame pixel inside the minimap ROI to normalized map coords.

        Returns ``None`` when the pixel falls outside the minimap rectangle.
        """
        x, y, w, h = self.roi_pixels(frame_w, frame_h)
        if w <= 0 or h <= 0:
            return None
        u = (px - x) / w
        v = (py - y) / h
        if not (-0.02 <= u <= 1.02 and -0.02 <= v <= 1.02):
            return None
        u = min(max(u, 0.0), 1.0)
        v = min(max(v, 0.0), 1.0)
        # Apply rotation (clockwise) then optional mirror.
        rot = self.rotation % 360
        if rot == 90:
            u, v = 1.0 - v, u
        elif rot == 180:
            u, v = 1.0 - u, 1.0 - v
        elif rot == 270:
            u, v = v, 1.0 - u
        if self.flip_x:
            u = 1.0 - u
        return u, v


DEFAULT_CALIBRATION = MinimapCalibration()
