from __future__ import annotations

import asyncio
import io
import json
import zipfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from fastapi import FastAPI, HTTPException, Query, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse, PlainTextResponse, Response, StreamingResponse
from pydantic import BaseModel, Field
from sse_starlette.sse import EventSourceResponse

from ..config import FIXTURES_DIR, ROOT, get_settings
from ..runner.battery import RunConfig, RunEngine, make_run_id

app = FastAPI(title="Persona-Fuzz API", version="0.1.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173", "http://localhost:8000", "http://127.0.0.1:8000"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)


class RunRequest(BaseModel):
    quick: bool = True
    full: bool = False
    seed: int = 20260426
    no_adaptive: bool = False
    extended: bool = True
    offline: bool = False
    model: str = ""
    run_id: str | None = None
    max_episodes: int = Field(default=0, ge=0)
    max_usd: float = Field(default=25.0, gt=0)


class RunManager:
    def __init__(self) -> None:
        self.task: asyncio.Task | None = None
        self.run_id: str = ""
        self.status: str = "idle"
        self.error: str = ""
        self.lock = asyncio.Lock()

    @property
    def running(self) -> bool:
        return self.task is not None and not self.task.done()

    def start(self, cfg: RunConfig) -> None:
        self.run_id = cfg.run_id
        self.status = "running"
        self.error = ""
        self.task = asyncio.create_task(self._run(cfg))

    async def _run(self, cfg: RunConfig) -> None:
        engine = RunEngine(cfg)
        try:
            await engine.run()
            self.status = "completed"
        except asyncio.CancelledError:
            self.status = "cancelled"
            raise
        except Exception as exc:
            self.status = "failed"
            self.error = f"{type(exc).__name__}: {exc}"
            run_dir = get_settings().runs_dir / cfg.run_id
            run_dir.mkdir(parents=True, exist_ok=True)
            (run_dir / "error.json").write_text(json.dumps({"error": self.error, "ts": datetime.now(timezone.utc).isoformat()}, indent=2), encoding="utf-8")
        finally:
            await engine.close()


manager = RunManager()


def _runs_dir() -> Path:
    return get_settings().runs_dir


def _all_run_dirs() -> list[Path]:
    dirs: list[Path] = []
    base = _runs_dir()
    if base.exists():
        dirs = [p.parent for p in base.glob("*/summary.json")]
    sample = FIXTURES_DIR / "sample_run"
    if (sample / "summary.json").exists():
        dirs.append(sample)
    return dirs


def _run_dir(run_id: str | None = None) -> Path:
    if run_id:
        safe = Path(run_id).name
        for candidate in _all_run_dirs():
            if candidate.name == safe:
                return candidate
        raise HTTPException(404, f"run {safe!r} not found")
    dirs = _all_run_dirs()
    if not dirs:
        raise HTTPException(404, "no runs yet; start a quick run")
    return max(dirs, key=lambda p: (p / "summary.json").stat().st_mtime)


def _summary(run_id: str | None = None) -> dict[str, Any]:
    path = _run_dir(run_id) / "summary.json"
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except Exception as exc:
        raise HTTPException(500, f"summary unreadable: {exc}") from exc
    data["source"] = "fixture" if path.parent.name == "sample_run" and path.parent.parent == FIXTURES_DIR else "run"
    return data


def _episodes(run_id: str | None = None) -> list[dict[str, Any]]:
    path = _run_dir(run_id) / "episodes.jsonl"
    if not path.exists():
        return []
    rows = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if line.strip():
            try:
                rows.append(json.loads(line))
            except Exception:
                continue
    return rows


@app.get("/api/health")
async def health() -> dict[str, Any]:
    settings = get_settings()
    try:
        latest = _summary()
        latest_id = latest["run_id"]
        synthetic = latest["synthetic_fixture"]
    except HTTPException:
        latest_id = ""
        synthetic = True
    return {
        "status": "ok",
        "live_key": settings.has_key,
        "running": manager.running,
        "run_id": manager.run_id if manager.running else latest_id,
        "synthetic_fixture": synthetic,
        "ui_built": (ROOT / "ui" / "dist" / "index.html").exists(),
    }


@app.get("/api/run")
async def get_run(run_id: str | None = Query(default=None)) -> dict[str, Any]:
    return _summary(run_id)


@app.get("/api/runs")
async def list_runs() -> list[dict[str, Any]]:
    out = []
    for d in _all_run_dirs():
        try:
            s = json.loads((d / "summary.json").read_text(encoding="utf-8"))
        except Exception:
            continue
        out.append(
            {
                "run_id": s.get("run_id"),
                "status": s.get("status"),
                "synthetic_fixture": s.get("synthetic_fixture", True),
                "dataset_source": s.get("dataset_source"),
                "leak_rate_before": s.get("metrics", {}).get("leak_rate_before", 0),
                "leak_rate_after": s.get("metrics", {}).get("leak_rate_after", 0),
                "finished_at": s.get("finished_at"),
                "mtime": (d / "summary.json").stat().st_mtime,
                "source": "fixture" if d.name == "sample_run" else "run",
            }
        )
    return sorted(out, key=lambda r: r["mtime"], reverse=True)


@app.get("/api/run/status")
async def run_status() -> dict[str, Any]:
    return {
        "running": manager.running,
        "run_id": manager.run_id,
        "status": manager.status,
        "error": manager.error,
    }


@app.post("/api/run")
async def start_run(body: RunRequest) -> dict[str, Any]:
    async with manager.lock:
        if manager.running:
            raise HTTPException(409, f"run {manager.run_id} is already running")
        cfg = RunConfig(
            run_id=body.run_id or make_run_id(),
            quick=body.quick,
            full=body.full,
            seed=body.seed,
            no_adaptive=body.no_adaptive,
            extended=body.extended,
            offline=body.offline,
            models=[body.model] if body.model else [],
            max_episodes=body.max_episodes,
            max_usd=body.max_usd,
        )
        if body.full:
            cfg.quick = False
        manager.start(cfg)
    return {"run_id": cfg.run_id, "status": "running"}


