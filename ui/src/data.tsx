import { createContext, useCallback, useContext, useEffect, useMemo, useState, type ReactNode } from "react";
import { fetchRuns, fetchSummary } from "./api";
import type { RunListItem, Summary } from "./types";

interface DataState {
  summary: Summary | null;
  runs: RunListItem[];
  runId: string | undefined;
  loading: boolean;
  error: string;
  selectRun: (id: string) => Promise<void>;
  reload: () => Promise<void>;
}

const DataContext = createContext<DataState | null>(null);

export function DataProvider({ children }: { children: ReactNode }) {
  const [summary, setSummary] = useState<Summary | null>(null);
  const [runs, setRuns] = useState<RunListItem[]>([]);
  const [runId, setRunId] = useState<string | undefined>(undefined);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  const load = useCallback(async (id?: string) => {
    setError("");
    try {
      const all = await fetchRuns();
      setRuns(all);
      const data = await fetchSummary(id);
      setSummary(data);
      setRunId(data.run_id);
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    void load();
  }, [load]);

  const selectRun = useCallback(
    async (id: string) => {
      setLoading(true);
      await load(id);
    },
    [load],
  );

  const reload = useCallback(async () => {
    await load(runId);
  }, [load, runId]);

  const value = useMemo(
    () => ({ summary, runs, runId, loading, error, selectRun, reload }),
    [summary, runs, runId, loading, error, selectRun, reload],
  );

  return <DataContext.Provider value={value}>{children}</DataContext.Provider>;
}

export function useData(): DataState {
  const value = useContext(DataContext);
  if (!value) throw new Error("useData outside DataProvider");
  return value;
}
