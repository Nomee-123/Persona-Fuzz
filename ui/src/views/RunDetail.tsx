import { useState } from "react";
import { fetchEpisode } from "../api";
import { Badge } from "../components/Badge";
import { Drawer } from "../components/Drawer";
import { LineChart } from "../components/LineChart";
import { Meter } from "../components/Meter";
import { Section } from "../components/Section";
import { useData } from "../data";
import { bytes, dateTime, num, pct } from "../format";
import type { Condition, Episode } from "../types";
import { TraceView } from "./AttackExplorer";

const CONDITIONS: Condition[] = ["D0", "D1", "D2", "D3", "D4"];

export function RunDetail() {
  const { summary, loading } = useData();
  const [episode, setEpisode] = useState<Episode | null>(null);
  const [traceError, setTraceError] = useState("");

  if (loading && !summary) return <div className="empty-state"><span className="spinner" /> Loading run…</div>;
  if (!summary) return <div className="empty-state"><h2>No run selected</h2></div>;

  const m = summary.metrics;
  const series = [
    { name: "Train leak", color: "#ff8a65", values: summary.curve.map((p) => p.train_leak) },
    { name: "Held-out leak", color: "#ffd166", values: summary.curve.map((p) => p.heldout_leak) },
    { name: "Utility", color: "#76e4b8", values: summary.curve.map((p) => p.utility) },
  ];
  const labels = summary.curve.map((p) => (p.iter === 0 ? "D0" : `D4.${p.iter}`));

  const openExample = async () => {
    setTraceError("");
    try {
      const ep = await fetchEpisode(summary.example_trace_ids.episode_id, summary.run_id);
      setEpisode(ep);
    } catch (err) {
      setTraceError(err instanceof Error ? err.message : String(err));
    }
  };

  return (
    <div className="page">
      <div className="page-head">
        <div>
          <div className="eyebrow">Run detail</div>
          <h2>{summary.run_id}</h2>
          <p>{summary.config.agent_label} · {summary.config.dataset}</p>
        </div>
        <div className="page-head-actions">
          <Badge tone={summary.status === "completed" ? "good" : "warn"}>{summary.status}</Badge>
          <button type="button" className="btn" onClick={() => void openExample()} disabled={!summary.example_trace_ids.episode_id}>
            Inspect example trace
          </button>
          <a className="btn" href={`/api/export?run_id=${encodeURIComponent(summary.run_id)}`}>Download bundle</a>
        </div>
      </div>

      <div className="stat-grid">
        <div className="stat"><div className="stat-label">Leak before → after</div><div className="stat-value">{m.leaks_before}/{m.total_runs} → {m.leaks_after}/{m.total_runs}</div><div className="stat-detail">{pct(m.leak_rate_before)} → {pct(m.leak_rate_after)}</div></div>
        <div className="stat"><div className="stat-label">Improvement</div><div className="stat-value">{pct(m.improvement)}</div><div className="stat-detail">relative reduction in headline leak rate</div></div>
        <div className="stat"><div className="stat-label">Benign utility</div><div className="stat-value">{pct(m.utility_benign_d4)}</div><div className="stat-detail">D0 {pct(m.utility_benign_d0)} · under attack {pct(m.utility_under_attack_d4)}</div></div>
        <div className="stat"><div className="stat-label">Attack potency</div><div className="stat-value">{pct(m.potency)}</div><div className="stat-detail">{m.attack_potency_low ? "below 10% alert" : "D0 targeted success on this sample"}</div></div>
      </div>

      <div className="grid-2">
        <Section title="Configuration" subtitle="Recorded in config.json and summary.json.">
          <dl className="kv wide">
            <div><dt>Dataset</dt><dd>{summary.config.dataset}</dd></div>
            <div><dt>Split</dt><dd>{summary.config.n_fit} fit / {summary.config.n_eval} eval personas</dd></div>
            <div><dt>Model</dt><dd className="mono">{summary.config.model}</dd></div>
            <div><dt>Compute</dt><dd>{summary.config.compute_label}</dd></div>
            <div><dt>Region</dt><dd>{summary.config.region}</dd></div>
            <div><dt>Enforcement</dt><dd>{summary.config.enforcement}</dd></div>
            <div><dt>Attack types</dt><dd>{summary.config.attack_types.join(", ")}</dd></div>
            <div><dt>Canary classes</dt><dd>{summary.config.canary_categories.join(", ")}</dd></div>
            <div><dt>Started</dt><dd>{dateTime(summary.started_at)}</dd></div>
            <div><dt>Finished</dt><dd>{dateTime(summary.finished_at)}</dd></div>
          </dl>
        </Section>
        <Section title="Cost and integrity" subtitle="No metric is edited by hand.">
          <dl className="kv wide">
            <div><dt>Total tokens</dt><dd>{num(summary.cost.tokens)}</dd></div>
            <div><dt>USD estimate</dt><dd>${summary.cost.usd_estimate.toFixed(2)}</dd></div>
            <div><dt>Synthetic fixture</dt><dd>{summary.synthetic_fixture ? "true" : "false"}</dd></div>
            <div><dt>Dataset source</dt><dd>{summary.dataset_source}</dd></div>
            <div><dt>Policy size</dt><dd>{bytes(m.avg_policy_bytes)}</dd></div>
            <div><dt>Paired McNemar</dt><dd>{summary.paired_mcnemar ? `p=${summary.paired_mcnemar.p_value}` : "not available"}</dd></div>
          </dl>
          {traceError ? <p className="error-line">{traceError}</p> : null}
        </Section>
      </div>

      <Section title="CEGIS curve" subtitle="Each accepted iteration must preserve benign utility within the configured epsilon.">
        {summary.curve.length ? <LineChart series={series} labels={labels} yLabel="Rate" /> : <div className="empty-plot">No curve recorded.</div>}
      </Section>

      <Section title="Condition comparison" subtitle="Extended battery. Headline cards above use the disjoint held-out headline episodes only.">
        <div className="table-wrap">
          <table>
            <thead>
              <tr><th>Condition</th><th>Attacks</th><th>Leak</th><th>Targeted ASR</th><th>Utility under attack</th><th>Benign utility</th><th>Blocked</th><th>False blocks</th></tr>
            </thead>
            <tbody>
              {CONDITIONS.map((c) => {
                const row = summary.conditions[c];
                return (
                  <tr key={c}>
                    <td><Badge tone={c === "D0" ? "bad" : c === "D4" ? "good" : "neutral"}>{c}</Badge></td>
                    <td>{row.episodes}</td>
                    <td><div className="inline-meter"><Meter value={row.leak_rate} tone={row.leak_rate > 0.1 ? "bad" : "good"} /><span>{pct(row.leak_rate)}</span></div></td>
                    <td>{pct(row.targeted_asr)}</td>
                    <td>{pct(row.utility_under_attack)}</td>
                    <td>{pct(row.utility)}</td>
                    <td>{row.blocked_actions}</td>
                    <td>{pct(row.false_block_rate, 1)}</td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      </Section>

      <Section title="Per-model comparison" subtitle="Same held-out sample per model; tokens and latency are recorded.">
        <div className="table-wrap">
          <table>
            <thead><tr><th>Model</th><th>Leak D0</th><th>Leak D4</th><th>Utility D0</th><th>Utility D4</th><th>Tokens</th><th>Latency</th></tr></thead>
            <tbody>
              {summary.per_model.map((row) => (
                <tr key={row.model}>
                  <td className="mono">{row.model}</td>
                  <td>{pct(row.leak_rate_d0)}</td>
                  <td>{pct(row.leak_rate_d4)}</td>
                  <td>{pct(row.utility_d0)}</td>
                  <td>{pct(row.utility_d4)}</td>
                  <td>{num(row.tokens)}</td>
                  <td>{row.latency_ms.toFixed(0)} ms</td>
                </tr>
              ))}
              {!summary.per_model.length ? <tr><td colSpan={7} className="empty-cell">No per-model rows.</td></tr> : null}
            </tbody>
          </table>
        </div>
      </Section>

      <Section title="Run notes" subtitle="Limitations and fallbacks recorded by the runner.">
        {summary.notes?.length ? (
          <ul className="notes-list">{summary.notes.map((note, i) => <li key={i}>{note}</li>)}</ul>
        ) : <p className="muted">No notes.</p>}
      </Section>

      <Drawer open={!!episode} onClose={() => setEpisode(null)} title={episode ? `Trace ${episode.episode_id}` : "Trace"} subtitle={episode ? <>{episode.persona_id} · {episode.condition} · {episode.task_class}</> : null}>
        {episode ? <TraceView episode={episode} /> : null}
      </Drawer>
    </div>
  );
}
