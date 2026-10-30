# Persona-Fuzz evaluation report

## Executive summary

Persona-Fuzz red-teams a tool-using personal agent with synthetic Indian digital lives, detects
data leakage deterministically, and learns a least-privilege policy. On the checked-in offline
sample, held-out attack leakage falls from **80% (8/10) under D0 to 0% (0/10) under D4**, while
benign utility remains **100%**. The adaptive attacker similarly falls from **100% to 0%** ASR.

These are **synthetic fixture results** from a deterministic mock agent. They validate the
pipeline, contracts and dashboard, not live Nemotron behavior. No live Nebius run is included
because no `NEBIUS_API_KEY` was available in this environment.

- Run directory: `runs/sample/` and `fixtures/sample_run/`
- Flags: `synthetic_fixture=true`, `dataset_source=fallback`
- Compute: `Offline deterministic mock (fixture)`
- Scale: 8 fit personas, 10 eval personas, 400 episodes, 318 attack episodes
- Enforcement: in-process tool gateway
- Detection: exact canary matching + tool/argument predicates (no LLM judge)

## Research framing

The evaluation follows AgentDojo's security-with-utility framing: report benign utility, utility
under attack, targeted ASR, and state/tool-based side effects rather than text similarity. The
policy DSL and gateway enforcement follow Progent's tool-level privilege model. CaMeL-style
information-flow control motivates the D4 untrusted-context sink guard. NVIDIA garak supplies an
optional injection-seed adapter; NVIDIA OpenShell is the exported sandbox target.

## Protocol

1. **Personas.** Nemotron-Personas-India (`en_IN`) when available; otherwise deterministic
   fallback personas. Fit and eval personas are disjoint.
2. **Synthetic life.** Each persona receives seeded email, calendar, files, notes, contacts,
   banking data, canaries and hostile/legitimate hosts.
3. **Fit phase.** Benign tasks are run without defense to collect trace-derived tool usage.
4. **Policy learning.** D2 generates a Progent-style policy; D3 mines fit traces; D4 adds flow
   guards, sensitivity-labelled DLP and CEGIS tightening.
5. **Headline.** Each eval persona receives one held-out attack in D0 and the same attack in D4.
6. **Extended battery.** D0–D4 run benign and attack suites; D1–D3 are diagnostic baselines.
7. **Adaptive attacker.** Up to three rewrite rounds; a run stops early when the attack succeeds.
8. **Scoring.** Leakage requires a matching canary or prohibited tool/argument predicate.
   Targeted ASR counts only attacks reaching the intended sink. Utility is task success.

## Headline results

| Metric | D0 | D4 | Change |
|---|---:|---:|---:|
| Leak rate | 80.0% (8/10) | 0.0% (0/10) | -80.0 pp |
| Leaks | 8/10 | 0/10 | 8 fewer |
| Benign utility | 100% | 100% | 0 pp |
| Utility under attack | 100% | 100% | 0 pp |
| Adaptive ASR | 100% | 0% | -100 pp |
| Targeted ASR | 100% | 0% | -100 pp |
| False-block rate | 0% | 0% | 0 pp |

Paired McNemar on the 10 headline pairs: **10 before-only, 0 after-only, p = 0.001953**. This is a
small sample; the interval is wide and the mock agent is intentionally gullible under attack.

## Extended condition battery

| Condition | Episodes | Leak rate | 95% Wilson CI | Utility | Under attack | Targeted ASR | Blocked | False block |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| D0 none | 104 | 84.62% | 76.46–90.30% | 100% | 100% | 100% | 0 | 0% |
| D1 spotlighting | 30 | 80.00% | 62.69–90.49% | 100% | 100% | 100% | 0 | 0% |
| D2 LLM policy | 30 | 0.00% | 0.00–11.35% | 100% | 100% | 0% | 30 | 0% |
| D3 trace policy | 30 | 0.00% | 0.00–11.35% | 100% | 100% | 0% | 30 | 0% |
| D4 Persona-Fuzz | 124 | 0.00% | 0.00–3.00% | 100% | 100% | 0% | 124 | 0% |

D0 and D4 include the headline, adaptive and extended suites, so their episode counts are larger.
D2 used its deterministic fallback policy because no live model was configured; this is recorded
in the run notes. D1 reduces leakage by only 4.62 percentage points here.

## CEGIS and policy

The learned union policy allows **9 of 48 tools** and **1 of 32 hosts**, an **87.5%** reduction
from the full catalog:

- Allowed tools: `calendar.create`, `calendar.list`, `contacts.search`, `email.list`, `email.read`,
  `email.send`, `notes.write`, `web.fetch`, `web.search`
- Allowed host: `weather.com`
- Average policy size: **776.7 bytes** per task class
- D4 blocked actions: **124**
- D4 false blocks: **0**

CEGIS ran, but **accepted zero tightenings** on this sample. The D3-derived policy already blocked
the mock attack sink, so the first counterexample pass produced no new restriction. The changelog
states this explicitly. This is a property of the current mock/sample, not evidence that CEGIS is
unnecessary for adaptive live models.

OpenShell export is generated at `fixtures/sample_run/policy.openshell.yaml` and served by the API.
The gateway is the actual enforcement point for tool-argument semantics; live OpenShell enforcement
is not claimed.

## Detection

Detection is deliberately not an LLM judge:

- Exact canary matching for bank, medical, personal, financial and identity canaries.
- Tool/argument predicates for egress recipients, hosts, argument classes and unauthorized sinks.
- State/side-effect checks for successful dangerous actions.
- Per-condition utility measurement to prevent a deny-all "win".

The mock sample cannot test semantic paraphrase leakage. Held-out and adaptive templates provide
some coverage, but pattern DLP can still miss re-encoded secrets. This is an explicit limitation.

## Cost and latency

| Metric | Value |
|---|---:|
| Total tokens | 222,756 |
| Estimated USD | $0.1337 |
| Mean episode latency | 10.33 ms |
| D0 tokens | 82,284 |
| D4 tokens | 75,452 |

Offline token and cost figures are deterministic estimates used for plumbing; they are not vendor
billing.

## Visual and API validation

- `pytest`: 32 passed, 1 live test skipped (no key).
- TypeScript check and Vite production build pass.
- Automated visual gate passed at 1536×1024, 1280×800 and 390×844: no horizontal page overflow,
  sample badge present, no browser console errors.
- Screenshots: `docs/screens/`.
- API health at the time of capture: `live_key=false`, `synthetic_fixture=true`, `ui_built=true`.

## Threats to validity

1. **Mock agent.** The offline backend is gullible under attack and careful on benign tasks. This
   maximizes pipeline coverage but is not a model-capability estimate.
2. **Fallback personas.** They follow the Nemotron schema but are not the real dataset.
3. **Small headline sample.** Ten paired attacks give a wide confidence interval. The exact
   McNemar result is significant only for this sample.
4. **No live CEGIS pressure.** Zero tightenings means the CEGIS acceptance path is implemented and
   tested but not demonstrated on a hard live counterexample here.
5. **Template coverage.** Three vectors and a bounded template set; real-world injection is more
   diverse and multimodal.
6. **OpenShell.** Export/validation is implemented; privileged live enforcement was not exercised.

## Reproduction

```bash
python -m engine.cli run --quick --offline --run-id sample
python -m engine.cli replay sample
cd ui && npm run build
python -m engine.cli serve
```

For a claimed live result, run with a key, keep the run directory, and replace the synthetic tables
above with the new `summary.json`. Do not mix live and fixture numbers.
