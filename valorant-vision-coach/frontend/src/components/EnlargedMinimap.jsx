import { useMemo } from "react";
import { KIND_ICON, agentInitials } from "../util.js";

const SIZE = 1000;
const UTILITY_KINDS = new Set(["smoke", "recon", "turret", "trap", "flash", "molly", "wall"]);

export default function EnlargedMinimap({ mapMeta, markers = [] }) {
  const calloutById = useMemo(() => {
    const m = {};
    (mapMeta?.callouts || []).forEach((c) => (m[c.id] = c));
    return m;
  }, [mapMeta]);

  const siteCentroids = useMemo(() => {
    const groups = {};
    (mapMeta?.callouts || []).forEach((c) => c.site && (groups[c.site] = groups[c.site] || []).push(c));
    const out = {};
    Object.entries(groups).forEach(([s, cs]) => {
      out[s] = {
        x: cs.reduce((a, c) => a + c.x, 0) / cs.length,
        y: cs.reduce((a, c) => a + c.y, 0) / cs.length,
      };
    });
    return out;
  }, [mapMeta]);

  return (
    <div className="panel minimap-panel">
      <div className="panel-head"><h3>ENLARGED MINIMAP ANALYSIS</h3></div>
      <div className="panel-body">
        <div className="minimap-wrap">
          <svg viewBox={`0 0 ${SIZE} ${SIZE}`} className="minimap-svg" role="img">
            <rect x="0" y="0" width={SIZE} height={SIZE} fill="#11161f" rx="14" />
            {/* site zones */}
            {Object.entries(siteCentroids).map(([s, c]) => (
              <g key={`z-${s}`}>
                <rect
                  x={c.x * SIZE - 70} y={c.y * SIZE - 60} width="140" height="120" rx="12"
                  fill="#1c2533" opacity="0.7"
                />
                <text x={c.x * SIZE} y={c.y * SIZE + 6} className="mm-site-label" textAnchor="middle">
                  {s}
                </text>
              </g>
            ))}
            {/* rotation graph edges */}
            {(mapMeta?.edges || []).map(([a, b], i) => {
              const ca = calloutById[a];
              const cb = calloutById[b];
              if (!ca || !cb) return null;
              return (
                <line key={`e-${i}`} x1={ca.x * SIZE} y1={ca.y * SIZE} x2={cb.x * SIZE} y2={cb.y * SIZE}
                      stroke="#2a3344" strokeWidth="3" />
              );
            })}
            {/* callout nodes */}
            {(mapMeta?.callouts || []).map((c) => (
              <circle key={c.id} cx={c.x * SIZE} cy={c.y * SIZE} r="4" fill="#3a475e" />
            ))}
            {/* markers */}
            {markers.map((m, i) => (
              <Marker key={i} m={m} />
            ))}
          </svg>
        </div>
        <div className="legend">
          <span><i className="lg self" /> You</span>
          <span><i className="lg ally" /> Teammate</span>
          <span><i className="lg enemy" /> Enemy</span>
          <span><i className="lg dead" /> Dead</span>
          <span><i className="lg util" /> Utility</span>
        </div>
      </div>
    </div>
  );
}

function Marker({ m }) {
  const x = m.map_x * SIZE;
  const y = m.map_y * SIZE;
  if (UTILITY_KINDS.has(m.kind)) {
    return (
      <g opacity="0.92">
        <circle cx={x} cy={y} r="15" fill="#7a5cff" opacity="0.25" />
        <text x={x} y={y + 6} textAnchor="middle" className="mm-util">{KIND_ICON[m.kind] || "✦"}</text>
      </g>
    );
  }
  const self = m.kind === "self" || m.agent_name === "You";
  const color = m.team === "enemy" ? "#ff4655" : self ? "#ffd166" : "#3fb6a8";
  return (
    <g opacity={m.dead ? 0.45 : 1}>
      <circle cx={x} cy={y} r={self ? 17 : 15} fill={color}
              stroke={self ? "#fff" : "#0d1117"} strokeWidth={self ? 3 : 2} />
      <text x={x} y={y + 5} textAnchor="middle" className="mm-agent">{agentInitials(m.agent_name)}</text>
      {m.dead && <text x={x} y={y + 5} textAnchor="middle" className="mm-dead">✕</text>}
    </g>
  );
}
