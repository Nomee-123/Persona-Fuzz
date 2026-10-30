from __future__ import annotations

import asyncio
import json
import shutil
import sys
from pathlib import Path
from typing import Optional

import typer

from .config import FIXTURES_DIR, RESULTS_DIR, ROOT, get_settings
from .defense.compile_openshell import compile_openshell, validate_openshell
from .defense.policy_ir import Policy
from .llm.client import LLMError, TokenFactoryClient
from .runner.battery import RunConfig, RunEngine, make_run_id
from .world.persona_loader import load_personas, write_fallback_jsonl
from .world.registry import HOSTS, TOOLS

app = typer.Typer(no_args_is_help=True, add_completion=False, help="Persona-Fuzz: red-team and harden a personal AI agent.")


def _echo(message: str = "") -> None:
    typer.echo(message)


@app.command()
def doctor() -> None:
    """Check keys, model discovery, tool mode, personas, and run directories without printing secrets."""
    settings = get_settings()
    _echo("Persona-Fuzz doctor")
    _echo(f"  repo: {ROOT}")
    _echo(f"  python: {sys.version.split()[0]}")
    _echo(f"  token factory key: {'present' if settings.has_key else 'absent -> offline mock mode'}")
    _echo(f"  base url: {settings.base_url}")
    if settings.has_key:
        async def probe() -> None:
            client = TokenFactoryClient(settings)
            try:
                chosen, nemotrons = await client.discover()
                mode = await client.probe_tool_mode(chosen)
                _echo(f"  model discovered: {chosen}")
                _echo(f"  nemotron models: {len(nemotrons)}")
                _echo(f"  tool mode: {mode}")
            except LLMError as exc:
                _echo(f"  model discovery failed: {exc}")
            finally:
                await client.close()

        asyncio.run(probe())
    else:
        _echo(f"  model: offline/mock-nemotron (no live calls will be made)")
    _echo(f"  tools: {len(TOOLS)} | hosts: {len(HOSTS)}")
    elevated = [p for p in (ROOT, FIXTURES_DIR, settings.runs_dir) if not p.exists()]
    if elevated:
        _echo(f"  directories to create: {', '.join(str(p) for p in elevated)}")
    try:
        fit, ev, source = load_personas(n_fit=1, n_eval=1, settings=settings)
        _echo(f"  persona source: {source} ({fit[0].display_name}, {ev[0].display_name})")
    except Exception as exc:
        _echo(f"  persona source: fallback (probe failed: {exc})")
    _echo(f"  UI: {'built' if (ROOT / 'ui' / 'package.json').exists() else 'missing'}")
    _echo(f"  outputs: {settings.runs_dir}")


@app.command("personas")
def personas_cmd(
    n: int = typer.Option(200, help="Number of fallback personas to write."),
    preview: int = typer.Option(2, help="Rows to print."),
) -> None:
    """Write deterministic fallback personas and preview a few."""
    path = write_fallback_jsonl(FIXTURES_DIR / "personas_fallback.jsonl", n)
    _echo(f"wrote {path}")
    rows = [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]
    for row in rows[: max(0, preview)]:
        _echo(f"  {row['persona_id']} {row['display_name']} | {row['district']}, {row['state']} | {row['occupation']}")


