"""Multi-stage minimap enemy detector.

Colour is only a weak hint (≤20%). A candidate becomes a confirmed enemy only
when several independent cues agree:

* **colour**   ≤0.20 — rejects teammate-green outright, weakly favours the
  configured/known enemy tone.
* **shape**    ≤0.25 — circularity, solidity, aspect ratio and size of the blob.
* **template** ≤0.35 — normalized cross-correlation against learned enemy ping
  templates (with a shape-derived prior at cold start), minus a penalty for
  matching known false-positive templates.
* **motion**   ≤0.20 — persistence across frames; single-frame blips are dropped.

Total ≥ ``detection_confirm_threshold`` (default 0.62) ⇒ confirmed enemy. The
templates are learnable: confirmed/false patches are saved and reused.
"""
from __future__ import annotations

import math
from collections import deque
from pathlib import Path

import numpy as np

from ..config import Settings
from ..logging_config import get_logger
from .calibration import MinimapCalibration
from .detector import BaseDetector, RawDetection

logger = get_logger(__name__)

# Confidence caps per cue (the spec's weights).
W_COLOR, W_SHAPE, W_TEMPLATE, W_MOTION = 0.20, 0.25, 0.35, 0.20
TEMPLATE_SIZE = 24  # normalized patch size for template matching


def templates_dir(settings: Settings) -> Path:
    return settings.upload_dir.parent / "templates"


def _enemy_hue(h: int, color_mode: str, hue_min: int, hue_max: int) -> bool:
    mode = (color_mode or "auto").lower()
    if mode == "red":
        return h <= 12 or h >= 165
    if mode == "yellow":
        return 13 <= h <= 45
    if mode == "custom":
        return hue_min <= h <= hue_max
    # auto: red OR yellow/orange
    return h <= 12 or h >= 165 or 13 <= h <= 45


def _is_teammate_hue(h: int) -> bool:
    # Valorant teammates are green/cyan — never enemies.
    return 42 <= h <= 100


