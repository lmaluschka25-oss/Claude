import { useEffect, useState } from "react";
import { api } from "../api/client.js";
import { cx, formatClock } from "../util.js";

// Shows the round either as raw gameplay or as "what the program sees" — the
// real frame with the minimap ROI box and detected enemies circled (+ count).
export default function RoundView({ round }) {
  const [mode, setMode] = useState("detect");
  const [t, setT] = useState(2);
  const [imgT, setImgT] = useState(2);
  const [playing, setPlaying] = useState(false);

  const ready = round && round.status === "completed";
  const dur = round?.duration_seconds || 30;

  useEffect(() => {
    const id = setTimeout(() => setImgT(t), 150);
    return () => clearTimeout(id);
  }, [t]);

  // When a completed round opens in "What it sees", start scanning from the top
  // automatically so the timeline visibly plays through the round.
  useEffect(() => {
    if (ready && mode === "detect") {
      setT(0);
      setPlaying(true);
    } else {
      setPlaying(false);
    }
  }, [round?.id, ready, mode]);

  // Auto-play scans the whole recording front-to-back.
  useEffect(() => {
    if (!playing || mode !== "detect" || !ready) return;
    const id = setInterval(() => setT((p) => (p >= dur ? 0 : Math.min(dur, p + 1))), 550);
    return () => clearInterval(id);
  }, [playing, mode, ready, dur]);

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
              <button className="btn ghost" style={{ padding: "2px 9px" }}
                      onClick={() => setPlaying((p) => !p)}>
                {playing ? "⏸" : "▶"}
              </button>
              <input type="range" min="0" max={Math.max(dur, 1)} step="0.5" value={t}
                     onChange={(e) => { setPlaying(false); setT(Number(e.target.value)); }} />
              <div className="tcode">{formatClock(t)} / {formatClock(dur)}</div>
            </div>
            <div className="muted small">
              Green box = minimap area · circles = detected enemies (with count). ▶ scans the whole round.
            </div>
          </>
        )}
      </div>
    </div>
  );
}
