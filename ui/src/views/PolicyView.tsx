import { useEffect, useMemo, useState } from "react";
import { fetchPolicy, openshellUrl } from "../api";
import { Badge } from "../components/Badge";
import { Icon } from "../components/Icon";
import { Meter } from "../components/Meter";
import { Section } from "../components/Section";
import { useData } from "../data";
import { bytes, pct } from "../format";
import type { PolicyBundle, PolicyJson } from "../types";

export function PolicyView() {
  const { summary, loading } = useData();
  const [bundle, setBundle] = useState<PolicyBundle | null>(null);
  const [tab, setTab] = useState("union");
  const [copied, setCopied] = useState(false);

  useEffect(() => {
    if (!summary) return;
    fetchPolicy(summary.run_id)
      .then(setBundle)
      .catch(() => setBundle(null));
  }, [summary]);

  const policy: PolicyJson | null = useMemo(() => {
    if (!bundle) return summary?.policy.json ?? null;
    if (tab === "union") return bundle.union;
    return bundle.by_task_class[tab] ?? bundle.union;
  }, [bundle, tab, summary]);

  if (loading && !summary) return <div className="empty-state"><span className="spinner" /> Loading policy…</div>;
  if (!summary || !policy) return <div className="empty-state"><h2>No policy recorded</h2></div>;

  const yaml = summary.policy.openshell_yaml;
  const tasks = bundle ? Object.keys(bundle.by_task_class) : [];

  const copyYaml = async () => {
    try {
      await navigator.clipboard.writeText(yaml);
      setCopied(true);
      window.setTimeout(() => setCopied(false), 1500);
    } catch {
      setCopied(false);
    }
  };

  return (
    <div className="page">
      <div className="page-head">
        <div>
          <div className="eyebrow">Learned policy</div>
          <h2>Least privilege, derived from traces and counterexamples</h2>
          <p>D3 mines fit traces; D4 adds flow guards and sensitivity DLP, then tightens on failing counterexamples without losing benign utility.</p>
        </div>
        <div className="page-head-actions">
          <a className="btn" href={openshellUrl(summary.run_id)} target="_blank" rel="noreferrer"><Icon name="download" /> OpenShell YAML</a>
        </div>
      </div>

      <div className="stat-grid">
        <div className="stat">
          <div className="stat-label">Permissions reduced</div>
          <div className="stat-value">{pct(summary.policy.permissions_reduced)}</div>
          <Meter value={summary.policy.permissions_reduced} />
          <div className="stat-detail">{summary.policy.allowed_tools.length} of {summary.policy.catalog_tools} tools</div>
        </div>
        <div className="stat"><div className="stat-label">Allowed hosts</div><div className="stat-value">{summary.policy.allowed_hosts.length}<span className="stat-of">/{summary.policy.catalog_hosts}</span></div><div className="stat-detail">exact host allowlist</div></div>
        <div className="stat"><div className="stat-label">Denied tools</div><div className="stat-value">{summary.policy.denied_tools.length}</div><div className="stat-detail">explicitly blocked sinks</div></div>
        <div className="stat"><div className="stat-label">Policy size</div><div className="stat-value">{bytes(summary.metrics.avg_policy_bytes)}</div><div className="stat-detail">average per task class</div></div>
      </div>

      <Section
        title="Policy bundle"
        subtitle="Read the union or per-task-class policy. Learned rules are deterministic; no LLM judge at enforcement time."
        actions={
          <div className="tabs">
            <button type="button" className={tab === "union" ? "active" : ""} onClick={() => setTab("union")}>Union</button>
            {tasks.map((t) => <button key={t} type="button" className={tab === t ? "active" : ""} onClick={() => setTab(t)}>{t}</button>)}
          </div>
        }
      >
        <div className="grid-2 policy-grid">
          <div>
            <h3 className="sub-head">Allowed tools <Badge tone="good">{policy.allowed_tools.length}</Badge></h3>
            <div className="chips">{policy.allowed_tools.map((tool) => <code key={tool} className="chip good">{tool}</code>)}{!policy.allowed_tools.length ? <span className="muted">None</span> : null}</div>
            <h3 className="sub-head">Denied tools <Badge tone="bad">{policy.denied_tools.length}</Badge></h3>
            <div className="chips">{policy.denied_tools.map((tool) => <code key={tool} className="chip bad">{tool}</code>)}{!policy.denied_tools.length ? <span className="muted">None</span> : null}</div>
            <h3 className="sub-head">Allowed hosts <Badge tone="neutral">{policy.allowed_hosts.length}</Badge></h3>
            <div className="chips">{policy.allowed_hosts.map((host) => <code key={host} className="chip">{host}</code>)}{!policy.allowed_hosts.length ? <span className="muted">None</span> : null}</div>
          </div>
          <div>
            <h3 className="sub-head">Argument rules</h3>
            {Object.keys(policy.arg_rules ?? {}).length ? (
              <div className="rule-list">
                {Object.entries(policy.arg_rules ?? {}).map(([tool, fields]) => (
                  <div key={tool} className="rule">
                    <code className="rule-tool">{tool}</code>
                    {Object.entries(fields).map(([field, pred]) => (
                      <div key={field} className="rule-pred"><span>{field}</span><code>{JSON.stringify(pred)}</code></div>
                    ))}
                  </div>
                ))}
              </div>
            ) : <p className="muted">No argument predicates.</p>}
            <h3 className="sub-head">Flow rules</h3>
            {policy.flow_rules?.length ? (
              <div className="rule-list">
                {policy.flow_rules.map((rule) => (
                  <div key={rule.id} className="rule">
                    <div className="rule-title"><code>{rule.id}</code><Badge tone="accent">{rule.when}</Badge></div>
                    <div className="rule-pred"><span>sinks</span><code>{rule.sinks.join(", ")}</code></div>
                    <div className="rule-pred"><span>require</span><code>{JSON.stringify(rule.require)}</code></div>
                  </div>
                ))}
              </div>
            ) : <p className="muted">No flow rules.</p>}
          </div>
        </div>
      </Section>

      <div className="grid-2">
        <Section title="CEGIS changelog" subtitle="Each accepted tightening is recorded with its counterexample reason.">
          {bundle?.changelog.length ? (
            <ol className="changelog">
              {bundle.changelog.map((row, i) => (
                <li key={`${row.iteration}-${i}`}>
                  <div className="changelog-head"><Badge tone="accent">iter {row.iteration}</Badge><code>{row.tool}</code><Badge tone={row.action === "deny" ? "bad" : "warn"}>{row.action}</Badge></div>
                  <p>{row.detail}</p>
                  <div className="cell-sub">{row.task_class} · {row.reason}</div>
                </li>
              ))}
            </ol>
          ) : <p className="muted">No tightenings were needed on the fit set. This is recorded honestly, not hidden.</p>}
          {bundle?.rejected.length ? (
            <>
              <h3 className="sub-head">Rejected</h3>
              <ul className="notes-list">{bundle.rejected.map((r, i) => <li key={i}>{r}</li>)}</ul>
            </>
          ) : null}
        </Section>

        <Section
          title="OpenShell sandbox"
          subtitle="Exported YAML. The gateway enforces tool-argument semantics; this file maps allowed hosts."
          actions={
            <div className="page-head-actions">
              <button type="button" className="btn small" onClick={() => void copyYaml()}><Icon name="copy" /> {copied ? "Copied" : "Copy"}</button>
              <a className="btn small" href={openshellUrl(summary.run_id)} download="policy.openshell.yaml"><Icon name="download" /> .yaml</a>
            </div>
          }
        >
          <pre className="code yaml">{yaml}</pre>
        </Section>
      </div>
    </div>
  );
}
