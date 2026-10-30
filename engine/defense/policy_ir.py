from __future__ import annotations

import json
import re
from fnmatch import fnmatch
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from ..config import CONTRACTS_DIR

try:
    import jsonschema
except Exception:  # pragma: no cover
    jsonschema = None


class ArgPredicate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    in_set: str | None = None
    subset_of: str | None = None
    domain_in: list[str] | None = None
    prefix: str | None = None
    regex_not: str | None = None
    not_contains_class: list[str] | None = None
    max_count: int | None = None

    def dump(self) -> dict[str, Any]:
        return {k: v for k, v in self.model_dump().items() if v is not None}


class FlowRule(BaseModel):
    model_config = ConfigDict(extra="forbid")
    id: str
    when: str = "context.untrusted"
    sinks: list[str] = Field(default_factory=list)
    require: dict[str, str | bool] = Field(default_factory=dict)


class Policy(BaseModel):
    model_config = ConfigDict(extra="forbid")
    version: int = 1
    task_class: str
    allowed_tools: list[str] = Field(default_factory=list)
    allowed_hosts: list[str] = Field(default_factory=list)
    denied_tools: list[str] = Field(default_factory=list)
    arg_rules: dict[str, dict[str, ArgPredicate]] = Field(default_factory=dict)
    flow_rules: list[FlowRule] = Field(default_factory=list)
    on_violation: str = "block"

    def to_dict(self) -> dict[str, Any]:
        data = self.model_dump(exclude_none=True)
        for tool, fields in data.get("arg_rules", {}).items():
            for name, pred in list(fields.items()):
                fields[name] = {k: v for k, v in pred.items() if v is not None}
        return data

    def to_json(self, indent: int = 2) -> str:
        return json.dumps(self.to_dict(), indent=indent, ensure_ascii=False)


def tool_matches(pattern: str, name: str) -> bool:
    if pattern == "*" or pattern == name:
        return True
    if "*" in pattern:
        return fnmatch(name, pattern)
    return False


def any_tool_matches(patterns: list[str], name: str) -> bool:
    return any(tool_matches(p, name) for p in patterns)


def union_policies(policies: list[Policy], task_class: str = "union") -> Policy:
    tools: set[str] = set()
    hosts: set[str] = set()
    denied: set[str] = set()
    arg_rules: dict[str, dict[str, ArgPredicate]] = {}
    flow: list[FlowRule] = []
    seen_flow: set[str] = set()
    for p in policies:
        tools.update(p.allowed_tools)
        hosts.update(p.allowed_hosts)
        denied.update(p.denied_tools)
        for tool, fields in p.arg_rules.items():
            arg_rules.setdefault(tool, {})
            for field, pred in fields.items():
                arg_rules[tool].setdefault(field, pred)
        for rule in p.flow_rules:
            if rule.id not in seen_flow:
                flow.append(rule)
                seen_flow.add(rule.id)
    return Policy(
        version=1,
        task_class=task_class,
        allowed_tools=sorted(tools),
        allowed_hosts=sorted(hosts),
        denied_tools=sorted(denied),
        arg_rules=arg_rules,
        flow_rules=flow,
        on_violation="block",
    )


def validate_policy(data: dict[str, Any] | Policy) -> None:
    if isinstance(data, Policy):
        data = data.to_dict()
    if jsonschema is None:
        Policy.model_validate(data)
        return
    schema = json.loads((CONTRACTS_DIR / "policy.schema.json").read_text(encoding="utf-8"))
    jsonschema.validate(instance=data, schema=schema)


def permissions_reduced(union: Policy, catalog_tools: int, catalog_hosts: int) -> float:
    total = catalog_tools + catalog_hosts
    if total == 0:
        return 0.0
    used = len(union.allowed_tools) + len(union.allowed_hosts)
    return max(0.0, min(1.0, 1.0 - used / total))


def policy_bytes(policy: Policy) -> int:
    return len(policy.to_json(indent=2).encode("utf-8"))


def host_matches(host: str, allowed: list[str]) -> bool:
    host = (host or "").lower()
    if not host:
        return False
    for pattern in allowed:
        p = pattern.lower()
        if p == host:
            return True
        if p.startswith("*.") and host.endswith(p[1:]):
            return True
        if p.startswith(".") and host.endswith(p):
            return True
    return False


def extract_recipients(args: dict[str, Any]) -> list[str]:
    out: list[str] = []
    for key in ("to", "attendees", "with", "recipient", "vpa"):
        value = args.get(key)
        if isinstance(value, str):
            out.extend([v.strip() for v in value.split(",") if v.strip()])
        elif isinstance(value, list):
            out.extend(str(v).strip() for v in value if str(v).strip())
    return out


_HOST_RE = re.compile(r"https?://([^/\s]+)", re.I)


def extract_hosts(args: dict[str, Any]) -> list[str]:
    hosts = []
    for value in args.values():
        if isinstance(value, str):
            m = _HOST_RE.search(value)
            if m:
                hosts.append(m.group(1).lower())
    return hosts
