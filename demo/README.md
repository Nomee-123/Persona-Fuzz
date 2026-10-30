# Offline demo runbook

This is a four-minute walkthrough that needs no API key and no network. It replays the checked-in
synthetic sample, then opens the dashboard. Everything is labelled fixture data.

## Option A: local

From the repository root:

```bash
python -m engine.cli replay sample
python -m engine.cli serve
```

Open <http://127.0.0.1:8000>.

Windows PowerShell:

```powershell
.\.venv\Scripts\python.exe -m engine.cli replay sample
.\.venv\Scripts\python.exe -m engine.cli serve
```

## Option B: Docker

```bash
docker compose -f docker/compose.yaml up --build
```

Open <http://127.0.0.1:8000>. The image uses the same offline sample unless
`NEBIUS_API_KEY` is supplied.

## Walkthrough

1. **Overview.** Point out the Sample data badge, the 80% → 0% held-out leak rate and the unchanged
   100% utility. Read the honesty ledger: fixture, fallback personas, deterministic detection,
   held-out headline.
2. **CEGIS convergence.** The first point is D0; the second is the D4 point after guards/DLP. The
   policy needed no tightening on this sample because D3 already blocked the mock sink. This is
   stated rather than hidden.
3. **Defense conditions.** D0 leaks; D1 barely helps; D2 and D3 block; D4 blocks with 100% utility.
   Note that D2 is a deterministic fallback because no model was configured.
4. **Run detail.** Show cost, tokens, latency and per-condition counts. Open the evidence table.
5. **Attack explorer.** Filter by vector, condition or leak; open a trace. Show the untrusted
   content, the malicious tool call, the gateway decision and the canary result.
6. **Policy.** Show the 9/48 tool allowlist, 1/32 host allowlist, 87.5% reduction, argument rules,
   FR1 flow rule and the zero-tightening changelog. Download the OpenShell YAML.
7. **Report.** Show the generated summary and the explicit limitations. Download the ZIP.
8. **Optional live run.** With a key, click “Run quick smoke” and explain that the new run is
   labelled live and gets a new run directory; the sample remains fixture data.

## Regenerating the sample

```bash
python -m engine.cli make-sample --force
python -m engine.cli replay sample
cd ui && npm run build
```

This takes about a minute and rewrites `runs/sample/` and `fixtures/sample_run/`. The sample must
remain `synthetic_fixture=true`.
