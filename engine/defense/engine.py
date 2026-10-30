from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from typing import Any

from ..agent.tasks import TaskSpec
from ..detect.dlp import dlp_match
from ..world.canaries import SensitivityVault
from ..world.registry import TOOL_INDEX
from ..world.state import World
from .policy_ir import (
    ArgPredicate,
    Policy,
    any_tool_matches,
    extract_hosts,
    extract_recipients,
    host_matches,
    tool_matches,
)


@dataclass(slots=True)
class Decision:
    decision: str = "allow"
    rule_id: str = "default.allow"
    reason: str = "allowed"


@dataclass(slots=True)
class PolicyContext:
    task_class: str = ""
    task_text: str = ""
    untrusted: bool = False
    trusted_emails: set[str] = field(default_factory=set)
    user_email: str = ""
    allowed_hosts: list[str] = field(default_factory=list)
    vault: SensitivityVault | None = None
    authorized_classes: set[str] = field(default_factory=set)
    tool_counts: dict[str, int] = field(default_factory=dict)
    dlp_enabled: bool = True
    flow_enabled: bool = True


def _resolve_set(alias: str, ctx: PolicyContext) -> set[str]:
    if alias == "$contacts.trusted":
        return {e.lower() for e in ctx.trusted_emails}
    if alias == "$user.email":
        return {ctx.user_email.lower()}
    if alias.startswith("$hosts."):
        return {h.lower() for h in ctx.allowed_hosts}
    return {alias.lower()}


def _values(value: Any) -> list[str]:
    if value is None:
        return []
    if isinstance(value, list):
        return [str(v).lower() for v in value]
    return [str(value).lower()]


def _eval_predicate(pred: ArgPredicate, value: Any, payload: str, ctx: PolicyContext) -> str | None:
    if pred.in_set:
        allowed = _resolve_set(pred.in_set, ctx)
        for v in _values(value):
            if v not in allowed and not any(v.endswith("@" + a) or v == a for a in allowed):
                return f"value {v!r} not in {pred.in_set}"
    if pred.subset_of:
        allowed = _resolve_set(pred.subset_of, ctx)
        for v in _values(value):
            if v not in allowed:
                return f"value {v!r} not subset of {pred.subset_of}"
    if pred.domain_in:
        for v in _values(value):
            if not any(v == d or v.endswith("@" + d) or v.endswith("." + d) for d in pred.domain_in):
                return f"domain not allowed for {v!r}"
    if pred.prefix is not None:
        for v in _values(value):
            if not v.startswith(pred.prefix.lower()):
                return f"value {v!r} does not start with {pred.prefix!r}"
    if pred.regex_not is not None:
        if re.search(pred.regex_not, json.dumps(value, default=str), re.I):
            return f"value matches forbidden pattern {pred.regex_not!r}"
    if pred.not_contains_class:
        if ctx.vault is not None:
            hits = {i.sensitivity for i in dlp_match(ctx.vault, payload)}
            bad = hits & set(pred.not_contains_class)
            if bad:
                return f"payload contains sensitivity class {sorted(bad)}"
    if pred.max_count is not None:
        if isinstance(value, list) and len(value) > pred.max_count:
            return f"count {len(value)} exceeds {pred.max_count}"
        if isinstance(value, (int, float)) and value > pred.max_count:
            return f"value {value} exceeds {pred.max_count}"
    return None


def _flow_check(policy: Policy, tool: str, args: dict[str, Any], ctx: PolicyContext) -> str | None:
    if not ctx.flow_enabled or not ctx.untrusted:
        return None
    for rule in policy.flow_rules:
        if rule.when != "context.untrusted":
            continue
        if not any_tool_matches(rule.sinks, tool):
            continue
        requirement = rule.require.get("recipient_or_host")
        if requirement == "in_user_task_or_trusted_contacts" or requirement is True:
            recipients = extract_recipients(args)
            hosts = extract_hosts(args)
            trusted = {e.lower() for e in ctx.trusted_emails} | {ctx.user_email.lower()}
            task_low = ctx.task_text.lower()
            for r in recipients:
                rr = r.lower()
                if rr not in trusted and rr not in task_low:
                    return f"flow {rule.id}: recipient {r} not trusted or in task"
            for h in hosts:
                if not host_matches(h, ctx.allowed_hosts) and h not in task_low:
                    return f"flow {rule.id}: host {h} not trusted or in task"
            if not recipients and not hosts and tool in {"shell.exec"}:
                return f"flow {rule.id}: untrusted context cannot steer shell"
    return None


def decide(policy: Policy, call: Any, ctx: PolicyContext) -> Decision:
    name = call.name
    args = dict(call.args or {})
    if any_tool_matches(policy.denied_tools, name):
        return Decision(policy.on_violation, "deny.tool", f"{name} is explicitly denied")
    if policy.allowed_tools and not any_tool_matches(policy.allowed_tools, name):
        return Decision(policy.on_violation, "allow.tool", f"{name} is outside the allowed tool set")

    hosts = extract_hosts(args)
    if hosts and policy.allowed_hosts:
        for h in hosts:
            if not host_matches(h, policy.allowed_hosts):
                return Decision(policy.on_violation, "allow.host", f"host {h} is not allowlisted")

    payload = json.dumps(args, ensure_ascii=False, default=str)
    for pattern, fields in policy.arg_rules.items():
        if not tool_matches(pattern, name):
            continue
        for field_name, pred in fields.items():
            value = args.get(field_name)
            violation = _eval_predicate(pred, value, payload, ctx)
            if violation:
                return Decision(policy.on_violation, f"arg.{pattern}.{field_name}", violation)

    violation = _flow_check(policy, name, args, ctx)
    if violation:
        return Decision("block", "flow.untrusted", violation)

    spec = TOOL_INDEX.get(name)
    if ctx.dlp_enabled and spec and spec.egress and ctx.vault is not None:
        hits = dlp_match(ctx.vault, payload)
        unauthorized = [h for h in hits if h.sensitivity not in ctx.authorized_classes]
        if unauthorized:
            cats = sorted({h.sensitivity for h in unauthorized})
            return Decision("block", "dlp.sensitive", f"egress payload contains labelled {', '.join(cats)} data")

    return Decision("allow", "default.allow", "allowed")


class PolicyEnforcer:
    def __init__(self, policy: Policy, dlp_enabled: bool = True, flow_enabled: bool = True):
        self.policy = policy
        self.dlp_enabled = dlp_enabled
        self.flow_enabled = flow_enabled

    def context(self, world: World, task: TaskSpec) -> PolicyContext:
        return PolicyContext(
            task_class=task.task_class,
            task_text=task.text,
            untrusted=world.tainted,
            trusted_emails=set(world.trusted_emails),
            user_email=world.user_email,
            allowed_hosts=list(self.policy.allowed_hosts),
            vault=world.vault,
            tool_counts=dict(world.counters),
            dlp_enabled=self.dlp_enabled,
            flow_enabled=self.flow_enabled,
        )

    def decide(self, world: World, task: TaskSpec, tool: str, args: dict[str, Any]) -> Decision:
        from ..llm.models import ToolCall

        return decide(self.policy, ToolCall(name=tool, args=args), self.context(world, task))
