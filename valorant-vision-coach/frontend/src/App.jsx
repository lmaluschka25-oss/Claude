import { useCallback, useEffect, useRef, useState } from "react";
import { api } from "./api/client.js";
import MatchUpload from "./components/MatchUpload.jsx";
import MatchList from "./components/MatchList.jsx";
import MapView from "./components/MapView.jsx";
import Timeline from "./components/Timeline.jsx";
import LastKnownPanel from "./components/LastKnownPanel.jsx";
import RotationPanel from "./components/RotationPanel.jsx";
import SitePressurePanel from "./components/SitePressurePanel.jsx";

export default function App() {
  const [info, setInfo] = useState(null);
  const [maps, setMaps] = useState([]);
  const [matches, setMatches] = useState([]);
  const [selectedId, setSelectedId] = useState(null);
  const [detail, setDetail] = useState(null);
  const [mapMeta, setMapMeta] = useState(null);
  const [snapshot, setSnapshot] = useState(null);
  const [at, setAt] = useState(0);
  const [ttl, setTtl] = useState(12);
  const [playing, setPlaying] = useState(false);
  const [error, setError] = useState(null);

  const atRef = useRef(at);
  const ttlRef = useRef(ttl);
  atRef.current = at;
  ttlRef.current = ttl;

  const loadMatches = useCallback(async () => {
    try {
      setMatches(await api.listMatches());
    } catch (e) {
      setError(e.message);
    }
  }, []);

  // Initial load.
  useEffect(() => {
    api.systemInfo().then(setInfo).catch((e) => setError(e.message));
    api.listMaps().then(setMaps).catch(() => {});
    loadMatches();
  }, [loadMatches]);

  // Poll while anything is still processing.
  useEffect(() => {
    const busy = matches.some((m) => m.status === "processing" || m.status === "pending");
    if (!busy) return;
    const id = setInterval(loadMatches, 2000);
    return () => clearInterval(id);
  }, [matches, loadMatches]);

  const loadDetail = useCallback(async (id) => {
    try {
      const d = await api.getMatch(id);
      setDetail(d);
      setAt(d.duration_seconds || 0);
      setPlaying(false);
      if (d.map_name) {
        api.getMap(d.map_name).then(setMapMeta).catch(() => setMapMeta(null));
      } else {
        setMapMeta(null);
      }
    } catch (e) {
      setError(e.message);
    }
  }, []);

  // When a selected match finishes processing, load its full detail.
  useEffect(() => {
    if (!selectedId) return;
    const summary = matches.find((m) => m.id === selectedId);
    if (summary && summary.status === "completed" && (!detail || detail.id !== selectedId)) {
      loadDetail(selectedId);
    }
  }, [matches, selectedId, detail, loadDetail]);

  // Throttled snapshot refresh: re-fetch only when at/ttl actually changed.
  useEffect(() => {
    if (!detail || detail.status !== "completed") {
      setSnapshot(null);
      return;
    }
    let cancelled = false;
    let lastKey = null;
    const fetchSnap = async () => {
      const key = `${atRef.current.toFixed(2)}|${ttlRef.current}`;
      if (key === lastKey) return;
      lastKey = key;
      try {
        const snap = await api.getSnapshot(detail.id, atRef.current, ttlRef.current);
        if (!cancelled) setSnapshot(snap);
      } catch (e) {
        if (!cancelled) setError(e.message);
      }
    };
    fetchSnap();
    const id = setInterval(fetchSnap, 200);
    return () => {
      cancelled = true;
      clearInterval(id);
    };
  }, [detail]);

  function handleSelect(m) {
    setSelectedId(m.id);
    setSnapshot(null);
    if (m.status === "completed") {
      loadDetail(m.id);
    } else {
      setDetail(null);
      setMapMeta(null);
    }
  }

  async function handleDelete(m) {
    if (!confirm(`Delete "${m.filename}" and its analysis?`)) return;
    try {
      await api.deleteMatch(m.id);
      if (selectedId === m.id) {
        setSelectedId(null);
        setDetail(null);
        setSnapshot(null);
      }
      loadMatches();
    } catch (e) {
      setError(e.message);
    }
  }

  const ready = detail && detail.status === "completed";

  return (
    <div className="app">
      <header className="app-header">
        <div className="brand">
          <div className="logo">VC</div>
          <div>
            <h1>Valorant Vision Coach</h1>
            <small>Post-match analysis · on-screen vision only</small>
          </div>
        </div>
        <div className="header-meta">
          {info && (
            <>
              <span>
                <span className={`dot ${info.detector_ready ? "ok" : "off"}`} />
                detector: {info.detector_backend}
              </span>
              <span>
                <span className={`dot ${info.ocr_ready ? "ok" : "off"}`} />
                ocr: {info.ocr_backend}
              </span>
              <span>v{info.version}</span>
            </>
          )}
        </div>
      </header>

      <div className="layout">
        <aside className="sidebar">
          <MatchUpload maps={maps} onUploaded={loadMatches} />
          <MatchList
            matches={matches}
            selectedId={selectedId}
            onSelect={handleSelect}
            onDelete={handleDelete}
          />
          <div className="notice">
            Reads only what was on your screen — viewport, minimap, killfeed,
            scoreboard, timer. No memory reads, no packets, no hidden info.
          </div>
        </aside>

        <main className="main">
          {error && <div className="error-banner">{error}</div>}

          {!selectedId && (
            <div className="panel">
              <div className="panel-body empty">
                Upload a recorded match and select it to open the tactical dashboard.
              </div>
            </div>
          )}

          {selectedId && !ready && (
            <div className="panel">
              <div className="panel-body empty">
                {detail?.status === "failed"
                  ? `Processing failed: ${detail.status_detail || "unknown error"}`
                  : "Processing… the dashboard opens automatically when analysis is ready."}
              </div>
            </div>
          )}

          {ready && (
            <>
              <Timeline
                duration={detail.duration_seconds || 0}
                at={at}
                onScrub={setAt}
                playing={playing}
                setPlaying={setPlaying}
                ttl={ttl}
                onTtl={setTtl}
              />
              <div className="grid-2">
                <div className="panel">
                  <div className="panel-header">
                    <h2>{mapMeta?.display_name || detail.map_name || "Map"}</h2>
                    <span className="faint">{detail.detections_count} detections</span>
                  </div>
                  <div className="panel-body">
                    <MapView mapMeta={mapMeta} snapshot={snapshot} />
                    <div className="legend">
                      <span>
                        <span className="swatch" style={{ background: "#ff4655" }} />
                        last known enemy
                      </span>
                      <span>
                        <span className="swatch" style={{ background: "#ffb454" }} />
                        likely rotation
                      </span>
                      <span>
                        <span className="swatch" style={{ background: "#19c3a6" }} />
                        site pressure
                      </span>
                    </div>
                  </div>
                </div>
                <div style={{ display: "flex", flexDirection: "column", gap: 16 }}>
                  <LastKnownPanel lastKnown={snapshot?.last_known || []} />
                  <SitePressurePanel sitePressure={snapshot?.site_pressure || []} />
                </div>
              </div>
              <RotationPanel rotations={snapshot?.rotations || []} />
            </>
          )}
        </main>
      </div>
    </div>
  );
}
