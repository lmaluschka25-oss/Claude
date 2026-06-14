import { useCallback, useEffect, useState } from "react";
import { api } from "../api/client.js";
import { cx, pct } from "../util.js";

// One slider bound to a settings key.
function Slider({ s, set, k, label, min, max, step, fmt }) {
  const v = s[k];
  return (
    <label className="slider">
      <span>{label} <em>{fmt ? fmt(v) : v}</em></span>
      <input type="range" min={min} max={max} step={step} value={v ?? min}
             onChange={(e) => set(k, Number(e.target.value))} />
    </label>
  );
}

// Gallery of taught patches for one label. Module-level so it doesn't remount
// (and refetch thumbnails) on every settings change. The newest `cap` are the
// ones actually matched per frame; older ones are dimmed as "unused".
function Gallery({ label, names, cap, onDelete }) {
  if (names.length === 0) return <div className="tpl-gallery"><span className="muted small">none yet</span></div>;
  return (
    <div className="tpl-gallery">
      {names.map((name, i) => {
        const active = i >= names.length - cap;
        return (
          <div key={name} className={cx("tpl-thumb", !active && "inactive")}
               title={active ? `${label} template (in use)` : `${label} template (beyond cap — not matched)`}>
            <img src={api.templateUrl(label, name)} alt={`${label} ${name}`} />
            <button className="tpl-del" onClick={() => onDelete(label, name)} title="Forget this one">✕</button>
          </div>
        );
      })}
    </div>
  );
}