@app.command("run")
def run_cmd(
    quick: bool = typer.Option(False, help="Quick local smoke (P4 gate scale)."),
    full: bool = typer.Option(False, help="Full eval scale (fit/eval defaults)."),
    seed: int = typer.Option(20260426),
    run_id: Optional[str] = typer.Option(None),
    no_adaptive: bool = typer.Option(False),
    extended: bool = typer.Option(True, "--extended/--no-extended"),
    offline: bool = typer.Option(False, help="Force the deterministic offline mock even if a key exists."),
    model: str = typer.Option("", help="Override the agent model id."),
    executor: str = typer.Option("local", help="local or nebius."),
    shards: int = typer.Option(1),
    shard_id: int = typer.Option(0),
    max_episodes: int = typer.Option(0),
    max_usd: float = typer.Option(25.0),
) -> None:
    """Run discovery -> D3 fit -> D4 CEGIS -> held-out + adaptive evaluation."""
    settings = get_settings()
    if model:
        settings.model = model
    if full:
        quick = False
    if executor not in {"local", "nebius"}:
        raise typer.BadParameter("executor must be local or nebius")
    if executor == "nebius":
        _echo("nebius executor: using the documented local fallback worker; results are labelled local unless PF_NEBIUS_JOB_ID is present.")
        executor = "local"
    cfg = RunConfig(
        run_id=run_id or make_run_id(),
        quick=quick,
        full=full,
        seed=seed,
        no_adaptive=no_adaptive,
        extended=extended,
        offline=offline,
        models=[model] if model else [],
        executor=executor,
        shards=shards,
        shard_id=shard_id,
        max_episodes=max_episodes,
        max_usd=max_usd,
    )

    async def go() -> dict:
        engine = RunEngine(cfg)
        try:
            return await engine.run()
        finally:
            await engine.close()

    summary = asyncio.run(go())
    metrics = summary["metrics"]
    _echo("")
    _echo(f"run {summary['run_id']} completed: {summary['status']}")
    _echo(f"  headline leak {metrics['leaks_before']}/{metrics['total_runs']} -> {metrics['leaks_after']}/{metrics['total_runs']} ({metrics['leak_rate_before']:.0%} -> {metrics['leak_rate_after']:.0%})")
    _echo(f"  benign utility D0 {metrics['utility_benign_d0']:.0%} -> D4 {metrics['utility_benign_d4']:.0%}")
    _echo(f"  synthetic_fixture={str(summary['synthetic_fixture']).lower()} | compute={summary['config']['compute_label']}")
    _echo(f"  summary: {settings.runs_dir / summary['run_id'] / 'summary.json'}")


@app.command()
def serve(
    host: str = typer.Option("127.0.0.1"),
    port: int = typer.Option(8000),
    reload: bool = typer.Option(False),
) -> None:
    """Serve the API (and built UI) on the given port."""
    import uvicorn

    uvicorn.run("engine.api.app:app", host=host, port=port, reload=reload)


@app.command()
def replay(
    run_id: Optional[str] = typer.Argument(None),
    out: Optional[Path] = typer.Option(None),
) -> None:
    """Render an offline replay markdown from a completed run."""
    settings = get_settings()
    runs = settings.runs_dir
    if run_id:
        run_dir = runs / run_id
    else:
        candidates = sorted(runs.glob("*/summary.json"), key=lambda p: p.stat().st_mtime)
        if not candidates:
            raise typer.BadParameter("no runs found; run `python -m engine.cli run --quick` first")
        run_dir = candidates[-1].parent
    summary = json.loads((run_dir / "summary.json").read_text(encoding="utf-8"))
    episodes = []
    ep_path = run_dir / "episodes.jsonl"
    if ep_path.exists():
        episodes = [json.loads(line) for line in ep_path.read_text(encoding="utf-8").splitlines() if line.strip()]
    target = out or (RESULTS_DIR / run_dir.name / "replay.md")
    target.parent.mkdir(parents=True, exist_ok=True)
    metrics = summary["metrics"]
    lines = [
        f"# Replay: {summary['run_id']}",
        "",
        f"- synthetic_fixture: `{str(summary['synthetic_fixture']).lower()}`",
        f"- dataset_source: `{summary['dataset_source']}`",
        f"- compute: {summary['config']['compute_label']}",
        f"- headline leak: {metrics['leaks_before']}/{metrics['total_runs']} -> {metrics['leaks_after']}/{metrics['total_runs']}",
        f"- benign utility D0 -> D4: {metrics['utility_benign_d0']:.0%} -> {metrics['utility_benign_d4']:.0%}",
        f"- adaptive ASR D0 -> D4: {metrics['adaptive_asr_d0']:.0%} -> {metrics['adaptive_asr_d4']:.0%}",
        f"- policy bytes: {metrics['avg_policy_bytes']:.0f}",
        "",
        "## CEGIS curve",
        "",
        "| iter | train leak | held-out leak | utility | bytes |",
        "|---:|---:|---:|---:|---:|",
    ]
    for p in summary["curve"]:
        lines.append(f"| {p['iter']} | {p['train_leak']:.0%} | {p['heldout_leak']:.0%} | {p['utility']:.0%} | {p.get('policy_bytes', 0)} |")
    lines += ["", "## Example trace", ""]
    ex = summary.get("example_trace_ids", {})
    chosen = next((e for e in episodes if e.get("episode_id") == ex.get("episode_id")), None)
    if chosen:
        lines.append(f"Persona `{chosen['persona_id']}` | condition `{chosen['condition']}` | task `{chosen['task_class']}`")
        for step in chosen["steps"]:
            role = step["role"]
            call = step.get("tool_call")
            gateway = step.get("gateway")
            if call:
                lines.append(f"- t{step['t']} {role}: `{call['name']}` {json.dumps(call['args'], ensure_ascii=False)[:240]}")
                if gateway:
                    lines.append(f"  - gateway: {gateway['decision']} ({gateway['rule_id']}) {gateway['reason']}")
            elif step.get("content"):
                lines.append(f"- t{step['t']} {role}: {step['content'][:240]}")
    lines += ["", "## Notes", ""]
    lines += [f"- {n}" for n in summary.get("notes", [])]
    target.write_text("\n".join(lines) + "\n", encoding="utf-8")
    _echo(f"wrote {target}")


