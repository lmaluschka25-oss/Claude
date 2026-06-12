import { agentInitials, formatAge } from "../util.js";

export default function LastKnownPanel({ lastKnown }) {
  return (
    <div className="panel">
      <div className="panel-header">
        <h2>Last Known Positions</h2>
        <span className="faint">{lastKnown.length} tracked</span>
      </div>
      <div className="panel-body">
        {lastKnown.length === 0 && <div className="empty">No enemies seen within the TTL window.</div>}
        {lastKnown.map((lk, i) => (
          <div className="row" key={i}>
            <div className="label">
              <span className="agent-chip">
                <span className="ic">{agentInitials(lk.agent_name)}</span>
                {lk.agent_name || "Unknown"}
              </span>
              {lk.stale && <span className="tag-stale">stale</span>}
            </div>
            <div style={{ textAlign: "right" }}>
              <div>{lk.callout || "—"}</div>
              <div className="faint mono">
                {formatAge(lk.age_seconds)} · {(lk.confidence * 100).toFixed(0)}%
              </div>
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}
