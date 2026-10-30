import { useEffect, useMemo, useState } from "react";
import { fetchEpisode, fetchEpisodes } from "../api";
import { Badge } from "../components/Badge";
import { Drawer } from "../components/Drawer";
import { useData } from "../data";
import { compact, num, shortId } from "../format";
import type { Condition, Episode, EpisodeRow, TaskClass } from "../types";

const CONDITIONS: (Condition | "")[] = ["", "D0", "D1", "D2", "D3", "D4"];
const TASKS: (TaskClass | "")[] = ["", "inbox", "schedule", "research"];
const VECTORS = ["", "email", "calendar", "web"];

export function AttackExplorer() {
  const { summary } = useData();
  const [condition, setCondition] = useState<Condition | "">("");
  const [task, setTask] = useState<TaskClass | "">("");
  const [vector, setVector] = useState("");
  const [leak, setLeak] = useState("");
  const [search, setSearch] = useState("");
  const [rows, setRows] = useState<EpisodeRow[]>([]);
  const [total, setTotal] = useState(0);
  const [page, setPage] = useState(0);
  const limit = 40;
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [selected, setSelected] = useState<Episode | null>(null);
  const [traceLoading, setTraceLoading] = useState(false);

  useEffect(() => {
    setPage(0);
  }, [condition, task, vector, leak]);

  useEffect(() => {
    if (!summary) return;
    setLoading(true);
    fetchEpisodes({
      runId: summary.run_id,
      condition: condition || undefined,
      task: task || undefined,
      vector: vector || undefined,
      attack: "true",
      leak: leak || undefined,
      limit,
      offset: page * limit,
    })
      .then((res) => {
        setRows(res.episodes);
        setTotal(res.total);
        setError("");
      })
      .catch((err) => setError(err instanceof Error ? err.message : String(err)))
      .finally(() => setLoading(false));
  }, [summary, condition, task, vector, leak, page]);

  const visible = useMemo(() => {
    if (!search.trim()) return rows;
    const needle = search.toLowerCase();
    return rows.filter(
      (row) =>
        row.persona_id.toLowerCase().includes(needle) ||
        row.episode_id.toLowerCase().includes(needle) ||
        (row.attack?.template_id ?? "").toLowerCase().includes(needle),
    );
  }, [rows, search]);

  const open = async (row: EpisodeRow) => {
    setTraceLoading(true);
    try {
      const ep = await fetchEpisode(row.episode_id, summary?.run_id);
      setSelected(ep);
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
    } finally {
      setTraceLoading(false);
    }
  };

  return (
    <div className="page">
      <div className="page-head">
        <div>
          <div className="eyebrow">Attack explorer</div>
          <h2>Every attempt, every gateway decision</h2>
          <p>Filter held-out and extended episodes. Click a row for the full trace, canaries and blocked sink calls.</p>
        </div>
        <Badge tone="neutral">{num(total)} episodes</Badge>
      </div>

      <div className="filter-bar">
        <label>
          <span>Condition</span>
          <select value={condition} onChange={(e) => setCondition(e.target.value as Condition | "")}>
            {CONDITIONS.map((c) => <option key={c || "all"} value={c}>{c || "All"}</option>)}
          </select>
        </label>
        <label>
          <span>Task</span>
          <select value={task} onChange={(e) => setTask(e.target.value as TaskClass | "")}>
            {TASKS.map((t) => <option key={t || "all"} value={t}>{t || "All"}</option>)}
          </select>
        </label>
        <label>
          <span>Vector</span>
          <select value={vector} onChange={(e) => setVector(e.target.value)}>
            {VECTORS.map((v) => <option key={v || "all"} value={v}>{v || "All"}</option>)}
          </select>
        </label>
        <label>
          <span>Leak</span>
          <select value={leak} onChange={(e) => setLeak(e.target.value)}>
            <option value="">All</option>
            <option value="true">Leaked</option>
            <option value="false">Blocked</option>
          </select>
        </label>
        <label className="filter-search">
          <span>Search</span>
          <input value={search} onChange={(e) => setSearch(e.target.value)} placeholder="persona, episode or template" />
        </label>
      </div>

      {error ? <p className="error-line">{error}</p> : null}
      {loading ? <div className="empty-state small"><span className="spinner" /> Loading episodes…</div> : null}

      <div className="panel">
        <div className="table-wrap">
          <table className="episode-table">
            <thead>
              <tr>
                <th>Episode</th>
                <th>Persona</th>
                <th>Condition</th>
                <th>Task</th>
                <th>Injection</th>
                <th>Leak</th>
                <th>Utility</th>
                <th>Blocked</th>
                <th>Tokens</th>
                <th>Latency</th>
              </tr>
            </thead>
            <tbody>
              {visible.map((row) => (
                <tr key={row.episode_id} onClick={() => void open(row)} tabIndex={0} onKeyDown={(e) => { if (e.key === "Enter") void open(row); }} className="clickable">
                  <td className="mono">{shortId(row.episode_id)}</td>
                  <td className="mono">{row.persona_id}</td>
                  <td><Badge tone={row.condition === "D0" ? "bad" : row.condition === "D4" ? "good" : "neutral"}>{row.condition}</Badge></td>
                  <td>{row.task_class}<div className="cell-sub">{row.split}</div></td>
                  <td>
                    {row.attack ? (
                      <>
                        <span className="vector-tag">{row.attack.vector}</span>
                        <div className="cell-sub">{row.attack.template_id}{row.attack.adaptive_round ? ` · round ${row.attack.adaptive_round}` : ""}</div>
                      </>
                    ) : <span className="muted">benign</span>}
                  </td>
                  <td>{row.outcome.leak.detected ? <Badge tone="bad">leaked</Badge> : <Badge tone="good">blocked</Badge>}</td>
                  <td>{row.outcome.utility_ok ? <Badge tone="good">ok</Badge> : <Badge tone="warn">failed</Badge>}</td>
                  <td>{row.outcome.blocked_count}</td>
                  <td>{num(row.tokens)}</td>
                  <td>{row.latency_ms.toFixed(0)} ms</td>
                </tr>
              ))}
              {!visible.length && !loading ? <tr><td colSpan={10} className="empty-cell">No episodes match these filters.</td></tr> : null}
            </tbody>
          </table>
        </div>
        <div className="table-foot table-nav">
          <span>{total} matching episodes · page {page + 1} of {Math.max(1, Math.ceil(total / limit))} · deterministic predicates only</span>
          <span className="pager">
            <button type="button" className="btn small" disabled={page === 0 || loading} onClick={() => setPage((p) => Math.max(0, p - 1))}>Previous</button>
            <button type="button" className="btn small" disabled={(page + 1) * limit >= total || loading} onClick={() => setPage((p) => p + 1)}>Next</button>
          </span>
        </div>
      </div>

      <Drawer
        open={!!selected}
        onClose={() => setSelected(null)}
        title={selected ? selected.episode_id : "Trace"}
        subtitle={selected ? <>{selected.persona_id} · {selected.condition} · {selected.task_class} · {selected.model}</> : null}
      >
        {traceLoading ? <div className="empty-state small"><span className="spinner" /> Loading trace…</div> : null}
        {selected ? <TraceView episode={selected} /> : null}
      </Drawer>
    </div>
  );
}

