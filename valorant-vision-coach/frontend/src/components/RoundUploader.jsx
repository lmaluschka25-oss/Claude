import { useEffect, useRef, useState } from "react";
import { api } from "../api/client.js";
import { formatClock } from "../util.js";

// Add a round to a match by recording the screen (analyzed AFTER you stop) or
// uploading a recording. Both feed the same post-match pipeline.
export default function RoundUploader({ matchId, onUploaded }) {
  const fileRef = useRef(null);
  const [progress, setProgress] = useState(null);
  const [error, setError] = useState(null);
  const [recording, setRecording] = useState(false);
  const [elapsed, setElapsed] = useState(0);
  const recRef = useRef(null);
  const chunksRef = useRef([]);
  const timerRef = useRef(null);

  useEffect(
    () => () => {
      clearInterval(timerRef.current);
      if (recRef.current && recRef.current.state !== "inactive") recRef.current.stop();
    },
    []
  );

  async function uploadFile(file) {
    setError(null);
    setProgress(0);
    try {
      await api.uploadRound(matchId, file, null, setProgress);
      setProgress(null);
      onUploaded?.();
    } catch (e) {
      setError(e.message);
      setProgress(null);
    }
  }

  async function startRecording() {
    setError(null);
    if (!navigator.mediaDevices?.getDisplayMedia) {
      setError("Screen capture not supported in this browser.");
      return;
    }
    let stream;
    try {
      stream = await navigator.mediaDevices.getDisplayMedia({ video: { frameRate: 30 }, audio: false });
    } catch {
      setError("Screen share cancelled.");
      return;
    }
    const mime = MediaRecorder.isTypeSupported("video/webm;codecs=vp8")
      ? "video/webm;codecs=vp8"
      : "video/webm";
    const rec = new MediaRecorder(stream, { mimeType: mime });
    chunksRef.current = [];
    rec.ondataavailable = (e) => e.data?.size && chunksRef.current.push(e.data);
    rec.onstop = async () => {
      stream.getTracks().forEach((t) => t.stop());
      clearInterval(timerRef.current);
      setRecording(false);
      const blob = new Blob(chunksRef.current, { type: "video/webm" });
      await uploadFile(new File([blob], `round-${Date.now()}.webm`, { type: "video/webm" }));
    };
    stream.getVideoTracks()[0].addEventListener("ended", () => {
      if (rec.state !== "inactive") rec.stop();
    });
    recRef.current = rec;
    rec.start(1000);
    setRecording(true);
    setElapsed(0);
    timerRef.current = setInterval(() => setElapsed((s) => s + 1), 1000);
  }

  const busy = progress != null;

  return (
    <div className="uploader">
      {!recording ? (
        <button className="btn primary block" onClick={startRecording} disabled={busy}>
          ● Record round
        </button>
      ) : (
        <button className="btn danger block" onClick={() => recRef.current?.stop()}>
          ■ Stop ({formatClock(elapsed)})
        </button>
      )}
      <label className="btn ghost block" style={{ textAlign: "center", cursor: "pointer" }}>
        {busy ? `Uploading ${Math.round(progress * 100)}%` : "Upload recording"}
        <input
          ref={fileRef}
          type="file"
          accept="video/*"
          hidden
          disabled={busy || recording}
          onChange={(e) => e.target.files?.[0] && uploadFile(e.target.files[0])}
        />
      </label>
      {busy && (
        <div className="progress">
          <span style={{ width: `${Math.round(progress * 100)}%` }} />
        </div>
      )}
      {error && <div className="error-banner">{error}</div>}
    </div>
  );
}