class MultiStageMinimapDetector(BaseDetector):
    ready = True

    def __init__(self, settings: Settings, calibration: MinimapCalibration | None = None) -> None:
        self.settings = settings
        self.calibration = calibration or settings.minimap_calibration()
        self.color_mode = getattr(settings, "minimap_color_mode", "auto")
        self.hue_min = settings.minimap_enemy_hue_min
        self.hue_max = settings.minimap_enemy_hue_max
        self.sat_floor = max(50, settings.minimap_enemy_sat_min - 70)
        self.val_floor = max(70, settings.minimap_enemy_val_min - 60)
        self.min_area = settings.minimap_min_area
        self.max_area = settings.minimap_max_area
        self.threshold = getattr(settings, "detection_confirm_threshold", 0.62)
        self._history: deque = deque(maxlen=6)  # recent frames' centroids (ROI px)
        self._enemy_tmpl, self._false_tmpl = self._load_templates()

    def reset(self) -> None:
        self._history.clear()

    # ---- templates (learnable) ------------------------------------------
    def _load_templates(self):
        import cv2

        def load(sub):
            d = templates_dir(self.settings) / sub
            out = []
            if d.exists():
                for p in sorted(d.glob("*.png"))[:60]:
                    img = cv2.imread(str(p), cv2.IMREAD_GRAYSCALE)
                    if img is not None:
                        out.append(cv2.resize(img, (TEMPLATE_SIZE, TEMPLATE_SIZE)))
            return out

        return load("enemy"), load("false")

    # ---- candidate generation -------------------------------------------
    def _roi(self, frame):
        h, w = frame.shape[:2]
        rx, ry, rw, rh = self.calibration.roi_pixels(w, h)
        return rx, ry, rw, rh, frame[ry : ry + rh, rx : rx + rw]

    def _candidates(self, roi):
        """Color-agnostic marker candidates: vivid, compact blobs."""
        import cv2

        hsv = cv2.cvtColor(roi, cv2.COLOR_BGR2HSV)
        sat = hsv[:, :, 1]
        val = hsv[:, :, 2]
        vivid = ((sat >= self.sat_floor) & (val >= self.val_floor)).astype(np.uint8) * 255
        kernel = np.ones((2, 2), np.uint8)
        vivid = cv2.morphologyEx(vivid, cv2.MORPH_OPEN, kernel)
        vivid = cv2.morphologyEx(vivid, cv2.MORPH_CLOSE, kernel)
        contours, _ = cv2.findContours(vivid, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        gray = cv2.cvtColor(roi, cv2.COLOR_BGR2GRAY)
        cands = []
        for c in contours:
            area = cv2.contourArea(c)
            if not (self.min_area <= area <= self.max_area * 1.6):
                continue
            x, y, bw, bh = cv2.boundingRect(c)
            cx, cy = x + bw / 2.0, y + bh / 2.0
            cands.append({"contour": c, "area": area, "x": x, "y": y, "w": bw, "h": bh,
                          "cx": cx, "cy": cy, "hsv": hsv, "gray": gray})
        return cands

    # ---- per-cue scoring -------------------------------------------------
    def _color_cue(self, cand):
        # Median hue over the *vivid* pixels of the blob (ignore dark edge
        # pixels, which would skew a plain mean toward the wrong hue).
        sub = cand["hsv"][cand["y"] : cand["y"] + cand["h"], cand["x"] : cand["x"] + cand["w"]]
        sel = (sub[:, :, 1] >= self.sat_floor) & (sub[:, :, 2] >= self.val_floor)
        if not sel.any():
            return W_COLOR * 0.3, "weak (no vivid pixels)"
        h = int(np.median(sub[:, :, 0][sel]))
        if _is_teammate_hue(h):
            return None, f"teammate hue {h}"  # exclude allies entirely
        if _enemy_hue(h, self.color_mode, self.hue_min, self.hue_max):
            return W_COLOR, f"enemy hue {h}"
        return W_COLOR * 0.4, f"hue {h} (weak)"

    def _shape_quality(self, cand):
        import cv2

        c = cand["contour"]
        area = cand["area"]
        peri = cv2.arcLength(c, True)
        circ = (4 * math.pi * area / (peri * peri)) if peri > 0 else 0.0
        hull = cv2.convexHull(c)
        hull_area = cv2.contourArea(hull) or 1.0
        solidity = area / hull_area
        aspect = cand["w"] / max(cand["h"], 1)
        aspect_ok = 1.0 - min(1.0, abs(1.0 - aspect))
        size_ok = 1.0 if self.min_area <= area <= self.max_area else 0.5
        q = 0.30 * min(1.0, circ / 0.85) + 0.30 * min(1.0, solidity) + 0.20 * aspect_ok + 0.20 * size_ok
        return max(0.0, min(1.0, q)), {"circ": round(circ, 2), "solidity": round(solidity, 2),
                                       "aspect": round(aspect, 2)}

    def _template_cue(self, cand, shape_q):
        import cv2

        x, y, w, h = cand["x"], cand["y"], cand["w"], cand["h"]
        patch = cand["gray"][y : y + h, x : x + w]
        if patch.size == 0:
            return W_TEMPLATE * 0.5 * shape_q, "no patch", 0.0
        patch = cv2.resize(patch, (TEMPLATE_SIZE, TEMPLATE_SIZE))

        def best(tmpls):
            b = 0.0
            for t in tmpls:
                r = cv2.matchTemplate(patch, t, cv2.TM_CCOEFF_NORMED)
                b = max(b, float(r.max()))
            return b

        if not self._enemy_tmpl:
            # Cold start: shape-derived prior so good blobs can still confirm.
            return W_TEMPLATE * 0.85 * shape_q, "prior (no templates)", 0.0
        be = best(self._enemy_tmpl)
        bf = best(self._false_tmpl) if self._false_tmpl else 0.0
        score = W_TEMPLATE * max(0.0, min(1.0, (be - 0.2) / 0.7))
        penalty = 0.25 * max(0.0, min(1.0, (bf - 0.2) / 0.7))
        return score, f"tmpl {be:.2f}", penalty

    def _motion_cue(self, cand):
        radius = 0.05 * max(1, self.calibration.w_frac * 1000)  # rough px radius
        seen = 0
        for pts in self._history:
            if any(math.hypot(cand["cx"] - px, cand["cy"] - py) <= radius for px, py in pts):
                seen += 1
        return W_MOTION * min(seen, 3) / 3.0, seen

    def _score_all(self, roi):
        cands = self._candidates(roi)
        scored = []
        for cand in cands:
            color = self._color_cue(cand)
            if color is None or color[0] is None:
                continue  # teammate / excluded
            shape_q, shape_meta = self._shape_quality(cand)
            shape = W_SHAPE * shape_q
            tmpl, tmpl_reason, penalty = self._template_cue(cand, shape_q)
            motion, seen = self._motion_cue(cand)
            total = max(0.0, color[0] + shape + tmpl + motion - penalty)
            cand["scores"] = {
                "color": round(color[0], 3), "shape": round(shape, 3),
                "template": round(tmpl, 3), "motion": round(motion, 3),
                "penalty": round(penalty, 3), "total": round(total, 3),
                "frames_seen": seen,
            }
            cand["reasons"] = {"color": color[1], "shape": shape_meta, "template": tmpl_reason}
            cand["total"] = total
            scored.append(cand)
        # Update motion history AFTER scoring this frame.
        self._history.append([(c["cx"], c["cy"]) for c in cands])
        return scored

    # ---- public API ------------------------------------------------------
    def find_enemies(self, frame):
        rx, ry, _, _, roi = self._roi(frame)
        if roi.size == 0:
            return []
        out = []
        for cand in self._score_all(roi):
            if cand["total"] < self.threshold:
                continue
            cx, cy = rx + cand["cx"], ry + cand["cy"]
            out.append(RawDetection("mm_enemy", round(cand["total"], 3),
                                    (cx - 5, cy - 5, 10, 10), meta=cand["scores"]))
        return out

    def detect(self, frame, frame_index, timestamp):
        return self.find_enemies(frame)

    def debug_candidates(self, frame):
        """All candidates with scores + confirmed flag (for the debug overlay)."""
        rx, ry, _, _, roi = self._roi(frame)
        if roi.size == 0:
            return rx, ry, []
        items = []
        for cand in self._score_all(roi):
            items.append({
                "cx": rx + cand["cx"], "cy": ry + cand["cy"],
                "w": cand["w"], "h": cand["h"],
                "total": cand["total"], "confirmed": cand["total"] >= self.threshold,
                "scores": cand["scores"], "reasons": cand["reasons"],
            })
        return rx, ry, items

    def teach(self, frame, px: float, py: float, label: str) -> bool:
        """Save a 24×24 grayscale patch around (px,py) as an enemy/false template."""
        import cv2

        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        h, w = gray.shape[:2]
        half = TEMPLATE_SIZE // 2
        x0, y0 = int(px) - half, int(py) - half
        x0 = max(0, min(x0, w - TEMPLATE_SIZE))
        y0 = max(0, min(y0, h - TEMPLATE_SIZE))
        patch = gray[y0 : y0 + TEMPLATE_SIZE, x0 : x0 + TEMPLATE_SIZE]
        if patch.size == 0:
            return False
        sub = "false" if label == "false" else "enemy"
        d = templates_dir(self.settings) / sub
        d.mkdir(parents=True, exist_ok=True)
        n = len(list(d.glob("*.png")))
        cv2.imwrite(str(d / f"{n:04d}.png"), cv2.resize(patch, (TEMPLATE_SIZE, TEMPLATE_SIZE)))
        self._enemy_tmpl, self._false_tmpl = self._load_templates()
        return True