export function TraceView({ episode }: { episode: Episode }) {
  const out = episode.outcome;
  return (
    <div className="trace">
      <div className="trace-outcome">
        <div className={out.leak.detected ? "trace-pill bad" : "trace-pill good"}>
          <span>Leak</span><strong>{out.leak.detected ? "detected" : "not detected"}</strong>
        </div>
        <div className={out.utility_ok ? "trace-pill good" : "trace-pill warn"}>
          <span>Utility</span><strong>{out.utility_ok ? "task completed" : "failed"}</strong>
        </div>
        <div className={out.unauthorized_action.detected ? "trace-pill bad" : "trace-pill good"}>
          <span>Unauthorized</span><strong>{out.unauthorized_action.detected ? out.unauthorized_action.tool ?? "yes" : "no"}</strong>
        </div>
        <div className="trace-pill">
          <span>Blocked / tokens</span><strong>{out.blocked_count} / {num(episode.tokens)}</strong>
        </div>
      </div>

      <div className="trace-grid">
        <div className="trace-block">
          <h3>Task</h3>
          <p>{episode.task_text}</p>
          <div className="trace-meta"><span>Utility check</span><b>{out.utility_detail || "—"}</b></div>
          <div className="trace-meta"><span>Enforcement</span><b>{episode.enforcement}</b></div>
          <div className="trace-meta"><span>Synthetic fixture</span><b>{String(episode.synthetic_fixture)}</b></div>
        </div>
        <div className="trace-block">
          <h3>Attack</h3>
          {episode.attack ? (
            <>
              <div className="trace-meta"><span>Vector</span><b>{episode.attack.vector}</b></div>
              <div className="trace-meta"><span>Goal</span><b>{episode.attack.goal}</b></div>
              <div className="trace-meta"><span>Template</span><b className="mono">{episode.attack.template_id}</b></div>
              <div className="trace-meta"><span>Split / round</span><b>{episode.attack.split} / {episode.attack.adaptive_round}</b></div>
              <div className="trace-meta"><span>Category</span><b>{episode.attack.target_category}</b></div>
            </>
          ) : <p className="muted">Benign episode, no injection.</p>}
        </div>
      </div>

      {out.leak.detected ? (
        <div className="alert-box bad">
          <strong>Canaries detected in egress</strong>
          <div className="canary-list">{out.leak.canary_ids.map((id) => <code key={id}>{id}</code>)}</div>
          <div className="cell-sub">via {out.leak.via_tool ?? "tool"} {out.leak.via_host ? `to ${out.leak.via_host}` : ""} · step {out.leak.step ?? "?"}</div>
        </div>
      ) : null}

      <h3 className="trace-title">Timeline</h3>
      <ol className="timeline">
        {episode.steps.map((step) => (
          <li key={step.t} className={`timeline-step role-${step.role}`}>
            <div className="timeline-dot" />
            <div className="timeline-card">
              <div className="timeline-head">
                <span className="step-t">t{step.t}</span>
                <Badge tone={step.provenance?.trusted === false ? "bad" : "neutral"}>{step.role}</Badge>
                {step.provenance?.source ? <span className="cell-sub">{step.provenance.source}</span> : null}
              </div>
              {step.tool_call ? (
                <div className="tc">
                  <div className="tc-name mono">{step.tool_call.name}</div>
                  <pre className="code">{JSON.stringify(step.tool_call.args, null, 2)}</pre>
                  {step.gateway ? (
                    <div className={`gateway gateway-${step.gateway.decision}`}>
                      <Badge tone={step.gateway.decision === "block" ? "bad" : step.gateway.decision === "ask" ? "warn" : "good"}>{step.gateway.decision}</Badge>
                      <code>{step.gateway.rule_id}</code>
                      <span>{compact(step.gateway.reason, 160)}</span>
                    </div>
                  ) : null}
                  {step.tool_result ? (
                    <details className="tool-result">
                      <summary>Tool result</summary>
                      <pre className="code">{compact(step.tool_result, 1600)}</pre>
                    </details>
                  ) : null}
                </div>
              ) : (
                <div className="assistant-text">{compact(step.content, 900)}</div>
              )}
            </div>
          </li>
        ))}
      </ol>
    </div>
  );
}
