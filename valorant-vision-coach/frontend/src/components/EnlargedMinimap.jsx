import { useMemo } from "react";

const SIZE = 1000;
const UTILITY_KINDS = new Set(["smoke", "recon", "turret", "trap", "flash", "molly", "wall"]);
const GRID = 0.09; // enemy clustering bucket size (normalized)

// Cluster enemy markers into presence blobs: more enemies in an area → bigger.
function clusterEnemies(markers) {
  const buckets = {};
  for (const m of markers) {
    if (m.team !== "enemy" || UTILITY_KINDS.has(m.kind) || m.map_x == null) continue;
    const key = `${Math.round(m.map_x / GRID)}_${Math.round(m.map_y / GRID)}`;
    const b = (buckets[key] ||= { x: 0, y: 0, n: 0 });
    b.x += m.map_x;
    b.y += m.map_y;
    b.n += 1;
  }
  return Object.values(buckets).map((b) => ({ x: b.x / b.n, y: b.y / b.n, count: b.n }));
}

export default function EnlargedMinimap({ mapMeta, markers = [] }) {
  const calloutById = useMemo(() => {
    const m = {};
    (mapMeta?.callouts || []).forEach((c) => (m[c.id] = c));
    return m;
  }, [mapMeta]);

  const siteCentroids = useMemo(() => {
    const groups = {};
    (mapMeta?.callouts || []).forEach((c) => c.site && (groups[c.site] ||= []).push(c));
    const out = {};
    Object.entries(groups).forEach(([s, cs]) => {
      out[s] = {
        x: cs.reduce((a, c) => a + c.x, 0) / cs.length,
        y: cs.reduce((a, c) => a + c.y, 0) / cs.length,
      };
    });
    return out;
  }, [mapMeta]);

  const clusters = useMemo(() => clusterEnemies(markers), [markers]);
  const self = markers.find((m) => m.kind === "self" || m.agent_name === "You");
  const spawns = (mapMeta?.callouts || []).filter((c) => c.id.includes("spawn"));

  return (
    <div className="panel minimap-panel">
      <div className="panel-head">
        <h3>MAP — ENEMY PRESENCE</h3>
        <span className="panel-extra">{clusters.reduce((a, c) => a + c.count, 0)} enemies located</span>
      </div>
      <div className="panel-body minimap-body">
        <div className="minimap-wrap">
          <svg viewBox={`0 0 ${SIZE} ${SIZE}`} className="minimap-svg" preserveAspectRatio="xMidYMid meet" role="img">
            <defs>
              <radialGradient id="enemyGlow" cx="50%" cy="50%" r="50%">
                <stop offset="0%" stopColor="#ff4655" stopOpacity="0.9" />
                <stop offset="100%" stopColor="#ff4655" stopOpacity="0.12" />
              </radialGradient>
            </defs>
            <rect x="0" y="0" width={SIZE} height={SIZE} rx="16" fill="#0e1420" />

            {/* site zones */}
            {Object.entries(siteCentroids).map(([s, c]) => (
              <g key={`z-${s}`}>
                <rect x={c.x * SIZE - 95} y={c.y * SIZE - 80} width="190" height="160" rx="18"
                      fill="#19222f" stroke="#26303f" />
                <text x={c.x * SIZE} y={c.y * SIZE + 14} className="mm-site-label" textAnchor="middle">{s}</text>
              </g>
            ))}

            {/* lanes (corridors) drawn thick + rounded so it reads like a map */}
            {(mapMeta?.edges || []).map(([a, b], i) => {
              const ca = calloutById[a];
              const cb = calloutById[b];
              if (!ca || !cb) return null;
              return (
                <line key={`e-${i}`} x1={ca.x * SIZE} y1={ca.y * SIZE} x2={cb.x * SIZE} y2={cb.y * SIZE}
                      stroke="#243049" strokeWidth="16" strokeLinecap="round" />
              );
            })}
            {/* area rooms */}
            {(mapMeta?.callouts || []).map((c) => (
              <circle key={c.id} cx={c.x * SIZE} cy={c.y * SIZE} r="16" fill="#2a3548" stroke="#36435c" />
            ))}
            {/* spawn labels */}
            {spawns.map((c) => (
              <text key={c.id} x={c.x * SIZE} y={c.y * SIZE + 4} className="mm-spawn" textAnchor="middle">
                {c.name.split(" ")[0]}
              </text>
            ))}

            {/* enemy presence blobs — size ∝ how many enemies */}
            {clusters.map((c, i) => {
              const r = 28 + c.count * 22;
              return (
                <g key={`en-${i}`}>
                  <circle cx={c.x * SIZE} cy={c.y * SIZE} r={r} fill="url(#enemyGlow)" />
                  <circle cx={c.x * SIZE} cy={c.y * SIZE} r={18 + c.count * 6} fill="#ff4655"
                          stroke="#fff" strokeWidth="2" />
                  <text x={c.x * SIZE} y={c.y * SIZE + 7} className="mm-count" textAnchor="middle">{c.count}</text>
                </g>
              );
            })}

            {/* your position */}
            {self && self.map_x != null && (
              <g>
                <circle cx={self.map_x * SIZE} cy={self.map_y * SIZE} r="13" fill="#ffd166"
                        stroke="#fff" strokeWidth="3" />
                <text x={self.map_x * SIZE} y={self.map_y * SIZE - 20} className="mm-you" textAnchor="middle">YOU</text>
              </g>
            )}

            {clusters.length === 0 && (
              <text x={SIZE / 2} y={SIZE - 30} textAnchor="middle" className="mm-empty">
                No enemies revealed this round
              </text>
            )}
          </svg>
        </div>
        <div className="legend">
          <span><i className="lg self" /> You</span>
          <span><i className="lg enemy" /> Enemy presence — bigger = more enemies</span>
        </div>
      </div>
    </div>
  );
}
