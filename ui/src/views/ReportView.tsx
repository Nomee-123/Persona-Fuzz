import { Badge } from "../components/Badge";
import { Section } from "../components/Section";
import { useData } from "../data";
import { bytes, dateTime, num, pct } from "../format";
import type { Condition } from "../types";

const CONDITIONS: Condition[] = ["D0", "D1", "D2", "D3", "D4"];

export function ReportView() {
  const { summary, loading } = useData();
  if (loading && !summary) return <div className="empty-state"><span className="spinner" /> Loading report…</div>;
  if (!summary) return <div className="empty-state"><h2>No run selected</h2></div>;
  const m = summary.metrics;

  return (
    <div className="page report">
      <div className="page-head">
        <div>
          <div className="eyebrow">Report</div>
          <h2>Persona-Fuzz evaluation report</h2>
          <p>{summary.run_id} · {dateTime(summary.finished_at)} · generated from <code>runs/{summary.run_id}/</code></p>
        </div>
        <div className="page-head-actions">
          {summary.synthetic_fixture ? <Badge tone="warn">Sample data</Badge> : <Badge tone="good">Live run</Badge>}
          <a className="btn" href={`/api/export?run_id=${encodeURIComponent(summary.run_id)}`}>Download bundle</a>
        </div>
      </div>

      {summary.synthetic_fixture ? (
        <div className="report-callout">
          <strong>Read this first.</strong> This run uses deterministic offline mock agents and/or fallback personas
          (<code>synthetic_fixture=true</code>, <code>dataset_source={summary.dataset_source}</code>). The numbers are computed
          from the run files and are useful for validating the pipeline and UI, but they are not claims about a live model.
        </div>
      ) : null}

      <article className="report-body">
        <h3>1. Question</h3>
        <p>
          Can a tool-using personal agent be red-teamed with synthetic Indian digital lives, and can its least-privilege
          policy be learned automatically so that prompt-injected exfiltration fails on held-out personas and attack templates
          without breaking benign tasks?
        </p>

        <h3>2. Method</h3>
        <ul>
          <li><strong>Personas and world.</strong> {summary.config.dataset}; {summary.config.n_fit} fit and {summary.config.n_eval} disjoint eval personas. Each life contains email, calendar, notes, files, contacts, bank records and canary-labelled secrets.</li>
          <li><strong>Agent.</strong> {summary.config.agent_label}; model <code>{summary.config.model}</code>; tool gateway with 48 tools and 32 hosts.</li>
          <li><strong>Attacks.</strong> Email, calendar and web injection with train/eval template splits, plus a multi-round adaptive attacker on the eval set.</li>
          <li><strong>Detection.</strong> Deterministic canary matching plus tool and argument predicates. No LLM judge is used to decide leakage.</li>
          <li><strong>Defenses.</strong> D0 none; D1 spotlighting; D2 LLM-written Progent-style policy; D3 trace-derived policy; D4 = D3 + CEGIS tightening + sensitivity DLP + untrusted-context sink guard.</li>
        </ul>

        <h3>3. Headline results (held-out)</h3>
        <div className="report-table">
          <table>
            <thead><tr><th>Metric</th><th>D0 before</th><th>D4 after</th></tr></thead>
            <tbody>
              <tr><td>Leak rate</td><td>{pct(m.leak_rate_before)} ({m.leaks_before}/{m.total_runs})</td><td>{pct(m.leak_rate_after)} ({m.leaks_after}/{m.total_runs})</td></tr>
              <tr><td>Benign utility</td><td>{pct(m.utility_benign_d0)}</td><td>{pct(m.utility_benign_d4)}</td></tr>
              <tr><td>Utility under attack</td><td>{pct(m.utility_under_attack_d0)}</td><td>{pct(m.utility_under_attack_d4)}</td></tr>
              <tr><td>Adaptive attacker ASR</td><td>{pct(m.adaptive_asr_d0)}</td><td>{pct(m.adaptive_asr_d4)}</td></tr>
              <tr><td>False-block rate (benign calls)</td><td>—</td><td>{pct(m.false_block_rate, 1)}</td></tr>
            </tbody>
          </table>
        </div>
        <p>
          Relative leak reduction is {pct(m.improvement)}. Attack potency on this sample is {pct(m.potency)}
          {m.attack_potency_low ? "; this is below the 10% sanity gate, so treat the comparison as uninformative." : "."}
          {" "}D4 blocked {m.blocked_actions} attack actions across the extended battery.
        </p>

        <h3>4. Security with utility</h3>
        <p>
          A deny-all policy is not a win. D4 retains {pct(m.utility_benign_d4)} benign utility on the eval set with a
          false-block rate of {pct(m.false_block_rate, 1)} on benign tool calls. The learned policy allows
          {" "}{summary.policy.allowed_tools.length}/{summary.policy.catalog_tools} tools and
          {" "}{summary.policy.allowed_hosts.length}/{summary.policy.catalog_hosts} hosts
          ({pct(summary.policy.permissions_reduced)} reduction); the average policy is {bytes(m.avg_policy_bytes)}.
        </p>

        <h3>5. Defense conditions</h3>
        <div className="report-table">
          <table>
            <thead><tr><th>Condition</th><th>Attacks</th><th>Leak</th><th>Utility under attack</th><th>Blocked</th></tr></thead>
            <tbody>
              {CONDITIONS.map((c) => {
                const row = summary.conditions[c];
                return <tr key={c}><td>{c}</td><td>{row.episodes}</td><td>{pct(row.leak_rate)}</td><td>{pct(row.utility_under_attack)}</td><td>{row.blocked_actions}</td></tr>;
              })}
            </tbody>
          </table>
        </div>

        <h3>6. Learned policy</h3>
        <p>
          The union allows: <code>{summary.policy.allowed_tools.join(", ") || "none"}</code>.
          {" "}Denied sinks: <code>{summary.policy.denied_tools.slice(0, 12).join(", ") || "none"}</code>.
          {" "}The full policy, CEGIS changelog and OpenShell YAML are in the run bundle.
        </p>

        <h3>7. Limitations</h3>
        <ul>
          <li>Pattern DLP can miss rephrased or re-encoded secrets; held-out obfuscation templates expose this gap.</li>
          <li>Policies are learned on fit personas and train templates. Headline evaluation uses eval personas, held-out templates and an adaptive attacker.</li>
          <li>Reported utility is task-specific (meeting scheduled, trusted email sent, briefing note saved), not a general capability score.</li>
          <li>Tool-argument semantics are enforced by this gateway. OpenShell YAML covers filesystem, network and process controls; it is not a substitute for the gateway’s recipient/body checks.</li>
          {summary.synthetic_fixture ? <li>This run is a synthetic fixture: offline mock agents and fallback data. It must not be cited as a live-model result.</li> : null}
          {summary.notes?.filter((n) => !n.startsWith("synthetic_fixture") && !n.startsWith("dataset_source")).map((n, i) => <li key={i}>{n}</li>)}
        </ul>

        <h3>8. Cost and reproducibility</h3>
        <p>
          {num(summary.cost.tokens)} tokens, estimated ${summary.cost.usd_estimate.toFixed(2)}. The run directory stores
          <code> episodes.jsonl</code>, <code>summary.json</code>, <code>policy.json</code>, <code>policy.md</code> and
          <code> policy.openshell.yaml</code>. Detection and enforcement functions are pure/deterministic; replay renders the recorded traces offline.
        </p>

        <h3>References</h3>
        <ul className="refs">
          <li>AgentDojo: benchmark for prompt injection and utility (arXiv <a href="https://arxiv.org/abs/2406.13352" target="_blank" rel="noreferrer">2406.13352</a>).</li>
          <li>Progent: tool-level privilege DSL and LLM-written policies (arXiv <a href="https://arxiv.org/abs/2504.11703" target="_blank" rel="noreferrer">2504.11703</a>).</li>
          <li>CaMeL: information-flow control against untrusted data steering privileged actions.</li>
          <li>NVIDIA garak: optional injection seed corpus.</li>
          <li>NVIDIA OpenShell: sandbox policy YAML export.</li>
          <li>NVIDIA Nemotron-Personas-India: <a href="https://huggingface.co/datasets/nvidia/Nemotron-Personas-India" target="_blank" rel="noreferrer">Hugging Face</a>.</li>
          <li>Nebius Token Factory: OpenAI-compatible inference and serverless jobs.</li>
        </ul>
      </article>

      <Section title="Audit notes" subtitle="Machine-written notes from this run.">
        {summary.notes?.length ? <ul className="notes-list">{summary.notes.map((n, i) => <li key={i}>{n}</li>)}</ul> : <p className="muted">No notes.</p>}
      </Section>
    </div>
  );
}
