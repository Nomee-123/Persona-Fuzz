from __future__ import annotations

import asyncio
import hashlib
import json
import random
import sqlite3
import time
from pathlib import Path
from typing import Any, Iterable

import httpx

from ..config import CORE_MODEL_PREFERENCES, Settings, get_settings
from .models import LLMResponse, ModelInfo, ToolCall, Usage
from .toolcall import parse_react_response, react_protocol_instruction, first_json_object


class LLMError(RuntimeError):
    pass


def _key(payload: dict[str, Any], mode: str) -> str:
    blob = json.dumps({"payload": payload, "mode": mode}, sort_keys=True, ensure_ascii=False)
    return hashlib.sha256(blob.encode("utf-8")).hexdigest()


class ResponseCache:
    def __init__(self, path: Path | None):
        self.path = path
        self._conn: sqlite3.Connection | None = None
        if path is not None:
            path.parent.mkdir(parents=True, exist_ok=True)
            self._conn = sqlite3.connect(str(path), check_same_thread=False)
            self._conn.execute("CREATE TABLE IF NOT EXISTS responses (k TEXT PRIMARY KEY, v TEXT)")
            self._conn.commit()

    def get(self, key: str) -> dict[str, Any] | None:
        if not self._conn:
            return None
        row = self._conn.execute("SELECT v FROM responses WHERE k = ?", (key,)).fetchone()
        return json.loads(row[0]) if row else None

    def put(self, key: str, value: dict[str, Any]) -> None:
        if not self._conn:
            return
        self._conn.execute("INSERT OR REPLACE INTO responses (k, v) VALUES (?, ?)", (key, json.dumps(value)))
        self._conn.commit()

    def close(self) -> None:
        if self._conn:
            self._conn.close()
            self._conn = None


