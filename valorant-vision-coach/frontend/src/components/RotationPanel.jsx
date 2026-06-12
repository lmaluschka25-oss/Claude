import { agentInitials } from "../util.js";

export default function RotationPanel({ rotations }) {
  return (
    <div className="panel">
      <div className="panel-header">
        <h2>Likely Rotations</h2>
        <span className="faint">dead-reckoned</span>
      </div>
      <div className="panel-body">
        {rotations.length === 0 && (
          <div className="empty">No active enemy tracks to project from.</div>
        )}
        {rotations.map((rot, i) => (
          <div key={i} style={{ marginBottom: 14 }}>
            <div className="row" style={{ borderBottom: "none", paddingBottom: 2 }}>
              <span className="agent-chip">
                <span className="ic">{agentInitials(rot.agent_name)}</span>
                {rot.agent_name || "Unknown"}
              </span>
              <span className="faint mono">
                from {rot.origin_callout} · {rot.age_seconds.toFixed(1)}s ago
              </span>
            </div>
            {rot.candidates.map((c, j) => (
              <div className="cand" key={j}>
                <div className="route">
                  → {c.to_callout}
                  {c.leads_to_site && (
                    <span className="muted"> · onto {c.leads_to_site}</span>
                  )}
                  <div className="bar" style={{ marginTop: 4 }}>
                    <span
                      style={{
                        width: `${Math.round(c.likelihood * 100)}%`,
                        background: "#ffb454",
                      }}
                    />
                  </div>
                </div>
                <div className="meta">
                  {Math.round(c.likelihood * 100)}% · ~{c.eta_seconds.toFixed(1)}s
                </div>
              </div>
            ))}
          </div>
        ))}
      </div>
    </div>
  );
}
