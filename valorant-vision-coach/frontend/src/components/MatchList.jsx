import { cx, formatClock } from "../util.js";
import StatusPill from "./StatusPill.jsx";

export default function MatchList({ matches, selectedId, onSelect, onDelete }) {
  return (
    <div className="panel">
      <div className="panel-header">
        <h2>Matches</h2>
        <span className="faint">{matches.length}</span>
      </div>
      <div className="panel-body">
        {matches.length === 0 && <div className="empty">No matches yet. Upload a VOD above.</div>}
        {matches.map((m) => (
          <div
            key={m.id}
            className={cx("match", m.id === selectedId && "active")}
            onClick={() => onSelect(m)}
          >
            <div className="name">{m.filename}</div>
            <div className="sub">
              <StatusPill status={m.status} />
              <span className="muted">{m.map_name || "—"}</span>
              {m.duration_seconds ? (
                <span className="muted">{formatClock(m.duration_seconds)}</span>
              ) : null}
              <span className="muted">{m.detections_count} det.</span>
            </div>
            {m.status === "processing" && (
              <div className="progress" title={`${Math.round((m.progress || 0) * 100)}%`}>
                <span style={{ width: `${Math.round((m.progress || 0) * 100)}%` }} />
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
                Delete
              </button>
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}