@app.post("/api/run/cancel")
async def cancel_run() -> dict[str, Any]:
    if not manager.running or manager.task is None:
        raise HTTPException(409, "no run is currently running")
    manager.task.cancel()
    return {"run_id": manager.run_id, "status": "cancelling"}


@app.get("/api/episodes")
async def list_episodes(
    run_id: str | None = Query(default=None),
    condition: str | None = Query(default=None),
    task_class: str | None = Query(default=None),
    vector: str | None = Query(default=None),
    attack: bool | None = Query(default=None),
    leak: bool | None = Query(default=None),
    limit: int = Query(default=200, ge=1, le=2000),
    offset: int = Query(default=0, ge=0),
) -> dict[str, Any]:
    rows = _episodes(run_id)
    if condition:
        rows = [r for r in rows if r.get("condition") == condition]
    if task_class:
        rows = [r for r in rows if r.get("task_class") == task_class]
    if vector:
        rows = [r for r in rows if (r.get("attack") or {}).get("vector") == vector]
    if attack is not None:
        rows = [r for r in rows if (r.get("attack") is not None) == attack]
    if leak is not None:
        rows = [r for r in rows if bool(r.get("outcome", {}).get("leak", {}).get("detected")) == leak]
    total = len(rows)
    page = [
        {
            "episode_id": r.get("episode_id"),
            "persona_id": r.get("persona_id"),
            "condition": r.get("condition"),
            "task_class": r.get("task_class"),
            "attack": r.get("attack"),
            "outcome": r.get("outcome"),
            "tokens": r.get("tokens", 0),
            "latency_ms": r.get("latency_ms", 0),
            "split": r.get("split"),
        }
        for r in rows[offset : offset + limit]
    ]
    return {"total": total, "offset": offset, "limit": limit, "episodes": page}


@app.get("/api/episodes/{episode_id}")
async def get_episode(episode_id: str, run_id: str | None = Query(default=None)) -> dict[str, Any]:
    for row in _episodes(run_id):
        if row.get("episode_id") == episode_id:
            return row
    raise HTTPException(404, f"episode {episode_id!r} not found")


@app.get("/api/policy")
async def get_policy(run_id: str | None = Query(default=None)) -> dict[str, Any]:
    path = _run_dir(run_id) / "policy.json"
    if not path.exists():
        return {"union": _summary(run_id)["policy"]["json"], "by_task_class": {}, "changelog": []}
    return json.loads(path.read_text(encoding="utf-8"))


@app.get("/api/policy/openshell", response_class=PlainTextResponse)
async def get_openshell(run_id: str | None = Query(default=None)) -> PlainTextResponse:
    path = _run_dir(run_id) / "policy.openshell.yaml"
    if path.exists():
        return PlainTextResponse(path.read_text(encoding="utf-8"), media_type="application/yaml")
    return PlainTextResponse(_summary(run_id)["policy"]["openshell_yaml"], media_type="application/yaml")


@app.get("/api/export")
async def export_run(run_id: str | None = Query(default=None)) -> Response:
    d = _run_dir(run_id)
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        for name in ("summary.json", "config.json", "episodes.jsonl", "policy.json", "policy.md", "policy.openshell.yaml"):
            p = d / name
            if p.exists():
                zf.write(p, arcname=f"{d.name}/{name}")
    buf.seek(0)
    return Response(
        content=buf.read(),
        media_type="application/zip",
        headers={"Content-Disposition": f'attachment; filename="persona-fuzz-{d.name}.zip"'},
    )


def _events_path() -> Path | None:
    try:
        return _run_dir() / "events.jsonl"
    except HTTPException:
        return None


@app.get("/api/run/stream")
async def stream(request: Request) -> EventSourceResponse:
    async def gen():
        offset = 0
        last_snapshot = 0.0
        while True:
            if await request.is_disconnected():
                break
            path = _events_path()
            if path and path.exists():
                with path.open("r", encoding="utf-8") as fh:
                    fh.seek(offset)
                    while True:
                        line = fh.readline()
                        if not line:
                            break
                        offset = fh.tell()
                        try:
                            event = json.loads(line)
                        except Exception:
                            continue
                        yield {"event": event.get("type", "message"), "data": json.dumps(event.get("data", {}), ensure_ascii=False)}
            now = asyncio.get_event_loop().time()
            if now - last_snapshot > 2:
                last_snapshot = now
                snapshot = {
                    "running": manager.running,
                    "status": manager.status,
                    "run_id": manager.run_id,
                }
                try:
                    s = _summary()
                    snapshot.update(
                        {
                            "run_id": s["run_id"],
                            "status": s["status"],
                            "synthetic_fixture": s["synthetic_fixture"],
                            "metrics": s["metrics"],
                        }
                    )
                except HTTPException:
                    pass
                yield {"event": "snapshot", "data": json.dumps(snapshot, ensure_ascii=False)}
            await asyncio.sleep(0.75)

    return EventSourceResponse(gen())


_UI_DIST = ROOT / "ui" / "dist"
if (_UI_DIST / "index.html").exists():
    from fastapi.staticfiles import StaticFiles

    app.mount("/assets", StaticFiles(directory=_UI_DIST / "assets"), name="assets")

    @app.get("/{path:path}", include_in_schema=False)
    async def spa(path: str):
        candidate = _UI_DIST / path
        if path and candidate.is_file():
            return FileResponse(candidate)
        return FileResponse(_UI_DIST / "index.html")
