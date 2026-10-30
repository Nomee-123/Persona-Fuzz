import { NavLink, Outlet } from "react-router-dom";
import { useData } from "../data";
import { Badge } from "./Badge";
import { Icon } from "./Icon";
import { RunButton } from "./RunButton";

const NAV = [
  { to: "/", label: "Overview", icon: "overview", end: true },
  { to: "/run", label: "Run detail", icon: "run" },
  { to: "/attacks", label: "Attack explorer", icon: "attack" },
  { to: "/policy", label: "Learned policy", icon: "policy" },
  { to: "/report", label: "Report", icon: "report" },
];

export function Layout() {
  const { summary, runs, runId, selectRun, loading } = useData();

  return (
    <div className="app-shell">
      <aside className="sidebar">
        <div className="brand">
          <div className="brand-mark">PF</div>
          <div>
            <div className="brand-name">Persona-Fuzz</div>
            <div className="brand-sub">Agent red-team lab</div>
          </div>
        </div>
        <nav className="nav" aria-label="Main">
          {NAV.map((item) => (
            <NavLink key={item.to} to={item.to} end={item.end} className={({ isActive }) => `nav-item ${isActive ? "active" : ""}`}>
              <Icon name={item.icon} />
              <span>{item.label}</span>
            </NavLink>
          ))}
        </nav>
        <div className="sidebar-foot">
          <div className="mini-label">Dataset</div>
          <div className="sidebar-dataset">{summary?.config.dataset ?? "Nemotron-Personas-India"}</div>
          <div className="sidebar-rule" />
          <div className="mini-label">Detection</div>
          <div className="sidebar-note">Deterministic canary + tool predicates. No LLM judge.</div>
        </div>
      </aside>

      <div className="main">
        <header className="topbar">
          <div className="topbar-left">
            <div className="mobile-brand">PF</div>
            <div>
              <div className="eyebrow">Pre-deployment evaluation</div>
              <h1>{summary ? `Run ${summary.run_id}` : "Persona-Fuzz"}</h1>
            </div>
          </div>
          <div className="topbar-right">
            {summary?.synthetic_fixture ? <Badge tone="warn" title="Synthetic fixture data">Sample data</Badge> : null}
            {summary ? <Badge tone={summary.config.enforcement === "openshell" ? "accent" : "neutral"}>{summary.config.enforcement === "openshell" ? "OpenShell enforcement" : "Gateway enforcement"}</Badge> : null}
            <label className="run-select">
              <span className="sr-only">Select run</span>
              <select
                value={runId ?? ""}
                onChange={(event) => void selectRun(event.target.value)}
                disabled={loading || runs.length === 0}
              >
                {runs.map((run) => (
                  <option key={run.run_id} value={run.run_id}>
                    {run.run_id}{run.synthetic_fixture ? " · sample" : ""}
                  </option>
                ))}
              </select>
            </label>
            <RunButton />
          </div>
        </header>

        {summary?.synthetic_fixture ? (
          <div className="sample-banner" role="status">
            <strong>Sample data.</strong> This run uses a deterministic offline mock and fallback personas. Every number below is computed from the run files, but it is not a live-model result.
          </div>
        ) : null}
        {summary?.metrics.attack_potency_low ? (
          <div className="sample-banner warn" role="status">
            <strong>Low attack potency.</strong> D0 targeted success was under 10% on this sample, so the hardening comparison is not informative.
          </div>
        ) : null}

        <main className="content">
          <Outlet />
        </main>
        <footer className="footer">
          <span>Persona-Fuzz · deterministic detection · held-out is the headline</span>
          <span>{summary ? `${summary.config.model} · ${summary.config.region}` : ""}</span>
        </footer>
      </div>
    </div>
  );
}
