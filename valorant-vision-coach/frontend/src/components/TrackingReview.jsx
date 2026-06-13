import { useEffect, useState } from "react";
import { api } from "../api/client.js";
import { formatClock } from "../util.js";

// Annotated playback of a recording: scrub through time and see what the
// detector found (red circles = detected enemy markers, green box = minimap
// region). Review AFTER recording — not a live in-match overlay.
export default function TrackingReview({ matchId, duration }) {
  const [t, setT] = useState(0);
  const [imgT, setImgT] = useState(0);
  const [mask, setMask] = useState(false);

  // Debounce image reloads while dragging the slider.
  useEffect(() => {
    const id = setTimeout(() => setImgT(t), 180);
    return () => clearTimeout(id);
  }, [t]);

  const max = Math.max(duration || 0, 0.1);
  const src = api.minimapPreviewUrl(matchId, imgT.toFixed(1), mask);

  return (
    <div className="panel">
      <div className="panel-header">
        <h2>Tracking-Vorschau</h2>
        <label className="faint" style={{ display: "flex", gap: 6, alignItems: "center" }}>
          <input type="checkbox" checked={mask} onChange={(e) => setMask(e.target.checked)} />
          Farbmaske
        </label>
      </div>
      <div className="panel-body">
        <div className="track-img">
          <img src={src} alt="Tracking-Vorschau" />
        </div>
        <div className="timeline" style={{ marginTop: 12 }}>
          <input
            type="range"
            min={0}
            max={max}
            step={0.5}
            value={t}
            onChange={(e) => setT(Number(e.target.value))}
          />
          <div className="tcode">
            {formatClock(t)} / {formatClock(duration || 0)}
          </div>
        </div>
        <div className="notice" style={{ marginTop: 12 }}>
          Rote Kreise = erkannte Gegner-Marker · grüner Kasten = Minimap-Bereich.
          „Farbmaske" zeigt türkis, welche Pixel als Rot erkannt werden (zum
          Einstellen). Wiedergabe deiner Aufnahme — keine Live-Einblendung im Spiel.
        </div>
      </div>
    </div>
  );
}
