import { useEffect, useRef, useState } from "react";
import { startRun } from "../api";
import { useData } from "../data";

export function RunButton() {
  const { reload } = useData();
  const [running, setRunning] = useState(false);
  const [count, setCount] = useState(0);
  const [error, setError] = useState("");
  const sourceRef = useRef<EventSource | null>(null);

  useEffect(() => {
    return () => {
      sourceRef.current?.close();
    };
  }, []);

  const begin = async () => {
    setError("");
    setRunning(true);
    setCount(0);
    try {
      const out = await startRun({ quick: true });
      const es = new EventSource("/api/run/stream");
      sourceRef.current = es;
      const onEpisode = () => setCount((c) => c + 1);
      const onSnapshot = (event: MessageEvent) => {
        try {
          const data = JSON.parse(event.data) as { status?: string; run_id?: string };
          if (data.status === "completed" && data.run_id === out.run_id) {
            es.close();
            sourceRef.current = null;
            setRunning(false);
            void reload();
          }
          if (data.status === "failed" || data.status === "cancelled") {
            es.close();
            sourceRef.current = null;
            setRunning(false);
            setError(`Run ${data.status}`);
          }
        } catch {
          return;
        }
      };
      es.addEventListener("episode", onEpisode);
      es.addEventListener("snapshot", onSnapshot as EventListener);
      es.onerror = () => {
        if (es.readyState === EventSource.CLOSED) {
          setRunning(false);
        }
      };
    } catch (err) {
      setRunning(false);
      setError(err instanceof Error ? err.message : String(err));
    }
  };

  return (
    <div className="run-control">
      <button type="button" className="btn btn-primary" onClick={() => void begin()} disabled={running}>
        {running ? <span className="spinner" aria-hidden="true" /> : null}
        {running ? `Running${count ? ` · ${count}` : ""}` : "Run quick smoke"}
      </button>
      {error ? <span className="run-error" title={error}>Run failed</span> : null}
    </div>
  );
}
