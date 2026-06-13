import { useState } from "react";
import { cx, formatClock, formatDateTime } from "../util.js";
import StatusPill from "./StatusPill.jsx";

export default function MatchList({ matches, selectedId, onSelect, onDelete }) {
  const [onlyAnalyzed, setOnlyAnalyzed] = useState(false);

  const completed = matches.filter((m) => m.status === "completed").length;
  const shown = onlyAnalyzed
    ? matches.filter((m) => m.status === "completed")
    : matches;

  return (
    <div className="panel">
      <div className="panel-header">
        <h2>Matches</h2>
        <span className="faint">
          {completed}/{matches.length} ausgewertet
        </span>
      </div>
      <div className="panel-body">
        {matches.length > 0 && (
          <button
            className={cx("btn ghost", onlyAnalyzed && "primary")}
            style={{ width: "100%", marginBottom: 10, fontSize: 12 }}
            onClick={() => setOnlyAnalyzed((v) => !v)}
          >
            {onlyAnalyzed ? "✓ Nur ausgewertete" : "Nur ausgewertete zeigen"}
          </button>
        )}

        {shown.length === 0 && (
          <div className="empty">
            {matches.length === 0
              ? "Noch keine Matches. Lade oben ein VOD hoch."
              : "Keine ausgewerteten Matches."}
          </div>
        )}

        {shown.map((m) => (
          <div
            key={m.id}
            className={cx("match", m.id === selectedId && "active")}
            onClick={() => onSelect(m)}
          >
            <div className="name">
              {m.status === "completed" && <span className="check">✓</span>}
              {m.filename}
            </div>
            <div className="sub">
              <StatusPill status={m.status} />
              <span className="muted">{m.map_name || "—"}</span>
              {m.duration_seconds ? (
                <span className="muted">{formatClock(m.duration_seconds)}</span>
              ) : null}
              <span className="muted">{m.detections_count} det.</span>
            </div>

            {m.status === "completed" && (
              <div className="analyzed-line">
                Ausgewertet · {formatDateTime(m.processed_at || m.created_at)}
              </div>
            )}

            {m.status === "processing" && (
              <div className="progress" title={`${Math.round((m.progress || 0) * 100)}%`}>
                <span style={{ width: `${Math.round((m.progress || 0) * 100)}%` }} />
              </div>
            )}
            {m.status === "failed" && (
              <div className="analyzed-line" style={{ color: "var(--accent)" }}>
                Fehlgeschlagen — erneut hochladen
              </div>
            )}

            <div style={{ display: "flex", justifyContent: "flex-end" }}>
              <button
                className="btn ghost danger"
                style={{ padding: "2px 8px", fontSize: 11 }}
                onClick={(e) => {
                  e.stopPropagation();
                  onDelete(m);
                }}
              >
                Löschen
              </button>
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}
