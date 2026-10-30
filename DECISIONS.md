# Decisions

Architecture decisions and documented fallbacks. Each entry records context, decision and
consequence. Do not rewrite history after live results exist; add a new entry instead.

## D-001: Offline deterministic mock when no Nebius key is present

**Context:** This build environment has no `NEBIUS_API_KEY`. AGENTS.md requires no hardcoded or
fake metrics and says to choose a documented fallback when blocked.

**Decision:** Run the deterministic mock backend and mark every such run `synthetic_fixture=true`
with `compute_label="Offline deterministic mock (fixture)"`. The UI shows a persistent "Sample
data" badge. `doctor` reports the key as absent.

**Consequence:** The sample validates contracts, runner, detection, policy learning, API and UI.
It is not evidence of live-model behavior. A live run must produce separate numbers.

## D-002: Deterministic fallback personas

**Context:** `nvidia/Nemotron-Personas-India` (`en_IN`) and `HF_TOKEN` are not available.

**Decision:** Generate 200 deterministic fallback personas that follow the Nemotron persona schema,
write them to `fixtures/personas_fallback.jsonl`, and set `dataset_source=fallback`.

**Consequence:** Persona diversity is synthetic but reproducible. Rows are visibly labelled as
fallback in the UI and summary; they must not be described as the NVIDIA dataset.

## D-003: No LLM judge for leakage

**Context:** AGENTS.md requires deterministic detection.

**Decision:** Leakage is canary matching plus tool/argument predicates and state checks. LLMs may
generate attacks and policies but never decide whether a leak occurred.

**Consequence:** Results are reproducible and auditable. Rephrased/re-encoded leakage can evade
pattern DLP; this is reported as a limitation and measured by held-out templates.

## D-004: Headline is D0 → D4 on disjoint eval data

**Context:** D1–D3 are useful baselines, but a headline must test generalization.

**Decision:** Train policies on fit personas and train attacks. Evaluate the headline on disjoint
eval personas and held-out templates. Adaptive attacks run on eval personas.

**Consequence:** D0 and D4 episode counts are larger than D1–D3 because they include multiple
suites. The UI labels this rather than comparing raw episode counts as if they were equal.

## D-005: D3 already blocks the mock sink, so sample CEGIS records zero tightenings

**Context:** On the offline sample, D3's trace-derived policy already denies the sink used by the
mock attack. The CEGIS loop receives no accepted counterexample-driven tightening.

**Decision:** Keep the CEGIS implementation and acceptance checks, record the empty changelog
honestly, and do not manufacture a counterexample or tune a metric to make the curve look better.
The convergence chart shows D0 and the D4 point.

**Consequence:** The sample proves the CEGIS path runs and preserves utility, but does not
demonstrate a successful live tightening. A live/adaptive run is required for that claim.

## D-006: D2 deterministic fallback policy

**Context:** Progent-style D2 normally asks an LLM to write a policy. No model was configured in the
offline run.

**Decision:** Use the deterministic D2 policy generator and write per-task notes:
`D2 <task>: No model configured; used deterministic D2 baseline.`

**Consequence:** D2 numbers are a baseline, not an LLM-policy result. Notes appear in the summary
and UI ledger.

## D-007: Gateway is the enforcement point; OpenShell is exported

**Context:** OpenShell YAML describes sandbox filesystem/network/process controls, while the
attacks target tool-argument semantics.

**Decision:** Enforce tool/host/argument policy in the in-process gateway. Compile and validate an
OpenShell YAML artifact for the union policy. Only label enforcement "OpenShell" when it is
actually used.

**Consequence:** There is no false claim of live OpenShell sandbox enforcement. The deployed
enforcement label is `gateway`.

## D-008: Local sharding default

**Context:** A default of five shards caused a single local quick run to evaluate only one fifth of
personas.

**Decision:** Default to one shard for local runs. `--shards/--shard-id` remain available for
distributed execution; Nebius executor currently falls back to a labelled local worker.

**Consequence:** Quick runs are complete by default. Multi-shard orchestration is not claimed as a
live Nebius Serverless Jobs result.

## D-009: Per-model comparison only where it is meaningful

**Context:** The offline provider is a single model; iterating model lists makes no sense and could
create misleading rows.

**Decision:** For offline or single-model runs, fill `per_model` from the headline D0/D4 episodes.
For live multi-model runs, use a capped 20-persona sample per model.

**Consequence:** The sample has one honest model row. Multi-model breadth remains a scoped adapter.

## D-010: Flagged fixture fallback in the API/UI

**Context:** The dashboard must work before a live run exists, without pretending fixture data is a
real result.

**Decision:** The API selects the newest `runs/*/summary.json` and falls back to
`fixtures/sample_run/`. The source field distinguishes fixture from run. The UI always shows the
summary's synthetic flag.

**Consequence:** Judges can open the UI immediately. A fixture can never appear as live data.

## D-011: Attack Explorer server-side pagination

**Context:** Rendering hundreds of full attack rows produced a 22,000 px page and unnecessary DOM
work.

**Decision:** Page attacks 40 at a time and filter by vector in the API (`GET /api/episodes?vector=`).
Search remains a client-side filter over the current page.

**Consequence:** The page is stable at all target viewports. Global search across all pages is a
known UX limitation; it can move server-side later.

## D-012: Unique CEGIS episode ids

**Context:** Re-running CEGIS iterations reused episode ids, so the `EpisodeStore` skipped new
counterexamples and the loop could appear converged for the wrong reason.

**Decision:** Prefix train/held-out/benign suites with a call counter
(`cegis-train-<n>`, `cegis-heldout-<n>`, `cegis-benign-<n>`).

**Consequence:** Every iteration is persisted and auditable. Resume tests remain deterministic.

## D-013: Utility on the eval split only

**Context:** Filling condition utility with fit episodes would inflate or misattribute utilities.

**Decision:** Compute headline benign utility from eval episodes only; fit utility is used only for
the CEGIS baseline/acceptance threshold.

**Consequence:** Reported utility matches the held-out claim. A tightening that drops utility below
`baseline - epsilon` is rejected and logged.

## D-014: No secret logging

**Context:** Live runs require an API key; logs and exports are shared in demos.

**Decision:** Read secrets from environment/.env only, never print keys, and redact authorization
headers in client errors. `.env` is git-ignored.

**Consequence:** Demo logs are safe to screen-record. Live connectivity is still diagnosable through
`doctor` without exposing the credential.

## D-015: Docker runs offline by default without a key

**Context:** A judge may run the image without Nebius credentials.

**Decision:** The container starts the API and UI; without `NEBIUS_API_KEY` it uses the same
flagged offline sample/mock path. Live runs are enabled by passing the key at runtime.

**Consequence:** The demo is reproducible without spending money, and no container result is
mislabeled as live.
