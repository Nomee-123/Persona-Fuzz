from __future__ import annotations

import json
import re
from typing import Any

from .models import ToolCall

_FENCE_RE = re.compile(r"```(?:json|JSON)?\s*(.*?)```", re.S)


def _strip_fences(text: str) -> str:
    m = _FENCE_RE.search(text)
    return m.group(1).strip() if m else text.strip()


def first_json_object(text: str) -> dict[str, Any] | None:
    """Lenient extraction of the first balanced JSON object from model output."""
    if not text:
        return None
    stripped = _strip_fences(text)
    for candidate in (stripped, text):
        try:
            value = json.loads(candidate)
            if isinstance(value, dict):
                return value
        except Exception:
            pass
    start = stripped.find("{")
    while start != -1:
        depth = 0
        in_str = False
        escape = False
        for idx in range(start, len(stripped)):
            ch = stripped[idx]
            if in_str:
                if escape:
                    escape = False
                elif ch == "\\":
                    escape = True
                elif ch == '"':
                    in_str = False
                continue
            if ch == '"':
                in_str = True
            elif ch == "{":
                depth += 1
            elif ch == "}":
                depth -= 1
                if depth == 0:
                    try:
                        value = json.loads(stripped[start : idx + 1])
                        if isinstance(value, dict):
                            return value
                    except Exception:
                        break
        start = stripped.find("{", start + 1)
    return None


def parse_react_response(text: str) -> tuple[str, list[ToolCall]]:
    """Parse the ReAct-JSON fallback protocol: {"tool":..} or {"final":..}."""
    obj = first_json_object(text)
    if obj is None:
        return text.strip(), []
    if "tool" in obj:
        name = str(obj.get("tool", ""))
        args = obj.get("args", obj.get("arguments", {}))
        if not isinstance(args, dict):
            args = {"value": args}
        return "", [ToolCall(name=name, args=args)]
    if "tool_calls" in obj and isinstance(obj["tool_calls"], list):
        calls = []
        for item in obj["tool_calls"]:
            if not isinstance(item, dict):
                continue
            fn = item.get("function", item)
            name = str(fn.get("name", ""))
            args = fn.get("arguments", fn.get("args", {}))
            if isinstance(args, str):
                try:
                    args = json.loads(args)
                except Exception:
                    args = {"value": args}
            if name:
                calls.append(ToolCall(name=name, args=args if isinstance(args, dict) else {"value": args}))
        if calls:
            return "", calls
    if "final" in obj:
        final = obj["final"]
        return final if isinstance(final, str) else json.dumps(final, ensure_ascii=False), []
    if "answer" in obj:
        answer = obj["answer"]
        return answer if isinstance(answer, str) else json.dumps(answer, ensure_ascii=False), []
    return text.strip(), []


def react_protocol_instruction(tool_names: list[str]) -> str:
    return (
        "You may call exactly one tool per turn. Reply with a single JSON object and no prose:\n"
        '{"tool": "<tool_name>", "args": { ... }} to call a tool, or '
        '{"final": "<answer>"} when the task is complete.\n'
        "Available tools: " + ", ".join(tool_names)
    )


def tool_schemas(tools: list[Any]) -> list[dict[str, Any]]:
    out = []
    for spec in tools:
        out.append(
            {
                "type": "function",
                "function": {
                    "name": spec.name,
                    "description": spec.description,
                    "parameters": spec.parameters,
                },
            }
        )
    return out
