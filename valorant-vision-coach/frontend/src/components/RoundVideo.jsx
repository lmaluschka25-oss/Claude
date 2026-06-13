import { api } from "../api/client.js";

export default function RoundVideo({ round }) {
  return (
    <div className="panel video-panel">
      <div className="panel-head"><h3>ORIGINAL ROUND VIDEO</h3></div>
      <div className="panel-body">
        {round && round.status === "completed" ? (
          <video
            key={round.id}
            className="round-video"
            src={api.roundVideoUrl(round.id)}
            controls
            preload="metadata"
          />
        ) : (
          <div className="video-placeholder">
            {round
              ? round.status === "processing"
                ? `Analyzing… ${Math.round((round.progress || 0) * 100)}%`
                : "Round not analyzed yet."
              : "Select a round to view its recording."}
          </div>
        )}
      </div>
    </div>
  );
}
