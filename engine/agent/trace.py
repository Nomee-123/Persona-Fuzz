from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class ToolCallTrace(BaseModel):
    model_config = ConfigDict(extra="forbid")
    name: str
    args: dict = Field(default_factory=dict)
    call_id: str | None = None


class Provenance(BaseModel):
    model_config = ConfigDict(extra="forbid")
    trusted: bool = True
    source: str = "agent"


class GatewayTrace(BaseModel):
    model_config = ConfigDict(extra="forbid")
    decision: Literal["allow", "block", "ask"]
    rule_id: str
    reason: str


class Step(BaseModel):
    model_config = ConfigDict(extra="forbid")
    t: int
    role: Literal["system", "user", "assistant", "tool"]
    content: str
    tool_call: ToolCallTrace | None = None
    tool_result: str | None = None
    provenance: Provenance = Field(default_factory=Provenance)
    gateway: GatewayTrace | None = None
    ts: str = ""


class AttackTrace(BaseModel):
    model_config = ConfigDict(extra="forbid")
    vector: Literal["email", "calendar", "web"]
    goal: Literal["exfil_email", "exfil_web", "exfil_invite", "destructive"]
    template_id: str
    split: Literal["train", "eval"]
    adaptive_round: int = 0
    target_category: str = ""
    attacker: str = ""


class LeakTrace(BaseModel):
    model_config = ConfigDict(extra="forbid")
    detected: bool = False
    canary_ids: list[str] = Field(default_factory=list)
    via_tool: str | None = None
    via_host: str | None = None
    step: int | None = None


class UnauthorizedTrace(BaseModel):
    model_config = ConfigDict(extra="forbid")
    detected: bool = False
    tool: str | None = None
    step: int | None = None


class Outcome(BaseModel):
    model_config = ConfigDict(extra="forbid")
    utility_ok: bool = False
    utility_detail: str = ""
    leak: LeakTrace = Field(default_factory=LeakTrace)
    unauthorized_action: UnauthorizedTrace = Field(default_factory=UnauthorizedTrace)
    blocked_count: int = 0
    ask_count: int = 0
    false_blocks: int = 0
    benign_calls: int = 0


class Episode(BaseModel):
    model_config = ConfigDict(extra="forbid")
    episode_id: str
    run_id: str
    persona_id: str
    split: Literal["fit", "eval", "sample"] = "eval"
    condition: Literal["D0", "D1", "D2", "D3", "D4"]
    model: str
    task_class: Literal["inbox", "schedule", "research"]
    task_text: str
    attack: AttackTrace | None = None
    steps: list[Step] = Field(default_factory=list)
    outcome: Outcome = Field(default_factory=Outcome)
    tokens: int = 0
    latency_ms: float = 0.0
    enforcement: Literal["gateway", "openshell"] = "gateway"
    synthetic_fixture: bool = False
    notes: list[str] = Field(default_factory=list)
