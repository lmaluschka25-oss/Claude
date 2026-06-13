import Heatmap from "../components/Heatmap.jsx";
import {
  EnemyProfiles,
  MatchMemory,
  PatternRecognition,
  PositionProbabilities,
} from "../components/panels.jsx";

export default function LearningsView({ intelligence, mapMeta }) {
  if (!intelligence) {
    return <div className="view"><div className="panel"><div className="panel-body empty">Select a match to see what the system has learned.</div></div></div>;
  }
  return (
    <div className="view learnings-view">
      <div className="grid-2">
        <MatchMemory memory={intelligence.match_memory} />
        <PositionProbabilities probs={intelligence.position_probabilities} />
      </div>
      <PatternRecognition patterns={intelligence.patterns} />
      <EnemyProfiles profiles={intelligence.enemy_profiles} />
      <Heatmap cells={intelligence.heatmap} mapMeta={mapMeta} />
    </div>
  );
}
