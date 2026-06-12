import { useMemo } from "react";
import { agentInitials, pressureColor } from "../util.js";

const SIZE = 1000;
const PRESSURE_RADIUS = 0.2; // normalized, for the zone overlay only

export default function MapView({ mapMeta, snapshot }) {
  const calloutById = useMemo(() => {
    const map = {};
    (mapMeta?.callouts || []).forEach((c) => (map[c.id] = c));
    return map;
  }, [mapMeta]);

  const siteCentroids = useMemo(() => {
    const groups = {};
    (mapMeta?.callouts || []).forEach((c) => {
      if (c.site) (groups[c.site] = groups[c.site] || []).push(c);
    });
    const out = {};
    Object.entries(groups).forEach(([site, cs]) => {
      out[site] = {
        x: cs.reduce((a, c) => a + c.x, 0) / cs.length,
        y: cs.reduce((a, c) => a + c.y, 0) / cs.length,
      };
    });
    return out;
  }, [mapMeta]);

  if (!mapMeta) {
    return <div className="mapwrap" />;
  }

  const pressureBySite = {};
  (snapshot?.site_pressure || []).forEach((p) => (pressureBySite[p.site] = p));

  return (
    <div className="mapwrap">
      <svg className="map-svg" viewBox={`0 0 ${SIZE} ${SIZE}`} role="img" aria-label="Tactical map">
        <rect x="0" y="0" width={SIZE} height={SIZE} fill="#0e1420" />

        {/* Site pressure zones */}
        {Object.entries(siteCentroids).map(([site, c]) => {
          const p = pressureBySite[site]?.pressure || 0;
          return (
            <g key={`zone-${site}`}>
              <circle
                cx={c.x * SIZE}
                cy={c.y * SIZE}
                r={PRESSURE_RADIUS * SIZE}
                fill={pressureColor(p)}
                opacity={0.06 + p * 0.32}
              />
              <text
                x={c.x * SIZE}
                y={c.y * SIZE - PRESSURE_RADIUS * SIZE - 8}
                fill="#aeb9c9"
                fontSize="22"
                fontWeight="700"
                textAnchor="middle"
              >
                {site}
              </text>
            </g>
          );
        })}

        {/* Rotation graph edges */}
        {(mapMeta.edges || []).map(([a, b], i) => {
          const ca = calloutById[a];
          const cb = calloutById[b];
          if (!ca || !cb) return null;
          return (
            <line
              key={`e-${i}`}
              x1={ca.x * SIZE}
              y1={ca.y * SIZE}
              x2={cb.x * SIZE}
              y2={cb.y * SIZE}
              stroke="#243049"
              strokeWidth="2"
            />
          );
        })}

        {/* Callout nodes */}
        {mapMeta.callouts.map((c) => (
          <g key={c.id}>
            <circle cx={c.x * SIZE} cy={c.y * SIZE} r="4" fill="#3a475e" />
            <text
              x={c.x * SIZE + 7}
              y={c.y * SIZE + 4}
              fill="#5a6678"
              fontSize="13"
            >
              {c.name}
            </text>
          </g>
        ))}

        {/* Rotation candidate routes */}
        {(snapshot?.rotations || []).flatMap((rot) =>
          rot.candidates.map((cand, j) => {
            const origin = (mapMeta.callouts || []).find((c) => c.name === rot.origin_callout);
            if (!origin) return null;
            return (
              <line
                key={`r-${rot.agent_name}-${j}`}
                x1={origin.x * SIZE}
                y1={origin.y * SIZE}
                x2={cand.to_x * SIZE}
                y2={cand.to_y * SIZE}
                stroke="#ffb454"
                strokeWidth={1 + cand.likelihood * 5}
                strokeOpacity={0.25 + cand.likelihood * 0.6}
                strokeDasharray="6 5"
                markerEnd="url(#arrow)"
              />
            );
          })
        )}

        {/* Last known enemy positions */}
        {(snapshot?.last_known || [])
          .filter((lk) => lk.map_x != null)
          .map((lk, i) => {
            const x = lk.map_x * SIZE;
            const y = lk.map_y * SIZE;
            const dim = lk.stale ? 0.45 : 1;
            return (
              <g key={`lk-${i}`} opacity={dim}>
                <circle cx={x} cy={y} r="16" fill="#ff4655" opacity="0.18" />
                <circle cx={x} cy={y} r="9" fill="#ff4655" stroke="#fff" strokeWidth="1.5" />
                <text x={x} y={y + 4} fill="#11151d" fontSize="11" fontWeight="800" textAnchor="middle">
                  {agentInitials(lk.agent_name)}
                </text>
                <text x={x + 14} y={y - 8} fill="#ffd2d6" fontSize="13" fontWeight="600">
                  {lk.agent_name || "Enemy"}
                </text>
                <text x={x + 14} y={y + 8} fill="#8b97a8" fontSize="11">
                  {lk.age_seconds.toFixed(1)}s
                </text>
              </g>
            );
          })}

        <defs>
          <marker id="arrow" viewBox="0 0 10 10" refX="8" refY="5" markerWidth="6" markerHeight="6" orient="auto-start-reverse">
            <path d="M 0 0 L 10 5 L 0 10 z" fill="#ffb454" />
          </marker>
        </defs>
      </svg>
    </div>
  );
}
