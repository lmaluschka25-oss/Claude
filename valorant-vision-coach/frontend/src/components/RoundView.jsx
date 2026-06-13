import { useEffect, useState } from "react";
import { api } from "../api/client.js";
import { cx, formatClock } from "../util.js";

// Shows the round either as raw gameplay or as "what the program sees" — the
// real frame with the minimap ROI box and detected enemies circled (+ count).
export default function RoundView({ round }) {
  const [mode, setMode] = useState("detect");
  const [t, setT] = useState(2);
  const [imgT, setImgT] = useState(2);

  useEffect(() => {
    const id = setTimeout(() => setImgT(t), 180);
    return () => clearTimeout(id);
  }, [t]);

  const ready = round && round.status === "completed";
  const dur = round?.duration_seconds || 30;

  return (
    <div className="panel">
      <div className="panel-head">
        <h3>ROUND VIEW</h3>
        <div className="seg">
          <button className={cx("seg-btn", mode === "detect" && "on")} onClick={() => setMode("detect")}>
            What it sees
          </button>
          <button className={cx("seg-btn", mode === "video" && "on")} onClick={() => setMode("video")}>
            Gameplay
          </button>
        </div>
      </div>
      <div className="panel-body">
        {!ready ? (
          <div className="video-placeholder">
            {round
              ? round.status === "processing"
                ? `Analyzing ${Math.round((round.progress || 0) * 100)}%`
                : "Round not analyzed yet."
              : "Select a round."}
          </div>
        ) : mode === "video" ? (
          <video key={round.id} className="round-video" src={api.roundVideoUrl(round.id)} controls preload="metadata" />
        ) : (
          <>
            <div className="detect-img">
              <img src={api.minimapPreviewUrl(round.id, { t: imgT })} alt="detection overlay" />
            </div>
            <div className="timeline" style={{ marginTop: 8 }}>
              <input type="range" min="0" max={Math.max(dur, 1)} step="0.5" value={t}
                     onChange={(e) => setT(Number(e.target.value))} />
              <div className="tcode">{formatClock(t)}</div>
            </div>
            <div className="muted small">
              Green box = minimap area · red circles = detected enemies (with count). Scrub the slider.
            </div>
          </>
        )}
      </div>
    </div>
  );
}