class TokenFactoryClient:
    """OpenAI-compatible Nebius Token Factory client with deterministic caching."""

    def __init__(
        self,
        settings: Settings | None = None,
        cache_path: Path | None = None,
        transport: httpx.AsyncBaseTransport | None = None,
    ):
        self.settings = settings or get_settings()
        self.cache = ResponseCache(cache_path)
        self._client = httpx.AsyncClient(
            base_url=self.settings.base_url,
            timeout=self.settings.request_timeout,
            transport=transport,
        )
        self._sem = asyncio.Semaphore(self.settings.concurrency)
        self.usage = Usage()
        self.calls = 0
        self.cache_hits = 0
        self.models: list[ModelInfo] = []
        self.tool_mode: str = "unknown"
        self._probed: dict[str, str] = {}
        self._headers = {
            "Authorization": f"Bearer {self.settings.api_key}",
            "Content-Type": "application/json",
        }
        self.last_latency_ms: float = 0.0

    @property
    def redacted_headers(self) -> dict[str, str]:
        return {"Authorization": "Bearer <redacted>", "Content-Type": "application/json"}

    async def close(self) -> None:
        await self._client.aclose()
        self.cache.close()

    async def _request(self, method: str, url: str, **kwargs: Any) -> httpx.Response:
        if not self.settings.has_key:
            raise LLMError("NEBIUS_API_KEY is not set")
        last: Exception | None = None
        for attempt in range(4):
            try:
                resp = await self._client.request(method, url, headers=self._headers, **kwargs)
                if resp.status_code in (429, 500, 502, 503, 504):
                    raise httpx.HTTPStatusError("retryable", request=resp.request, response=resp)
                if resp.status_code >= 400:
                    raise LLMError(f"Token Factory HTTP {resp.status_code}: {resp.text[:300]}")
                return resp
            except (httpx.HTTPError, LLMError) as exc:
                last = exc
                if attempt == 3:
                    break
                await asyncio.sleep((0.6 * (2**attempt)) + random.random() * 0.4)
        raise LLMError(f"Token Factory request failed: {last}")

    async def list_models(self) -> list[ModelInfo]:
        resp = await self._request("GET", "/models?verbose=true")
        data = resp.json()
        rows = data.get("data", data if isinstance(data, list) else [])
        self.models = [
            ModelInfo(
                id=str(row.get("id", "")),
                owned_by=str(row.get("owned_by", "")),
                created=int(row.get("created", 0) or 0),
                raw=row,
            )
            for row in rows
            if row.get("id")
        ]
        return self.models

    async def discover(self, include_all_nemotron: bool = True) -> tuple[str, list[ModelInfo]]:
        models = self.models or await self.list_models()
        nemotrons = [m for m in models if m.is_nemotron]
        if not nemotrons:
            raise LLMError("No Nemotron model is served by this Token Factory endpoint")
        available = {m.id: m for m in nemotrons}
        chosen = ""
        if self.settings.model and self.settings.model in available:
            chosen = self.settings.model
        else:
            for pref in CORE_MODEL_PREFERENCES:
                if pref in available:
                    chosen = pref
                    break
        if not chosen:
            def size(m: ModelInfo) -> int:
                digits = "".join(ch for ch in m.id if ch.isdigit())
                return int(digits[:4]) if digits else 9999
            chosen = sorted(nemotrons, key=size)[0].id
        ordered = sorted(nemotrons, key=lambda m: m.id != chosen)
        return chosen, ordered if include_all_nemotron else [available[chosen]]

    async def probe_tool_mode(self, model: str) -> str:
        if model in self._probed:
            return self._probed[model]
        tools = [
            {
                "type": "function",
                "function": {
                    "name": "ping",
                    "description": "Return pong.",
                    "parameters": {"type": "object", "properties": {}, "additionalProperties": False},
                },
            }
        ]
        payload = {
            "model": model,
            "messages": [
                {"role": "system", "content": "You are a connectivity probe. Call the ping tool."},
                {"role": "user", "content": "ping"},
            ],
            "tools": tools,
            "tool_choice": "auto",
            "temperature": 0,
            "max_tokens": 64,
        }
        try:
            resp = await self._post(payload)
            data = resp.json()
            msg = (data.get("choices") or [{}])[0].get("message", {})
            mode = "native" if msg.get("tool_calls") else "react"
        except Exception:
            mode = "react"
        self._probed[model] = mode
        return mode

    async def _post(self, payload: dict[str, Any]) -> httpx.Response:
        key = _key(payload, "raw")
        cached = self.cache.get(key)
        if cached is not None:
            self.cache_hits += 1
            return httpx.Response(200, json=cached)
        async with self._sem:
            started = time.perf_counter()
            resp = await self._request("POST", "/chat/completions", json=payload)
            self.last_latency_ms = (time.perf_counter() - started) * 1000
        self.cache.put(key, resp.json())
        return resp

    async def chat(
        self,
        messages: Iterable[dict[str, Any]],
        model: str,
        tools: list[dict[str, Any]] | None = None,
        tool_mode: str = "auto",
        temperature: float | None = None,
        seed: int | None = None,
        max_tokens: int = 1024,
        system_suffix: str = "",
    ) -> LLMResponse:
        msgs = list(messages)
        if system_suffix:
            msgs = msgs + [{"role": "system", "content": system_suffix}]
        mode = tool_mode
        if mode == "auto":
            mode = await self.probe_tool_mode(model)
        self.tool_mode = mode
        payload: dict[str, Any] = {
            "model": model,
            "messages": msgs,
            "temperature": self.settings.temperature if temperature is None else temperature,
            "max_tokens": max_tokens,
        }
        if seed is not None:
            payload["seed"] = seed
        if tools and mode == "native":
            payload["tools"] = tools
            payload["tool_choice"] = "auto"
        key = _key(payload, mode)
        cached = self.cache.get(key)
        if cached is not None:
            self.cache_hits += 1
            data = cached
            was_cached = True
        else:
            async with self._sem:
                started = time.perf_counter()
                resp = await self._request("POST", "/chat/completions", json=payload)
                self.last_latency_ms = (time.perf_counter() - started) * 1000
            data = resp.json()
            self.cache.put(key, data)
            was_cached = False
        self.calls += 1
        choice = (data.get("choices") or [{}])[0]
        msg = choice.get("message", {}) or {}
        content = msg.get("content") or ""
        calls: list[ToolCall] = []
        for item in msg.get("tool_calls") or []:
            fn = item.get("function", {}) if isinstance(item, dict) else {}
            args = fn.get("arguments", {})
            if isinstance(args, str):
                try:
                    args = json.loads(args)
                except Exception:
                    args = {"value": args}
            calls.append(
                ToolCall(
                    name=str(fn.get("name", "")),
                    args=args if isinstance(args, dict) else {"value": args},
                    call_id=item.get("id"),
                )
            )
        if not calls and mode == "react":
            content, calls = parse_react_response(content)
        u = data.get("usage") or {}
        usage = Usage(
            prompt_tokens=int(u.get("prompt_tokens", 0) or 0),
            completion_tokens=int(u.get("completion_tokens", 0) or 0),
        )
        if not was_cached:
            self.usage.add(usage)
        return LLMResponse(
            content=content,
            tool_calls=calls,
            usage=usage,
            model=str(data.get("model", model)),
            raw=data,
            cached=was_cached,
        )

    async def complete_json(
        self,
        model: str,
        system: str,
        user: str,
        schema_hint: str = "",
        max_tokens: int = 1600,
    ) -> dict[str, Any]:
        suffix = react_protocol_instruction([]) if schema_hint else ""
        resp = await self.chat(
            [
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
            model=model,
            tools=None,
            tool_mode="react",
            temperature=0.1,
            max_tokens=max_tokens,
            system_suffix=suffix,
        )
        obj = first_json_object(resp.content)
        if obj is None:
            raise LLMError("model did not return a JSON object")
        return obj


def estimate_usd(tokens: int) -> float:
    # Transparent, conservative planning estimate; not a billed figure.
    return round(tokens / 1_000_000 * 0.6, 4)
