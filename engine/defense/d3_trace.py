from __future__ import annotations

import re
from collections import Counter, defaultdict
from dataclasses import dataclass, field
from typing import Any

from ..config import CANARY_CATEGORIES
from .policy_ir import ArgPredicate, Policy

_HOST_RE = re.compile(r"https?://([^/\s]+)", re.I)


@dataclass(slots=True)
class TraceCall:
    name: str
    args: dict[str, Any]
    trusted_emails: set[str] = field(default_factory=set)
    user_email: str = ""


def _recipients(args: dict[str, Any]) -> list[str]:
    out: list[str] = []
    for key in ("to", "attendees", "with", "recipient"):
        value = args.get(key)
        if isinstance(value, str):
            out.extend([v.strip() for v in value.split(",") if v.strip()])
        elif isinstance(value, list):
            out.extend(str(v) for v in value if str(v).strip())
    return out


def _hosts(args: dict[str, Any]) -> list[str]:
    out = []
    for value in args.values():
        if isinstance(value, str):
            m = _HOST_RE.search(value)
            if m:
                out.append(m.group(1).lower())
    return out


def fit_trace_policy(
    task_class: str,
    traces: list[list[TraceCall]],
    tau: float = 0.9,
    expected_tools: set[str] | None = None,
) -> Policy:
    n = max(1, len(traces))
    tool_counts: Counter[str] = Counter()
    host_counts: Counter[str] = Counter()
    recipients_by_tool: dict[str, list[str]] = defaultdict(list)
    fields_by_tool: dict[str, set[str]] = defaultdict(set)
    for trace in traces:
        seen_tools = {c.name for c in trace}
        tool_counts.update(seen_tools)
        seen_hosts = {h for c in trace for h in _hosts(c.args)}
        host_counts.update(seen_hosts)
        for c in trace:
            for r in _recipients(c.args):
                recipients_by_tool[c.name].append(r)
                fields_by_tool[c.name].update(k for k in ("to", "attendees", "with", "recipient") if k in c.args)
    allowed = sorted(t for t, count in tool_counts.items() if count / n >= tau)
    if not allowed and expected_tools:
        allowed = sorted(expected_tools)
    hosts = sorted(h for h, count in host_counts.items() if count / n >= tau)
    arg_rules: dict[str, dict[str, ArgPredicate]] = {}
    for tool, recips in recipients_by_tool.items():
        if tool not in allowed:
            continue
        if recips:
            arg_rules[tool] = {field: ArgPredicate(subset_of="$contacts.trusted") for field in fields_by_tool[tool]}
    return Policy(
        task_class=task_class,
        allowed_tools=allowed,
        allowed_hosts=hosts,
        denied_tools=[],
        arg_rules=arg_rules,
        flow_rules=[],
        on_violation="block",
    )


def add_d4_guard(policy: Policy) -> Policy:
    from .policy_ir import FlowRule

    data = policy.to_dict()
    rules = [FlowRule.model_validate(r) for r in data.get("flow_rules", [])]
    if not any(r.id == "FR1" for r in rules):
        rules.append(
            FlowRule(
                id="FR1",
                when="context.untrusted",
                sinks=["email.*", "web.*", "sms.*", "chat.send", "calendar.invite", "calendar.share", "file.share", "bank.*", "shell.exec"],
                require={"recipient_or_host": "in_user_task_or_trusted_contacts"},
            )
        )
    return Policy(
        task_class=policy.task_class,
        allowed_tools=list(policy.allowed_tools),
        allowed_hosts=list(policy.allowed_hosts),
        denied_tools=list(policy.denied_tools),
        arg_rules={k: dict(v) for k, v in policy.arg_rules.items()},
        flow_rules=rules,
        on_violation="block",
    )


def default_arg_rules_for_sinks(policy: Policy) -> Policy:
    data = policy.to_dict()
    rules = {k: dict(v) for k, v in policy.arg_rules.items()}
    for tool in policy.allowed_tools:
        if tool in ("email.send", "email.reply", "email.forward", "email.draft", "calendar.create", "calendar.invite", "file.share", "sms.send", "chat.send"):
            rules.setdefault(tool, {})
            rules[tool].setdefault("body", ArgPredicate(not_contains_class=list(CANARY_CATEGORIES)))
    return Policy(
        task_class=policy.task_class,
        allowed_tools=list(policy.allowed_tools),
        allowed_hosts=list(policy.allowed_hosts),
        denied_tools=list(policy.denied_tools),
        arg_rules=rules,
        flow_rules=list(policy.flow_rules),
        on_violation="block",
    )