export default function SettingsView({ info, intelligence, calibrationRound, onReanalyze }) {
  const [s, setS] = useState(null);
  const [saved, setSaved] = useState(false);
  const [busy, setBusy] = useState(false);
  const [mask, setMask] = useState(true);
  const [t, setT] = useState(2);
  const [zoom, setZoom] = useState(true);
  const [teachLabel, setTeachLabel] = useState("enemy");
  const [pkey, setPkey] = useState(0);
  const [taught, setTaught] = useState(null);
  const [templates, setTemplates] = useState({ enemy: [], false: [], enemy_count: 0, false_count: 0 });
  // Debounced snapshot of the preview-affecting inputs so dragging a slider
  // doesn't fire a video-decode request on every tick (keeps the UI snappy).
  const [pv, setPv] = useState(null);

  useEffect(() => {
    api.getCalibration().then(setS).catch(() => setS(null));
  }, []);

  const refreshTemplates = useCallback(() => {
    api.listTemplates().then(setTemplates).catch(() => {});
  }, []);
  useEffect(() => { refreshTemplates(); }, [refreshTemplates]);

  useEffect(() => {
    if (!s) return undefined;
    const id = setTimeout(() => setPv({ s, t, mask, zoom }), 300);
    return () => clearTimeout(id);
  }, [s, t, mask, zoom]);

  const set = (k, v) => { setS((p) => ({ ...p, [k]: v })); setSaved(false); };

  async function save() {
    setBusy(true);
    try {
      const updated = await api.saveCalibration(s);
      setS(updated);
      setSaved(true);
    } finally {
      setBusy(false);
    }
  }

  async function reset() {
    setBusy(true);
    try {
      setS(await api.resetCalibration());
      setSaved(true);
    } finally {
      setBusy(false);
    }
  }

  if (!s) return <div className="view"><div className="panel"><div className="panel-body empty">Loading settings…</div></div></div>;

  const stats = intelligence?.detection_stats;
  const round = calibrationRound;
  const previewSrc = round && pv
    ? `${api.minimapPreviewUrl(round.id, { t: pv.t, mask: pv.mask, crop: pv.zoom, ...pv.s })}&_=${pkey}`
    : null;
  const cap = templates.active_cap ?? s.detection_max_templates ?? 12;

  async function onTeach(e) {
    if (!round) return;
    const r = e.target.getBoundingClientRect();
    const x = ((e.clientX - r.left) / r.width).toFixed(4);
    const y = ((e.clientY - r.top) / r.height).toFixed(4);
    try {
      const res = await api.teachRound(round.id, { t, x, y, label: teachLabel, roi: zoom });
      setTaught(teachLabel);
      if (res) setTemplates((p) => ({ ...p, enemy_count: res.enemy_count, false_count: res.false_count }));
      setPkey((k) => k + 1);
      refreshTemplates();
    } catch {
      setTaught("error");
    }
  }

  async function delTemplate(label, name) {
    try {
      await api.deleteTemplate(label, name);
      refreshTemplates();
      setPkey((k) => k + 1);
    } catch { /* ignore */ }
  }

  async function forgetAll() {
    if (!confirm("Forget everything the detector learned from your training? This cannot be undone.")) return;
    try {
      await api.clearTemplates();
      refreshTemplates();
      setPkey((k) => k + 1);
    } catch { /* ignore */ }
  }

  const statusColor = { ok: "good", low: "amber", none: "bad" }[stats?.status] || "muted";

  // Honest live warnings about the current settings.
  const warnings = [];
  if (s.sat_min > 200) warnings.push("Saturation min is very high — real enemy markers may be missed.");
  if (s.sat_min < 60) warnings.push("Saturation min is low — the map background may be picked up as enemies.");
  if (s.confidence_threshold > 0.85) warnings.push("Confidence threshold is high — many detections will be dropped.");
  if (s.hue_max - s.hue_min > 60) warnings.push("Color band is very wide — expect false positives.");
  if (s.analysis_interval >= 2) warnings.push("Analysis interval is coarse (≥2s) — brief sightings may be skipped.");
  if (s.detection_max_templates > 24) warnings.push("Matching many templates per frame is slower — lower it if analysis drags.");
  if (templates.enemy_count === 0) warnings.push("No enemy templates taught yet — click real enemy pings below with “✓ Enemy” so the detector can learn them.");

  return (
    <div className="view settings-view">
      {/* ---- Detection feedback ---- */}
      <div className="panel">
        <div className="panel-head">
          <h3>DETECTION FEEDBACK</h3>
          {saved && <span className="good small">✓ Applied & saved</span>}
        </div>
        <div className="panel-body">
          <div className="feedback-grid">
            <div><span className="fb-label">Detector</span><span className="fb-val">{stats?.detector_backend || info?.detector_backend}</span></div>
            <div><span className="fb-label">Analysis interval</span><span className="fb-val">{(stats?.analysis_interval ?? s.analysis_interval)}s</span></div>
            <div><span className="fb-label">Last round markers</span><span className={cx("fb-val", statusColor)}>{stats?.enemy_markers ?? "—"}</span></div>
            <div><span className="fb-label">Avg confidence</span><span className="fb-val">{stats ? pct(stats.avg_confidence) : "—"}</span></div>
            <div><span className="fb-label">Frames analyzed</span><span className="fb-val">{stats?.frames_analyzed ?? "—"}</span></div>
            <div><span className="fb-label">Taught (enemy / false)</span><span className="fb-val">{templates.enemy_count} / {templates.false_count}</span></div>
          </div>
          {stats?.message && <div className={cx("fb-msg", statusColor)}>{stats.message}</div>}
          {warnings.map((w, i) => <div className="fb-warn" key={i}>⚠ {w}</div>)}
          {!intelligence && <div className="muted small">Open a match in ANALYSIS to see live detection numbers here.</div>}
        </div>
      </div>

      {/* ---- Analysis settings ---- */}
      <div className="panel">
        <div className="panel-head"><h3>ANALYSIS SETTINGS</h3></div>
        <div className="panel-body settings-grid">
          <label className="slider">
            <span>Analysis interval <em>{s.analysis_interval}s</em></span>
            <select value={s.analysis_interval} onChange={(e) => set("analysis_interval", Number(e.target.value))}>
              {[0.25, 0.33, 0.5, 1, 2].map((v) => <option key={v} value={v}>{v}s (~{Math.round(1 / v)} fps)</option>)}
            </select>
          </label>
          <Slider s={s} set={set} k="confidence_threshold" label="Confidence threshold" min={0} max={1} step={0.05} fmt={pct} />
          <Slider s={s} set={set} k="pattern_weight" label="Pattern learning weight (recent)" min={0} max={1} step={0.02} fmt={pct} />
          <Slider s={s} set={set} k="memory_weight" label="Match memory weight (overall)" min={0} max={1} step={0.02} fmt={pct} />
          <Slider s={s} set={set} k="recommendation_min_confidence" label="Recommendation min confidence" min={0} max={1} step={0.05} fmt={pct} />
          <Slider s={s} set={set} k="timeline_detail" label="Timeline detail (max events)" min={4} max={20} step={1} />
        </div>
      </div>

      {/* ---- Enemy detection + minimap calibration (with live preview) ---- */}
      <div className="panel">
        <div className="panel-head"><h3>ENEMY DETECTION & MINIMAP</h3></div>
        <div className="panel-body calib">
          <div className="calib-preview">
            {round ? (
              <img src={previewSrc} alt="detection preview" onClick={onTeach}
                   style={{ cursor: "crosshair" }} title="Click a marker to teach the detector" />
            ) : (
              <div className="empty small">Analyze a round to preview detection here.</div>
            )}
            <div className="teach-row" style={{ marginTop: 6 }}>
              <label className="check-row">
                <input type="checkbox" checked={zoom} onChange={(e) => setZoom(e.target.checked)} />
                Zoom to minimap (for precise teaching)
              </label>
            </div>
            <div className="muted small" style={{ marginTop: 4 }}>
              <b style={{ color: "#19c37d" }}>Green ring</b> = confirmed enemy ·
              <b style={{ color: "#ffaa2a" }}> amber ring</b> = considered but not confirmed yet
              (number = confidence %). Until you teach a few icons, expect mostly amber — those
              are exactly what to click. Pick <b>✓ Enemy</b> and click a real enemy ping to teach
              it; pick <b>✕ False</b> and click a wrong spot to teach it to ignore that. Each click
              trains it — see <b>LEARNED TEMPLATES</b> below.
            </div>
            {round && (
              <div className="teach-row">
                <span className="muted small">Click image to teach:</span>
                <button className={cx("seg-btn", teachLabel === "enemy" && "on")}
                        onClick={() => setTeachLabel("enemy")}>✓ Enemy</button>
                <button className={cx("seg-btn", teachLabel === "false" && "on")}
                        onClick={() => setTeachLabel("false")}>✕ False</button>
                {taught && <span className={cx("small", taught === "error" ? "bad" : "good")}>
                  {taught === "error" ? "failed" : `taught: ${taught} (${templates.enemy_count}✓ / ${templates.false_count}✕)`}</span>}
              </div>
            )}
          </div>
          <div className="calib-controls">
            <div className="sub-label">Enemy color</div>
            <label className="slider">
              <span>Color mode</span>
              <select value={s.color_mode || "auto"} onChange={(e) => set("color_mode", e.target.value)}>
                <option value="auto">Auto — detect red & yellow (no tuning)</option>
                <option value="red">Red only</option>
                <option value="yellow">Yellow only</option>
                <option value="custom">Custom hue band</option>
              </select>
            </label>
            {(s.color_mode || "auto") === "custom" && (
              <>
                <Slider s={s} set={set} k="hue_min" label="hue min" min={0} max={179} step={1} />
                <Slider s={s} set={set} k="hue_max" label="hue max" min={0} max={179} step={1} />
              </>
            )}
            <Slider s={s} set={set} k="sat_min" label="saturation min (higher = stricter)" min={0} max={255} step={1} />
            <Slider s={s} set={set} k="val_min" label="brightness min" min={0} max={255} step={1} />
            <Slider s={s} set={set} k="min_area" label="min blob size" min={1} max={40} step={1} />
            <Slider s={s} set={set} k="max_area" label="max blob size" min={40} max={800} step={10} />
            <div className="sub-label">Detection confidence</div>
            <Slider s={s} set={set} k="detection_confirm_threshold" label="Enemy confirm threshold (all cues)" min={0.3} max={0.95} step={0.01} fmt={pct} />
            <Slider s={s} set={set} k="detection_template_threshold" label="Template match strictness" min={0.3} max={0.9} step={0.01} fmt={pct} />
            <Slider s={s} set={set} k="detection_motion_frames" label="Motion persistence (frames)" min={1} max={12} step={1} />
            <div className="sub-label">Minimap box (green) — put it on the minimap</div>
            <Slider s={s} set={set} k="x_frac" label="x" min={0} max={0.6} step={0.002} fmt={(v) => v.toFixed(3)} />
            <Slider s={s} set={set} k="y_frac" label="y" min={0} max={0.6} step={0.002} fmt={(v) => v.toFixed(3)} />
            <Slider s={s} set={set} k="w_frac" label="width" min={0.05} max={0.7} step={0.002} fmt={(v) => v.toFixed(3)} />
            <Slider s={s} set={set} k="h_frac" label="height" min={0.05} max={0.7} step={0.002} fmt={(v) => v.toFixed(3)} />
            {round && (
              <label className="slider">
                <span>preview time <em>{t}s</em></span>
                <input type="range" min="0" max="60" step="1" value={t} onChange={(e) => setT(Number(e.target.value))} />
              </label>
            )}
          </div>
        </div>
      </div>

      {/* ---- Learned templates (what training produced) ---- */}
      <div className="panel">
        <div className="panel-head">
          <h3>LEARNED TEMPLATES</h3>
          <span className="muted small">{templates.enemy_count} enemy · {templates.false_count} false</span>
        </div>
        <div className="panel-body">
          <div className="muted small" style={{ marginBottom: 8 }}>
            These are the patches the detector learned from your clicks. Enemy patches are matched
            against the minimap to find enemies; false patches suppress look-alikes. The newest
            <b> {cap}</b> of each are used per frame (the cap below — fewer = faster). Click ✕ to
            forget a mistake. Dimmed = beyond the cap, currently unused.
          </div>
          <div className="sub-label">Enemy ({templates.enemy_count})</div>
          <Gallery label="enemy" names={templates.enemy} cap={cap} onDelete={delTemplate} />
          <div className="sub-label" style={{ marginTop: 8 }}>False / ignore ({templates.false_count})</div>
          <Gallery label="false" names={templates.false} cap={cap} onDelete={delTemplate} />
          <div style={{ marginTop: 12 }}>
            <Slider s={s} set={set} k="detection_max_templates" label="Templates matched per frame (speed ↔ accuracy)" min={1} max={40} step={1} />
          </div>
          {(templates.enemy_count > 0 || templates.false_count > 0) && (
            <button className="btn ghost danger" style={{ marginTop: 8 }} onClick={forgetAll}>
              Forget all training
            </button>
          )}
        </div>
      </div>

      {/* ---- Killfeed (honest: needs OCR) ---- */}
      <div className="panel">
        <div className="panel-head"><h3>KILLFEED DETECTION</h3></div>
        <div className="panel-body">
          <div className={cx("fb-msg", info?.ocr_ready ? "good" : "muted")}>
            {info?.ocr_ready
              ? "OCR is active — killfeed parsing runs during analysis."
              : "Killfeed detection requires OCR, which is currently OFF. Enable VVC_OCR_BACKEND=easyocr (+ ML deps) to use it. No sensitivity slider is shown because it would have no effect while OCR is off."}
          </div>
        </div>
      </div>

      <div className="settings-actions">
        <button className="btn primary" onClick={save} disabled={busy}>
          {busy ? "Saving…" : saved ? "✓ Saved" : "Save settings"}
        </button>
        <button className="btn ghost" onClick={reset} disabled={busy}>Reset to defaults</button>
        {round && (
          <button className="btn" onClick={() => onReanalyze?.(round.id)}>
            Re-analyze latest round with these settings
          </button>
        )}
        <span className="muted small">Saved settings persist and apply to all future analyses. Re-analyze to apply to existing rounds.</span>
      </div>

      <div className="notice">
        <b>For correct positions:</b> set Valorant's minimap to <b>Fixed</b> rotation and
        <i> Keep Player Centered: Off</i>. A rotating/centered minimap can't give absolute enemy positions.
      </div>
    </div>
  );
}
