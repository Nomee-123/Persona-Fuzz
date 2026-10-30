import type { Episode, EpisodeRow, PolicyBundle, RunListItem, Summary } from "./types";

async function getJson<T>(url: string): Promise<T> {
  const res = await fetch(url);
  if (!res.ok) {
    const text = await res.text();
    throw new Error(text || `${res.status} ${res.statusText}`);
  }
  return (await res.json()) as T;
}

export function fetchSummary(runId?: string): Promise<Summary> {
  return getJson<Summary>(`/api/run${runId ? `?run_id=${encodeURIComponent(runId)}` : ""}`);
}

export function fetchRuns(): Promise<RunListItem[]> {
  return getJson<RunListItem[]>("/api/runs");
}

export function fetchPolicy(runId?: string): Promise<PolicyBundle> {
  return getJson<PolicyBundle>(`/api/policy${runId ? `?run_id=${encodeURIComponent(runId)}` : ""}`);
}

export function fetchEpisodes(
  params: {
    runId?: string;
    condition?: string;
    task?: string;
    vector?: string;
    attack?: string;
    leak?: string;
    limit?: number;
    offset?: number;
  },
): Promise<{ total: number; episodes: EpisodeRow[] }> {
  const q = new URLSearchParams();
  if (params.runId) q.set("run_id", params.runId);
  if (params.condition) q.set("condition", params.condition);
  if (params.task) q.set("task_class", params.task);
  if (params.vector) q.set("vector", params.vector);
  if (params.vector) q.set("vector", params.vector);
  if (params.attack) q.set("attack", params.attack);
  if (params.leak) q.set("leak", params.leak);
  q.set("limit", String(params.limit ?? 200));
  q.set("offset", String(params.offset ?? 0));
  return getJson<{ total: number; episodes: EpisodeRow[] }>(`/api/episodes?${q.toString()}`);
}

export function fetchEpisode(episodeId: string, runId?: string): Promise<Episode> {
  return getJson<Episode>(`/api/episodes/${encodeURIComponent(episodeId)}${runId ? `?run_id=${encodeURIComponent(runId)}` : ""}`);
}

export async function startRun(body: { quick?: boolean; offline?: boolean; model?: string; runId?: string }): Promise<{ run_id: string }> {
  const res = await fetch("/api/run", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      quick: body.quick ?? true,
      offline: body.offline ?? false,
      model: body.model ?? "",
      run_id: body.runId,
    }),
  });
  if (!res.ok) throw new Error(await res.text());
  return (await res.json()) as { run_id: string };
}

export function openshellUrl(runId?: string): string {
  return `/api/policy/openshell${runId ? `?run_id=${encodeURIComponent(runId)}` : ""}`;
}

export function exportUrl(runId?: string): string {
  return `/api/export${runId ? `?run_id=${encodeURIComponent(runId)}` : ""}`;
}
