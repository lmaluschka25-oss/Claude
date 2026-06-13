import { useCallback, useEffect, useMemo, useState } from "react";
import { api } from "./api/client.js";
import TopNav from "./components/TopNav.jsx";
import MatchSidebar from "./components/MatchSidebar.jsx";
import EnlargedMinimap from "./components/EnlargedMinimap.jsx";
import RoundVideo from "./components/RoundVideo.jsx";
import RoundTimeline from "./components/RoundTimeline.jsx";
import Heatmap from "./components/Heatmap.jsx";
import {
  AnalysisLog,
  DetectedInfo,
  DetectedPositions,
  EnemyProfiles,
  MatchMemory,
  PatternRecognition,
  PositionProbabilities,
  ReasoningPanel,
  RecommendationPanel,
  UtilityDetected,
  WeaponEconomy,
} from "./components/panels.jsx";
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
      if (d.map_name) api.getMap(d.map_name).then(setMapMeta).catch(() => setMapMeta(null));
      else setMapMeta(null);
    } catch (e) {
      setError(e.message);
    }
  }, []);

  useEffect(() => {
    if (matchId != null) loadMatch(matchId);
  }, [matchId, loadMatch]);

  // Poll while any round is still processing.
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

  const selectedRound =
    (detail?.rounds || []).find((r) => r.id === roundId) || intel?.current_round || null;
  const calibrationRound =
    (detail?.rounds || []).find((r) => r.status === "completed") || null;

  return (
    <div className="app">
      <TopNav tab={tab} onTab={setTab} info={info} />
      {error && <div className="error-banner top">{error}<button onClick={() => setError(null)}>✕</button></div>}

      {tab === "MATCHES" && (
        <MatchesView
          matches={matches} maps={maps} selectedId={matchId}
          onCreate={createMatch} onSelect={selectMatch} onDelete={deleteMatch}
        />
      )}

      {tab === "LEARNINGS" && <LearningsView intelligence={intel} mapMeta={mapMeta} />}
      {tab === "SETTINGS" && <SettingsView info={info} calibrationRound={calibrationRound} />}

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
                  onUploaded={() => loadMatch(matchId, roundId)}
                />
                <EnlargedMinimap mapMeta={mapMeta} markers={intel?.minimap_markers || []} />
                <div className="right-col">
                  <RoundVideo round={selectedRound} />
                  <div className="grid-2">
                    <DetectedInfo info={intel?.detected_info} />
                    <UtilityDetected utilities={intel?.utilities} />
                  </div>
                </div>
              </div>

              <RoundTimeline events={intel?.timeline} />

              <div className="grid-4">
                <DetectedPositions positions={intel?.detected_positions} />
                <PositionProbabilities probs={intel?.position_probabilities} />
                <PatternRecognition patterns={intel?.patterns} />
                <Heatmap cells={intel?.heatmap} mapMeta={mapMeta} />
              </div>

              <div className="grid-3">
                <MatchMemory memory={intel?.match_memory} />
                <EnemyProfiles profiles={intel?.enemy_profiles} />
                <WeaponEconomy economy={intel?.weapon_economy} />
              </div>

              <div className="grid-2">
                <RecommendationPanel rec={intel?.recommendation} />
                <ReasoningPanel rec={intel?.recommendation} />
              </div>

              <AnalysisLog steps={intel?.analysis_log} />
            </>
          )}
        </div>
      )}

      <footer className="appfoot">
        <span>Match Analyzer v{info?.version || "1.0.0"}</span>
        <span>Detector: {info?.detector_backend || "—"} · on-screen analysis only</span>
      </footer>
    </div>
  );
}
