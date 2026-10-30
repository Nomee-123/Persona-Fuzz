# AGENTS.md — Persona-Fuzz build contract

Persona-Fuzz is pre-deployment red-teaming and auto-hardening for personal AI agents.
It generates synthetic Indian digital lives from NVIDIA Nemotron-Personas, attacks a
tool-using personal agent served by Nebius Token Factory, detects leakage with
deterministic canary/tool predicates, and learns a least-privilege policy (D3 + CEGIS = D4).

## Non-negotiable honesty rules

1. Never hardcode, fake or tune a metric. Every number in UI/README/REPORT is computed
   from `runs/<run_id>/`. Mockup numbers (34%, 3%, 12/48, 7/32, 78%, 1.8 KB, 91%) are
   layout placeholders only.
2. Detection is deterministic: canary matching + tool/argument predicates. No LLM judge.
3. Security is always reported with utility (AgentDojo-style); a deny-all policy is not a win.
4. Policies are learned on fit personas + train attacks. Headline results use disjoint eval
   personas + held-out templates + adaptive attacker. Held-out is the headline.
5. UI labels reflect real configuration: OpenShell only when enforcement=openshell;
   "Sample data" badge whenever `synthetic_fixture` is true.
6. Report bad results and limitations honestly.

## Research anchors (README cites)

- AgentDojo (arXiv 2406.13352): benign utility, utility under attack, targeted ASR,
  state-based checks, workspace suite.
- Progent (arXiv 2504.11703): tool-level privilege DSL, deterministic runtime enforcement,
  LLM-written policy baseline (D2).
- CaMeL / information-flow: untrusted data must not steer privileged actions.
- NVIDIA garak: optional injection seed corpus.
- NVIDIA OpenShell: sandbox policy YAML export (filesystem/network/process; our gateway
  enforces tool-argument semantics).
- NVIDIA Nemotron-Personas-India (HF `nvidia/Nemotron-Personas-India`, config `en_IN`).
- Nebius Token Factory (OpenAI-compatible) + Nebius Serverless AI Jobs.

## Defense conditions

D0 none; D1 prompt spotlighting; D2 LLM-written policy (Progent-style); D3 trace-derived
policy; D4 Persona-Fuzz = D3 + counterexample-guided tightening (CEGIS) + sensitivity-labelled
sink DLP + untrusted-context sink guard. Headline Before=D0, After=D4.

## Repo layout

`engine/` (config, llm, world, agent, attacks, detect, defense, runner, metrics, api, cli),
`contracts/` (JSON schemas), `fixtures/` (flagged synthetic UI data), `tests/`, `ui/`
(Vite + React + TS), `docker/`, `demo/`, `scripts/`, `runs/` (git-ignored), `results/`.

## Phases and gates

P0 scaffold + contracts + fixtures: tests green, schemas validate fixtures.
P1 LLM client + discovery: `doctor` prints connectivity/model/tool mode.
P2 personas + world + 48 tools + 32 hosts: deterministic lives, canary scan complete.
P3 agent + traces: mock and live complete benign task, trace schema validates.
P4 attacks + detection: D0 potency >= 10% on sample, deterministic detectors.
P5 defenses D1-D4 + OpenShell: property tests green, mock D4 leak 0% utility >= 95%.
P6 executors + metrics + API: smoke summary valid, API serves it.
P7 UI: visual checklist at 1536x1024, 1280x800, 390x844; works fixtures + real run.
P8 full eval + docs + demo: REPORT.md, replay offline, README, license, Devpost text.

Cut order: adaptive rounds, garak adapter, D1/D2 breadth, OpenShell live enforcement,
per-model breadth, shard count (min 2). Never cut: live Token Factory runs when a key is
present, deterministic detection, held-out evaluation, dashboard, README/license/demo.

## Working agreement

- Do not ask the user questions. If blocked choose the documented fallback, record it in
  DECISIONS.md and continue.
- After each phase: run tests + gate, commit `P<n>: <summary>`, update PROGRESS.md.
- No placeholders/TODOs in committed live paths. Mocks only in tests/fixtures, flagged.
- Secrets from env only; never print keys; redact Authorization. `.env` git-ignored.
- External CLI/API details must be discovered with `--help`/live response first.
- Enforcement and detection functions are pure/deterministic (no LLM, no I/O).
- `make test`, `make dev` (API :8000 + UI :5173), `make build && make serve`; if `make`
  is unavailable use the equivalent documented Python/npm commands.
- Performance: smoke < 10 min; full eval < 90 min on Nebius shards.
