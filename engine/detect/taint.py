from __future__ import annotations

from ..world.tools import ToolResult


def is_untrusted(result: ToolResult) -> bool:
    return not result.trusted
