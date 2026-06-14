import { useCallback, useEffect, useMemo, useState } from "react";
import { api } from "./api/client.js";
import { cx } from "./util.js";
import TopNav from "./components/TopNav.jsx";
import MatchSidebar from "./components/MatchSidebar.jsx";
import EnlargedMinimap from "./components/EnlargedMinimap.jsx";
import RoundView from "./components/RoundView.jsx";
import RoundTimeline from "./components/RoundTimeline.jsx";
import NextRoundHero from "./components/NextRoundHero.jsx";
import { DetectedInfo, DetectedPositions } from "./components/panels.jsx";
import MatchesView from "./views/MatchesView.jsx";
import LearningsView from "./views/LearningsView.jsx";
import SettingsView from "./views/SettingsView.jsx";

export default function App() {
  const [info, setInfo] = useState(null);
  const [maps, setMaps] = useState([]);
  const [matches, setMatches] = useState([]);
  const [tab, setTab] = useState("MATCHES");
  const [matchId, setMatchId] = useState(null);
  const [detail, setDetail] = useState(null);
  const [intel, setIntel] = useState(null);
  const [mapMeta, setMapMeta] = useState(null);
  const [roundId, setRoundId] = useState(null);
  const [error, setError] = useState(null);

  const refreshMatches = useCallback(async () => {
    try {
      setMatches(await api.listMatches());
    } catch (e) {
      setError(e.message);
    }
  }, []);

  useEffect(() => {
    api.systemInfo().then(setInfo).catch((e) => setError(e.message));
    api.listMaps().then(setMaps).catch(() => {});
    refreshMatches();
  }, [refreshMatches]);

  const loadMatch = useCallback(async (id, rid = null) => {
    try {
      const [d, intelligence] = await Promise.all([api.getMatch(id), api.getIntelligence(id, rid)]);
      setDetail(d);
      setIntel(intelligence);
      setRoundId(rid ?? intelligence.current_round?.id ?? null);
      // Prefer the map the analysis resolved (a round may detect the map even
      // when the match was created without one) so the board always renders.
      const mapName =
        intelligence.match?.map_name ||
        intelligence.current_round?.map_name ||
        intelligence.detected_info?.map_name ||
        d.map_name;
      if (mapName) api.getMap(mapName).then(setMapMeta).catch(() => setMapMeta(null));
      else setMapMeta(null);
    } catch (e) {
      setError(e.message);
    }
  }, []);

  useEffect(() => {
    if (matchId != null) loadMatch(matchId);
  }, [matchId, loadMatch]);

  const processing = useMemo(
    () => (detail?.rounds || []).some((r) => r.status === "processing" || r.status === "pending"),
    [detail]
  );
  useEffect(() => {
    if (!processing || matchId == null) return;
    const id = setInterval(() => loadMatch(matchId, roundId), 2500);
    return () => clearInterval(id);
  }, [processing, matchId, roundId, loadMatch]);

  async function createMatch(body) {
    const m = await api.createMatch(body);
    await refreshMatches();
    setMatchId(m.id);
    setTab("ANALYSIS");
  }
  function selectMatch(m) {
    setMatchId(m.id);
    setRoundId(null);
    setTab("ANALYSIS");
  }
  async function deleteMatch(id) {
    if (!confirm("Delete this match and all its rounds?")) return;
    await api.deleteMatch(id);
    if (matchId === id) {
      setMatchId(null);
      setDetail(null);
      setIntel(null);
    }
    refreshMatches();
  }
  function selectRound(r) {
    setRoundId(r.id);
    if (r.status === "completed") loadMatch(matchId, r.id);
  }
  async function reanalyze(roundId) {
    try {
      await api.reanalyzeRound(roundId);
      if (matchId != null) loadMatch(matchId, roundId);
    } catch (e) {
      setError(e.message);
    }
  }
  async function updateSide(side) {
    if (matchId == null) return;
    try {
      await api.updateMatch(matchId, { side });
      await Promise.all([refreshMatches(), loadMatch(matchId, roundId)]);
    } catch (e) {
      setError(e.message);
    }
  }

  const selectedRound =
    (detail?.rounds || []).find((r) => r.id === roundId) || intel?.current_round || null;
  const calibrationRound =
    (detail?.rounds || []).find((r) => r.status === "completed") || null;

  return (
    <div className="app">
      <TopNav tab={tab} onTab={setTab} info={info} />
      <main className={cx("content", tab === "ANALYSIS" && "fit")}>
      {error && (
        <div className="error-banner top">{error}<button onClick={() => setError(null)}>✕</button></div>
      )}

      {tab === "MATCHES" && (
        <MatchesView
          matches={matches} maps={maps} selectedId={matchId}
          onCreate={createMatch} onSelect={selectMatch} onDelete={deleteMatch}
        />
      )}
      {tab === "LEARNINGS" && <LearningsView intelligence={intel} mapMeta={mapMeta} />}
      {tab === "SETTINGS" && (
        <SettingsView
          info={info} intelligence={intel} calibrationRound={calibrationRound} onReanalyze={reanalyze}
        />
      )}

      {tab === "ANALYSIS" && (
        <div className="analysis">
          {!detail ? (
            <div className="panel"><div className="panel-body empty">
              Select or create a match in the MATCHES tab to begin.
            </div></div>
          ) : (
            <>
              <div className="row-top">
                <MatchSidebar
                  match={detail} intelligence={intel} selectedRoundId={roundId}
                  onSelectRound={selectRound} onNewMatch={() => setTab("MATCHES")}
                  onUploaded={() => loadMatch(matchId, roundId)} onUpdateSide={updateSide}
                />
                <div className="center-col">
                  <NextRoundHero
                    rec={intel?.recommendation}
                    probs={intel?.position_probabilities || []}
                    roundsAnalyzed={intel?.match_memory?.rounds_analyzed || 0}
                  />
                  <EnlargedMinimap mapMeta={mapMeta} markers={intel?.minimap_markers || []} />
                </div>
                <div className="right-col">
                  <RoundView round={selectedRound} />
                  <DetectedInfo info={intel?.detected_info} />
                  <DetectedPositions positions={intel?.detected_positions} />
                </div>
              </div>
              <RoundTimeline events={intel?.timeline} />
              <div className="analysis-hint muted small">
                Deeper read — patterns, profiles, heatmap and the full analysis log — is in the
                <button className="linkbtn" onClick={() => setTab("LEARNINGS")}>LEARNINGS</button> tab.
              </div>
            </>
          )}
        </div>
      )}
      </main>

      <footer className="appfoot">
        <span>Match Analyzer v{info?.version || "1.0.0"}</span>
        <span>Detector: {info?.detector_backend || "—"} · on-screen analysis only</span>
      </footer>
    </div>
  );
}
