import { useCallback, useEffect, useState } from "react";
import { api } from "./api/client.js";
import MatchUpload from "./components/MatchUpload.jsx";
import MatchList from "./components/MatchList.jsx";
import PredictionCard from "./components/PredictionCard.jsx";

export default function App() {
  const [info, setInfo] = useState(null);
  const [maps, setMaps] = useState([]);
  const [matches, setMatches] = useState([]);
  const [selectedId, setSelectedId] = useState(null);
  const [detail, setDetail] = useState(null);
  const [mapMeta, setMapMeta] = useState(null);
  const [prediction, setPrediction] = useState(null);
  const [error, setError] = useState(null);

  const loadMatches = useCallback(async () => {
    try {
      setMatches(await api.listMatches());
    } catch (e) {
      setError(e.message);
    }
  }, []);

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
      api.getPrediction(id).then(setPrediction).catch(() => setPrediction(null));
      if (d.map_name) {
        api.getMap(d.map_name).then(setMapMeta).catch(() => setMapMeta(null));
      } else {
        setMapMeta(null);
      }
    } catch (e) {
      setError(e.message);
    }
  }, []);

  // Load the prediction once a selected match finishes processing.
  useEffect(() => {
    if (!selectedId) return;
    const summary = matches.find((m) => m.id === selectedId);
    if (summary && summary.status === "completed" && (!detail || detail.id !== selectedId)) {
      loadDetail(selectedId);
    }
  }, [matches, selectedId, detail, loadDetail]);

  function handleSelect(m) {
    setSelectedId(m.id);
    setPrediction(null);
    if (m.status === "completed") {
      loadDetail(m.id);
    } else {
      setDetail(null);
      setMapMeta(null);
    }
  }

  async function handleDelete(m) {
    if (!confirm(`"${m.filename}" und die Auswertung löschen?`)) return;
    try {
      await api.deleteMatch(m.id);
      if (selectedId === m.id) {
        setSelectedId(null);
        setDetail(null);
        setPrediction(null);
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
            <small>Site-Vorhersage · Scouting aus Aufnahmen</small>
          </div>
        </div>
        <div className="header-meta">
          {info && (
            <>
              <span>
                <span className={`dot ${info.detector_ready ? "ok" : "off"}`} />
                detector: {info.detector_backend}
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
            Reine Post-Match-Analyse aus deinen Aufnahmen. Keine Live-Daten, kein
            Speicher-Zugriff, keine versteckten Infos.
          </div>
        </aside>

        <main className="main">
          {error && <div className="error-banner">{error}</div>}

          {!selectedId && (
            <div className="panel">
              <div className="panel-body empty">
                Nimm eine Runde auf (oder lade eine Aufnahme hoch) und wähle sie
                aus — dann erscheint hier die Site-Vorhersage für die nächste Runde.
              </div>
            </div>
          )}

          {selectedId && !ready && (
            <div className="panel">
              <div className="panel-body empty">
                {detail?.status === "failed"
                  ? `Auswertung fehlgeschlagen: ${detail.status_detail || "unbekannter Fehler"}`
                  : "Wird ausgewertet … die Vorhersage erscheint automatisch, sobald es fertig ist."}
              </div>
            </div>
          )}

          {ready && <PredictionCard prediction={prediction} mapMeta={mapMeta} />}
        </main>
      </div>
    </div>
  );
}
