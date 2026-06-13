import { useMemo } from "react";
import { rampColor } from "../util.js";

const SIZE = 300;

export default function Heatmap({ cells = [], mapMeta }) {
  const calloutById = useMemo(() => {
    const m = {};
    (mapMeta?.callouts || []).forEach((c) => (m[c.id] = c));
    return m;
  }, [mapMeta]);

  return (
    <div className="panel">
      <div className="panel-head"><h3>HEATMAP (SITE CONTROL)</h3></div>
      <div className="panel-body heatmap-body">
        <svg viewBox={`0 0 ${SIZE} ${SIZE}`} className="heatmap-svg">
          <rect x="0" y="0" width={SIZE} height={SIZE} rx="10" fill="#11161f" />
          {(mapMeta?.edges || []).map(([a, b], i) => {
            const ca = calloutById[a];
            const cb = calloutById[b];
            if (!ca || !cb) return null;
            return (
              <line key={i} x1={ca.x * SIZE} y1={ca.y * SIZE} x2={cb.x * SIZE} y2={cb.y * SIZE}
                    stroke="#222b3a" strokeWidth="2" />
            );
          })}
          {cells.map((c, i) => (
            <circle key={i} cx={c.x * SIZE} cy={c.y * SIZE} r={6 + c.weight * 20}
                    fill={rampColor(c.weight)} opacity={0.2 + c.weight * 0.55} />
          ))}
          {cells.length === 0 && (
            <text x={SIZE / 2} y={SIZE / 2} textAnchor="middle" className="empty-svg">
              No enemy data yet
            </text>
          )}
        </svg>
        <div className="heat-scale">
          <span>High</span>
          <div className="heat-gradient" />
          <span>Low</span>
        </div>
      </div>
    </div>
  );
}
