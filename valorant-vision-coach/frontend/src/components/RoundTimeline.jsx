import { KIND_ICON, cx, formatClock } from "../util.js";

const KIND_CLASS = {
  spotted: "red", kill: "red", smoke: "violet", recon: "blue",
  turret: "amber", trap: "amber", rotation: "amber", move: "teal", info: "muted",
};

export default function RoundTimeline({ events = [] }) {
  return (
    <div className="panel timeline-panel">
      <div className="panel-head"><h3>ROUND TIMELINE</h3></div>
      <div className="panel-body">
        {events.length === 0 ? (
          <div className="empty small">No events for this round yet.</div>
        ) : (
          <div className="timeline-track">
            {events.map((e, i) => (
              <div className="tl-event" key={i}>
                <div className="tl-time">{formatClock(e.timestamp_seconds)}</div>
                <div className={cx("tl-dot", KIND_CLASS[e.kind] || "muted")}>
                  {KIND_ICON[e.kind] || "•"}
                </div>
                <div className="tl-label">{e.label}</div>
                {e.detail && <div className="tl-detail">{e.detail}</div>}
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}
