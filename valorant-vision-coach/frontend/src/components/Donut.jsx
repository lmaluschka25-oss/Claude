import { rampColor } from "../util.js";

const R = 42;
const C = 2 * Math.PI * R;
const SITE_COLOR = { A: "#ff4655", B: "#ffb454", C: "#9b8cff", MID: "#3fb6a8" };

// A donut chart of site-presence shares. `data` is { site: share(0..1) }.
export default function Donut({ data = {}, title }) {
  const entries = Object.entries(data).filter(([, v]) => v > 0).sort((a, b) => b[1] - a[1]);
  const total = entries.reduce((a, [, v]) => a + v, 0) || 1;
  let offset = 0;
  const top = entries[0];

  return (
    <div className="donut-wrap">
      <svg viewBox="0 0 120 120" className="donut">
        <g transform="rotate(-90 60 60)">
          <circle cx="60" cy="60" r={R} fill="none" stroke="#1e2735" strokeWidth="14" />
          {entries.map(([site, v]) => {
            const frac = v / total;
            const dash = frac * C;
            const el = (
              <circle
                key={site} cx="60" cy="60" r={R} fill="none"
                stroke={SITE_COLOR[site] || rampColor(v)} strokeWidth="14"
                strokeDasharray={`${dash} ${C - dash}`} strokeDashoffset={-offset}
              />
            );
            offset += dash;
            return el;
          })}
        </g>
        {top && (
          <>
            <text x="60" y="56" textAnchor="middle" className="donut-top">{top[0]}</text>
            <text x="60" y="74" textAnchor="middle" className="donut-pct">{Math.round(top[1] * 100)}%</text>
          </>
        )}
      </svg>
      <div className="donut-legend">
        {title && <div className="sub-label">{title}</div>}
        {entries.map(([site, v]) => (
          <div className="donut-key" key={site}>
            <i style={{ background: SITE_COLOR[site] || rampColor(v) }} />
            <span>{site}</span>
            <b>{Math.round(v * 100)}%</b>
          </div>
        ))}
        {entries.length === 0 && <div className="muted small">No site data yet.</div>}
      </div>
    </div>
  );
}