@app.command("compile-openshell")
def compile_cmd(
    policy_path: Path = typer.Option(..., exists=True, dir_okay=False),
    out: Optional[Path] = typer.Option(None),
) -> None:
    """Compile a policy JSON object into an OpenShell sandbox YAML."""
    data = json.loads(policy_path.read_text(encoding="utf-8"))
    if "union" in data:
        data = data["union"]
    policy = Policy.model_validate(data)
    text = compile_openshell(policy)
    target = out or policy_path.with_suffix(".openshell.yaml")
    target.write_text(text, encoding="utf-8")
    ok, errors = validate_openshell(text)
    _echo(f"wrote {target} ({'valid' if ok else 'INVALID'})")
    for err in errors:
        _echo(f"  - {err}")


@app.command("make-sample")
def make_sample(
    run_id: str = typer.Option("sample", help="Fixture run id."),
    force: bool = typer.Option(False),
) -> None:
    """Generate the flagged synthetic sample run that the UI uses when no real run exists."""
    target = FIXTURES_DIR / "sample_run"
    if target.exists() and not force:
        raise typer.BadParameter(f"{target} exists; use --force to replace it")
    cfg = RunConfig(run_id=run_id, quick=True, seed=20260426, offline=True, no_adaptive=False)
    engine = RunEngine(cfg)

    async def go() -> dict:
        try:
            return await engine.run()
        finally:
            await engine.close()

    summary = asyncio.run(go())
    if not summary["synthetic_fixture"]:
        raise RuntimeError("sample run must be flagged synthetic_fixture")
    target.mkdir(parents=True, exist_ok=True)
    run_dir = get_settings().runs_dir / run_id
    for name in ("summary.json", "episodes.jsonl", "policy.json", "policy.md", "policy.openshell.yaml", "config.json", "events.jsonl"):
        src = run_dir / name
        if src.exists():
            shutil.copy2(src, target / name)
    (target / "NOTICE.txt").write_text(
        "SAMPLE DATA: generated by a deterministic offline mock backend. "
        "synthetic_fixture=true. Do not cite these numbers as live model results.\n",
        encoding="utf-8",
    )
    _echo(f"wrote flagged synthetic sample to {target}")


def main() -> None:
    app()


if __name__ == "__main__":
    main()
