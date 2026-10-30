from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass(slots=True)
class ModelInfo:
    id: str
    owned_by: str = ""
    created: int = 0
    raw: dict[str, Any] = field(default_factory=dict)

    @property
    def is_nemotron(self) -> bool:
        return "nemotron" in self.id.lower()

    @property
    def short_name(self) -> str:
        name = self.id.split("/")[-1]
        return name.replace("NVIDIA-", "").replace("nvidia-", "")


@dataclass(slots=True)
class ToolCall:
    name: str
    args: dict[str, Any]
    call_id: str | None = None


@dataclass(slots=True)
class Usage:
    prompt_tokens: int = 0
    completion_tokens: int = 0

    @property
    def total_tokens(self) -> int:
        return self.prompt_tokens + self.completion_tokens

    def add(self, other: "Usage") -> None:
        self.prompt_tokens += other.prompt_tokens
        self.completion_tokens += other.completion_tokens


@dataclass(slots=True)
class LLMResponse:
    content: str
    tool_calls: list[ToolCall] = field(default_factory=list)
    usage: Usage = field(default_factory=Usage)
    model: str = ""
    raw: dict[str, Any] = field(default_factory=dict)
    cached: bool = False

    @property
    def has_tool_calls(self) -> bool:
        return bool(self.tool_calls)
