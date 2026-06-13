import { useEffect, useState } from "react";
import { api } from "../api/client.js";

const DEFAULTS = { x_frac: 0.012, y_frac: 0.012, w_frac: 0.182, h_frac: 0.324, sat_min: 150, val_min: 150 };

export default function SettingsView({ info, calibrationRound }) {
  const [cal, setCal] = useState(DEFAULTS);
  const [committed, setCommitted] = useState(DEFAULTS);
  const [mask, setMask] = useState(false);
  const [t, setT] = useState(2);

  useEffect(() => {
    const id = setTimeout(() => setCommitted(cal), 200);
    return () => clearTimeout(id);
  }, [cal]);

  const set = (k) => (e) => setCal({ ...cal, [k]: Number(e.target.value) });
  const round = calibrationRound;
  const src = round ? api.minimapPreviewUrl(round.id, { t, mask, ...committed }) : null;

  return (
    <div className="view settings-view">
      <div className="panel">
        <div className="panel-head"><h3>SYSTEM</h3></div>
        <div className="panel-body">
          <dl className="kv wide">
            <div><dt>Detector</dt><dd>{info?.detector_backend} {info?.detector_ready ? "✓" : "(fallback)"}</dd></div>
            <div><dt>OCR</dt><dd>{info?.ocr_backend} {info?.ocr_ready ? "✓" : "(off)"}</dd></div>
            <div><dt>Version</dt><dd>{info?.version}</dd></div>
            <div><dt>Maps</dt><dd>{(info?.available_maps || []).length}</dd></div>
          </dl>
          <p className="muted small">
            Detector is configured via <code>VVC_DETECTOR_BACKEND</code> (mock / minimap / yolo).
            Use <code>minimap</code> for real footage and calibrate the box below.
          </p>
        </div>
      </div>

      <div className="panel">
        <div className="panel-head"><h3>MINIMAP CALIBRATION</h3></div>
        <div className="panel-body calib">
          {!round ? (
            <div className="empty">Upload/analyze a round first, then calibrate against it here.</div>
          ) : (
            <>
              <div className="calib-preview">
                <img src={src} alt="calibration preview" />
              </div>
              <div className="calib-controls">
                {["x_frac", "y_frac", "w_frac", "h_frac"].map((k) => (
                  <label key={k} className="slider">
                    <span>{k} <em>{cal[k].toFixed(3)}</em></span>
                    <input type="range" min="0" max={k.startsWith("w") || k.startsWith("h") ? 0.6 : 0.5}
                           step="0.002" value={cal[k]} onChange={set(k)} />
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
                  <pre>{[
                    `VVC_MINIMAP_X_FRAC=${committed.x_frac}`,
                    `VVC_MINIMAP_Y_FRAC=${committed.y_frac}`,
                    `VVC_MINIMAP_W_FRAC=${committed.w_frac}`,
                    `VVC_MINIMAP_H_FRAC=${committed.h_frac}`,
                  ].join("\n")}</pre>
                </div>
              </div>
            </>
          )}
        </div>
      </div>
    </div>
  );
}
