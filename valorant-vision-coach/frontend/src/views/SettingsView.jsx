import { useEffect, useState } from "react";
import { api } from "../api/client.js";

const DEFAULTS = {
  x_frac: 0.02, y_frac: 0.046, w_frac: 0.224, h_frac: 0.396,
  hue_min: 18, hue_max: 45, sat_min: 90, val_min: 120,
};
const ROI = [
  ["x_frac", 0.6, 0.002], ["y_frac", 0.6, 0.002], ["w_frac", 0.7, 0.002], ["h_frac", 0.7, 0.002],
];
const COLOR = [
  ["hue_min", 179, 1], ["hue_max", 179, 1], ["sat_min", 255, 1], ["val_min", 255, 1],
];

export default function SettingsView({ info, calibrationRound }) {
  const [cal, setCal] = useState(DEFAULTS);
  const [committed, setCommitted] = useState(DEFAULTS);
  const [mask, setMask] = useState(true);
  const [t, setT] = useState(2);

  useEffect(() => {
    const id = setTimeout(() => setCommitted(cal), 200);
    return () => clearTimeout(id);
  }, [cal]);

  const set = (k) => (e) => setCal({ ...cal, [k]: Number(e.target.value) });
  const round = calibrationRound;
  const src = round ? api.minimapPreviewUrl(round.id, { t, mask, ...committed }) : null;
  const envLines = [
    `VVC_MINIMAP_X_FRAC=${committed.x_frac}`,
    `VVC_MINIMAP_Y_FRAC=${committed.y_frac}`,
    `VVC_MINIMAP_W_FRAC=${committed.w_frac}`,
    `VVC_MINIMAP_H_FRAC=${committed.h_frac}`,
    `VVC_MINIMAP_ENEMY_HUE_MIN=${committed.hue_min}`,
    `VVC_MINIMAP_ENEMY_HUE_MAX=${committed.hue_max}`,
    `VVC_MINIMAP_ENEMY_SAT_MIN=${committed.sat_min}`,
    `VVC_MINIMAP_ENEMY_VAL_MIN=${committed.val_min}`,
  ].join("\n");

  return (
    <div className="view settings-view">
      <div className="panel">
        <div className="panel-head"><h3>SYSTEM</h3></div>
        <div className="panel-body">
          <dl className="kv wide">
            <div><dt>Detector</dt><dd>{info?.detector_backend} {info?.detector_ready ? "✓" : "(fallback)"}</dd></div>
            <div><dt>OCR</dt><dd>{info?.ocr_backend} {info?.ocr_ready ? "✓" : "(off)"}</dd></div>
            <div><dt>Version</dt><dd>{info?.version}</dd></div>
          </dl>
          <div className="notice" style={{ marginTop: 10 }}>
            <b>For correct positions:</b> set Valorant's minimap to <b>Fixed</b> (Settings → General →
            <i> Minimap Rotation: Fixed</i>) and <i>Keep Player Centered: Off</i> so the minimap shows the
            whole map in one orientation. A rotating / player-centered minimap can't give absolute
            enemy positions.
          </div>
        </div>
      </div>

      <div className="panel">
        <div className="panel-head"><h3>MINIMAP CALIBRATION</h3></div>
        <div className="panel-body calib">
          {!round ? (
            <div className="empty">Upload/analyze a round first, then calibrate against it here.</div>
          ) : (
            <>
              <div className="calib-preview"><img src={src} alt="calibration preview" /></div>
              <div className="calib-controls">
                <div className="sub-label">Box (green) — put it on the minimap</div>
                {ROI.map(([k, max, step]) => (
                  <label key={k} className="slider">
                    <span>{k} <em>{cal[k].toFixed(3)}</em></span>
                    <input type="range" min="0" max={max} step={step} value={cal[k]} onChange={set(k)} />
                  </label>
                ))}
                <div className="sub-label">Enemy color — mask should hit only enemy dots</div>
                {COLOR.map(([k, max, step]) => (
                  <label key={k} className="slider">
                    <span>{k} <em>{cal[k]}</em></span>
                    <input type="range" min="0" max={max} step={step} value={cal[k]} onChange={set(k)} />
                  </label>
                ))}
                <label className="slider">
                  <span>frame time <em>{t}s</em></span>
                  <input type="range" min="0" max="60" step="1" value={t} onChange={(e) => setT(Number(e.target.value))} />
                </label>
                <label className="check-row">
                  <input type="checkbox" checked={mask} onChange={(e) => setMask(e.target.checked)} /> Color mask
                </label>
                <div className="env-out">
                  <div className="sub-label">Copy into .env</div>
                  <pre>{envLines}</pre>
                </div>
              </div>
            </>
          )}
        </div>
      </div>
    </div>
  );
}
