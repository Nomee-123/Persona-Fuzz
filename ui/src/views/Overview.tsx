import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { fetchEpisodes } from "../api";
import { Badge } from "../components/Badge";
import { LineChart } from "../components/LineChart";
import { Meter } from "../components/Meter";
import { Section } from "../components/Section";
import { Stat } from "../components/Stat";
import { useData } from "../data";
import { bytes, compact, dateTime, num, pct } from "../format";
import type { Condition, EpisodeRow } from "../types";

const CONDITIONS: Condition[] = ["D0", "D1", "D2", "D3", "D4"];

export function Overview() {
  const { summary, loading, error, runId } = useData();
  const [recent, setRecent] = useState<EpisodeRow[]>([]);

  useEffect(() => {
    if (!summary) return;
    fetchEpisodes({ runId: summary.run_id, attack: "true", limit: 6 })
      .then((res) => setRecent(res.episodes))
      .catch(() => setRecent([]));
  }, [summary, runId]);

  if (loading && !summary) {
    return <div className="empty-state"><span className="spinner" /> Loading the latest run…</div>;
  }
  if (error && !summary) {
    return (
      <div className="empty-state">
        <h2>No run available</h2>
        <p>{error}</p>
        <p>Start the API with <code>python -m engine.cli serve</code>, then use “Run quick smoke”.</p>
      </div>
    );
  }
  if (!summary) return null;

  const m = summary.metrics;
  const policy = summary.policy;
  const chartSeries = [
    { name: "Train leak", color: "#ff8a65", values: summary.curve.map((p) => p.train_leak) },
    { name: "Held-out leak", color: "#ffd166", values: summary.curve.map((p) => p.heldout_leak) },
    { name: "Benign utility", color: "#76e4b8", values: summary.curve.map((p) => p.utility) },
  ];
  const chartLabels = summary.curve.map((p) => (p.iter === 0 ? "D0" : `D4.${p.iter}`));

  return (
    <div className="page">
      <section className="hero">
        <div>
          <div className="hero-kicker">AgentDojo-style security × utility</div>
          <h2>Break the personal agent, then learn its least-privilege policy.</h2>
          <p>
            Synthetic Indian lives from {summary.config.dataset}. A tool-using assistant is attacked through email, calendar and web.
            Canary and tool predicates decide leakage; CEGIS tightens a trace-derived policy until attacks fail without breaking benign work.
          </p>
          <div className="hero-tags">
            <Badge tone="accent">{summary.config.n_eval} eval personas</Badge>
            <Badge>{summary.config.n_fit} fit personas</Badge>
            <Badge>{summary.config.attack_types.join(" · ")}</Badge>
            <Badge tone={summary.dataset_source === "nemotron_personas_india" ? "good" : "warn"}>
              {summary.dataset_source === "nemotron_personas_india" ? "Nemotron-Personas-India" : "Fallback personas"}
            </Badge>
          </div>
        </div>
        <div className="hero-meta">
          <div><span>Compute</span><strong>{summary.config.compute_label}</strong></div>
          <div><span>Model</span><strong>{summary.config.model}</strong></div>
          <div><span>Finished</span><strong>{dateTime(summary.finished_at)}</strong></div>
          <div><span>Cost</span><strong>${summary.cost.usd_estimate.toFixed(2)} · {num(summary.cost.tokens)} tok</strong></div>
        </div>
      </section>

      <div className="stat-grid">
        <Stat
          label="Headline leak rate"
          value={<span>{pct(m.leak_rate_before)} <span className="arrow-inline">→</span> {pct(m.leak_rate_after)}</span>}
          detail={`${m.leaks_before}/${m.total_runs} → ${m.leaks_after}/${m.total_runs} held-out attacks`}
          tone={m.leak_rate_after === 0 && m.leak_rate_before > 0.1 ? "good" : "warn"}
        />
        <Stat
          label="Benign task utility"
          value={<span>{pct(m.utility_benign_d0)} <span className="arrow-inline">→</span> {pct(m.utility_benign_d4)}</span>}
          detail={`D0 → D4 · utility under attack ${pct(m.utility_under_attack_d4)}`}
          tone={m.utility_benign_d4 >= 0.95 ? "good" : "warn"}
        />
        <Stat
          label="Adaptive attacker ASR"
          value={<span>{pct(m.adaptive_asr_d0)} <span className="arrow-inline">→</span> {pct(m.adaptive_asr_d4)}</span>}
          detail="Multi-round rewrites, same eval personas"
          tone={m.adaptive_asr_d4 <= m.adaptive_asr_d0 ? "good" : "bad"}
        />
        <Stat
          label="Least privilege"
          value={pct(policy.permissions_reduced)}
          detail={`${policy.allowed_tools.length}/${policy.catalog_tools} tools · ${policy.allowed_hosts.length}/${policy.catalog_hosts} hosts`}
          tone="default"
        >
          <Meter value={policy.permissions_reduced} />
        </Stat>
      </div>

      <div className="grid-2">
        <Section
          title="CEGIS convergence"
          subtitle="Iteration 0 is no defense (D0). Tightenings are accepted only if benign utility holds."
          actions={<Badge tone="good">{summary.curve.length > 1 ? "Converged" : "Baseline"}</Badge>}
        >
          {summary.curve.length ? (
            <LineChart series={chartSeries} labels={chartLabels} yLabel="Rate" />
          ) : (
            <div className="empty-plot">No curve recorded.</div>
          )}
        </Section>

        <Section title="Policy minimization" subtitle="What the agent is still allowed to do.">
          <div className="big-number">{pct(policy.permissions_reduced)}</div>
          <div className="sub-number">reduction from the full {policy.catalog_tools}-tool / {policy.catalog_hosts}-host catalog</div>
          <dl className="kv">
            <div><dt>Allowed tools</dt><dd>{policy.allowed_tools.length}</dd></div>
            <div><dt>Denied tools</dt><dd>{policy.denied_tools.length}</dd></div>
            <div><dt>Allowed hosts</dt><dd>{policy.allowed_hosts.length}</dd></div>
            <div><dt>Policy size</dt><dd>{bytes(m.avg_policy_bytes)}</dd></div>
            <div><dt>Blocked actions</dt><dd>{m.blocked_actions}</dd></div>
            <div><dt>False-block rate</dt><dd>{pct(m.false_block_rate, 1)}</dd></div>
          </dl>
          <Link className="text-link" to="/policy">Inspect the learned policy <span aria-hidden="true">→</span></Link>
        </Section>
      </div>

      <Section title="Defense conditions" subtitle="Every condition runs the same held-out attack suite; utility is reported alongside security.">
        <div className="condition-grid">
          {CONDITIONS.map((condition, i) => {
            const c = summary.conditions[condition];
            const active = condition === "D0" || condition === "D4";
            return (
              <div key={condition} className={`condition-card ${active ? "condition-active" : ""}`}>
                <div className="condition-head">
                  <strong>{condition}</strong>
                  <span>{conditionLabel(condition)}</span>
                </div>
                <div className="condition-metric">
                  <span>Leak</span><b>{pct(c.leak_rate)}</b>
                </div>
                <Meter value={c.leak_rate} tone={c.leak_rate > 0.1 ? "bad" : "good"} />
                <div className="condition-metric">
                  <span>Utility</span><b>{pct(c.utility)}</b>
                </div>
                <Meter value={c.utility} tone="good" />
                <div className="condition-foot">{c.episodes} attacks · {c.blocked_actions} blocked</div>
                {i === 0 ? <div className="condition-flag">Before</div> : null}
                {condition === "D4" ? <div className="condition-flag after">After</div> : null}
              </div>
            );
          })}
        </div>
      </Section>

      <div className="grid-2">
        <Section
          title="Recent attack episodes"
          subtitle="Click through to the Attack explorer for full traces."
          actions={<Link className="text-link" to="/attacks">Open explorer <span aria-hidden="true">→</span></Link>}
        >
          <div className="table-wrap">
            <table>
              <thead><tr><th>Persona</th><th>Vector</th><th>Condition</th><th>Leak</th><th>Utility</th></tr></thead>
              <tbody>
                {recent.map((e) => (
                  <tr key={e.episode_id}>
                    <td className="mono">{e.persona_id}</td>
                    <td>{e.attack?.vector ?? "—"}<div className="cell-sub">{e.attack ? compact(e.attack.goal, 26) : ""}</div></td>
                    <td><Badge tone={e.condition === "D0" ? "bad" : "good"}>{e.condition}</Badge></td>
                    <td>{e.outcome.leak.detected ? <Badge tone="bad">leaked</Badge> : <Badge tone="good">blocked</Badge>}</td>
                    <td>{e.outcome.utility_ok ? "ok" : <Badge tone="warn">failed</Badge>}</td>
                  </tr>
                ))}
                {!recent.length ? <tr><td colSpan={5} className="empty-cell">No attack episodes in this run.</td></tr> : null}
              </tbody>
            </table>
          </div>
        </Section>

        <Section title="Honesty ledger" subtitle="The run summary is the only source of truth.">
          <ul className="ledger">
            <li><Badge tone={summary.synthetic_fixture ? "warn" : "good"}>{summary.synthetic_fixture ? "Synthetic fixture" : "Live run"}</Badge> {summary.synthetic_fixture ? "Deterministic mock and/or fixture data; not a live-model claim." : "Live Token Factory calls are recorded in the run directory."}</li>
            <li><Badge tone={summary.dataset_source === "nemotron_personas_india" ? "good" : "warn"}>{summary.dataset_source === "nemotron_personas_india" ? "Nemotron personas" : "Fallback personas"}</Badge> Dataset source is recorded in config and summary.</li>
            <li><Badge tone="good">Deterministic</Badge> Leak detection is canary matching plus tool/argument predicates.</li>
            <li><Badge tone={m.utility_benign_d4 >= 0.95 ? "good" : "bad"}>Utility {pct(m.utility_benign_d4)}</Badge> Security is never reported without benign utility.</li>
            <li><Badge tone="neutral">Held-out</Badge> Headline uses eval personas and held-out attack templates.</li>
          </ul>
          {summary.notes?.length ? (
            <details className="notes">
              <summary>Run notes ({summary.notes.length})</summary>
              <ul>{summary.notes.map((note, i) => <li key={i}>{note}</li>)}</ul>
            </details>
          ) : null}
        </Section>
      </div>
    </div>
  );
}

function conditionLabel(condition: Condition): string {
  switch (condition) {
    case "D0": return "No defense";
    case "D1": return "Spotlighting";
    case "D2": return "LLM policy";
    case "D3": return "Trace policy";
    case "D4": return "CEGIS + DLP";
  }
}
