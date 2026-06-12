import { pressureColor } from "../util.js";

export default function SitePressurePanel({ sitePressure }) {
  return (
    <div className="panel">
      <div className="panel-header">
        <h2>Site Pressure</h2>
      </div>
      <div className="panel-body">
        {sitePressure.length === 0 && <div className="empty">No site data for this map.</div>}
        <div className="pressure-grid">
          {sitePressure.map((sp) => (
            <div className="pressure-row" key={sp.site}>
              <div className="site-name">{sp.site}</div>
              <div className="bar">
                <span
                  style={{
                    width: `${Math.round(sp.pressure * 100)}%`,
                    background: pressureColor(sp.pressure),
                  }}
                />
              </div>
              <div className="mono faint" style={{ textAlign: "right" }}>
                {Math.round(sp.pressure * 100)}%
                <div style={{ fontSize: 10 }}>{sp.enemy_count.toFixed(1)} ens</div>
              </div>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}
