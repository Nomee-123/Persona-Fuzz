from __future__ import annotations

from ..agent.prompts import D1_SYSTEM_SUFFIX, SPOTLIGHT_PREFIX, SPOTLIGHT_SUFFIX


def wrap_tool_output(content: str) -> str:
    return f"{SPOTLIGHT_PREFIX}{content}{SPOTLIGHT_SUFFIX}"


def d1_system_suffix() -> str:
    return D1_SYSTEM_SUFFIX
