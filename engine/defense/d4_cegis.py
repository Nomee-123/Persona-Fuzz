from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from statistics import mean
from typing import Any, Awaitable, Callable

from ..agent.trace import Episode
from ..config import CANARY_CATEGORIES
from ..world.registry import TOOLS
from .d3_trace import add_d4_guard, default_arg_rules_for_sinks
from .policy_ir import ArgPredicate, Policy, policy_bytes, union_policies
from .compile_openshell import compile_openshell


@dataclass(slots=True)
class Counterexample:
    episode_id: str
    task_class: str
    tool: str
    args: dict[str, Any]
    kind: str
    canary_ids: list[str] = field(default_factory=list)


@dataclass(slots=True)
class Tightening:
    iteration: int
    task_class: str
    tool: str
    action: str
    detail: str
    reason: str

    def line(self) -> str:
        return f"- iter {self.iteration} | {self.task_class} | {self.action} `{self.tool}` | {self.detail} | {self.reason}"


@dataclass(slots=True)
class D4Result:
    policies: dict[str, Policy]
    union: Policy
    curve: list[dict[str, Any]]
    tightenings: list[Tightening]
    rejected: list[str]


def counterexample_from_episode(episode: Episode) -> Counterexample | None:
    outcome = episode.outcome
    tool = outcome.leak.via_tool if outcome.leak.detected else outcome.unauthorized_action.tool
    if not tool:
        return None
    target_step = outcome.leak.step if outcome.leak.detected else outcome.unauthorized_action.step
    best: tuple[int, dict[str, Any]] | None = None
    for step in episode.steps:
        if step.tool_call and step.tool_call.name == tool:
            if target_step is None or step.t <= target_step:
                best = (step.t, dict(step.tool_call.args))
    if best is None:
        return None
    return Counterexample(
        episode_id=episode.episode_id,
        task_class=episode.task_class,
        tool=tool,
        args=best[1],
        kind="leak" if outcome.leak.detected else "unauthorized",
        canary_ids=list(outcome.leak.canary_ids),
    )


def _recipient_fields(args: dict[str, Any]) -> list[str]:
    return [k for k in ("to", "attendees", "with", "recipient") if args.get(k)]


def _host_values(args: dict[str, Any]) -> list[str]:
    import re

    vals = []
    for value in args.values():
        if isinstance(value, str):
            m = re.search(r"https?://([^/\s]+)", value)
            if m:
                vals.append(m.group(1).lower())
    return vals


def tighten_policy(
    policy: Policy,
    counterexamples: list[Counterexample],
    benign_tools: set[str],
    iteration: int,
) -> tuple[Policy, list[Tightening]]:
    data = policy.to_dict()
    allowed = set(data.get("allowed_tools", []))
    denied = set(data.get("denied_tools", []))
    arg_rules: dict[str, dict[str, ArgPredicate]] = {
        tool: {field: ArgPredicate.model_validate(pred) for field, pred in fields.items()}
        for tool, fields in data.get("arg_rules", {}).items()
    }
    notes: list[Tightening] = []
    for ce in counterexamples:
        if ce.tool not in allowed:
            continue
        needed = ce.tool in benign_tools
        if not needed or ce.tool.startswith("bank.") or ce.tool in {"web.post", "shell.exec", "upi.pay"}:
            allowed.discard(ce.tool)
            denied.add(ce.tool)
            notes.append(
                Tightening(iteration, ce.task_class, ce.tool, "deny", "tool not needed by any benign fit trace", f"{ce.kind} in {ce.episode_id}")
            )
            continue
        rules = arg_rules.setdefault(ce.tool, {})
        changed = False
        fields = _recipient_fields(ce.args)
        for field_name in fields:
            rules[field_name] = ArgPredicate(subset_of="$contacts.trusted")
            changed = True
        hosts = _host_values(ce.args)
        if hosts:
            if ce.tool.startswith("web."):
                rules["url"] = ArgPredicate(domain_in=sorted(set(policy.allowed_hosts)))
            changed = True
        if any(k in ce.args for k in ("body", "content", "note")):
            if "body" in ce.args:
                rules["body"] = ArgPredicate(not_contains_class=list(CANARY_CATEGORIES))
                changed = True
        if not changed:
            allowed.discard(ce.tool)
            denied.add(ce.tool)
            notes.append(
                Tightening(iteration, ce.task_class, ce.tool, "deny", "no separating predicate available", f"{ce.kind} in {ce.episode_id}")
            )
        else:
            notes.append(
                Tightening(
                    iteration,
                    ce.task_class,
                    ce.tool,
                    "narrow",
                    "added recipient/host/body predicate" + (f"; canaries {', '.join(ce.canary_ids)}" if ce.canary_ids else ""),
                    f"{ce.kind} in {ce.episode_id}",
                )
            )
    new = Policy(
        task_class=policy.task_class,
        allowed_tools=sorted(allowed),
        allowed_hosts=list(policy.allowed_hosts),
        denied_tools=sorted(denied),
        arg_rules=arg_rules,
        flow_rules=list(policy.flow_rules),
        on_violation="block",
    )
    return new, notes


def prepare_d4_policies(policies: dict[str, Policy]) -> dict[str, Policy]:
    out = {}
    for task_class, policy in policies.items():
        guarded = add_d4_guard(policy)
        out[task_class] = default_arg_rules_for_sinks(guarded)
    return out


async def run_cegis(
    policies: dict[str, Policy],
    benign_tools: dict[str, set[str]],
    baseline_utility: float,
    run_train_attacks: Callable[[dict[str, Policy]], Awaitable[list[Episode]]],
    run_benign: Callable[[dict[str, Policy]], Awaitable[list[Episode]]],
    run_heldout_attacks: Callable[[dict[str, Policy]], Awaitable[list[Episode]]] | None = None,
    epsilon: float = 0.02,
    max_iters: int = 8,
    on_point: Callable[[dict[str, Any]], None] | None = None,
) -> D4Result:
    current = prepare_d4_policies(policies)
    tightenings: list[Tightening] = []
    rejected: list[str] = []
    curve: list[dict[str, Any]] = []

    def rate(episodes: list[Episode]) -> float:
        return (sum(1 for e in episodes if e.outcome.leak.detected or e.outcome.unauthorized_action.detected) / len(episodes)) if episodes else 0.0

    def util(episodes: list[Episode]) -> float:
        return (sum(1 for e in episodes if e.outcome.utility_ok) / len(episodes)) if episodes else 0.0

    initial_attacks = await run_train_attacks(current)
    initial_benign = await run_benign(current)
    held = await run_heldout_attacks(current) if run_heldout_attacks else []
    point0 = {
        "iter": 0,
        "train_leak": rate(initial_attacks),
        "heldout_leak": rate(held),
        "utility": util(initial_benign),
        "policy_bytes": sum(policy_bytes(p) for p in current.values()),
    }
    curve.append(point0)
    if on_point:
        on_point(point0)
    utility = point0["utility"]
    for iteration in range(1, max_iters + 1):
        attacks = initial_attacks if iteration == 1 else await run_train_attacks(current)
        ces = [ce for ep in attacks if (ce := counterexample_from_episode(ep)) is not None]
        if not ces:
            break
        proposed: dict[str, Policy] = {}
        notes: list[Tightening] = []
        for task_class, policy in current.items():
            subset = [ce for ce in ces if ce.task_class == task_class]
            if subset:
                new_policy, n = tighten_policy(policy, subset, benign_tools.get(task_class, set()), iteration)
                proposed[task_class] = new_policy
                notes.extend(n)
            else:
                proposed[task_class] = policy
        if all(proposed[k].to_dict() == current[k].to_dict() for k in proposed):
            break
        benign = await run_benign(proposed)
        proposed_utility = util(benign)
        if proposed_utility < baseline_utility - epsilon:
            rejected.append(
                f"iteration {iteration}: rejected tightening because utility {proposed_utility:.2f} < baseline {baseline_utility:.2f} - {epsilon:.2f}"
            )
            break
        current = proposed
        tightenings.extend(notes)
        utility = proposed_utility
        attacks = await run_train_attacks(current)
        if run_heldout_attacks:
            held = await run_heldout_attacks(current)
        else:
            held = []
        point = {
            "iter": iteration,
            "train_leak": rate(attacks),
            "heldout_leak": rate(held),
            "utility": utility,
            "policy_bytes": sum(policy_bytes(p) for p in current.values()),
        }
        curve.append(point)
        if on_point:
            on_point(point)
        if rate(attacks) == 0:
            break
    union = union_policies(list(current.values()))
    return D4Result(policies=current, union=union, curve=curve, tightenings=tightenings, rejected=rejected)


def write_policy_bundle(
    run_dir: Path,
    policies: dict[str, Policy],
    union: Policy,
    tightenings: list[Tightening],
    rejected: list[str],
) -> None:
    run_dir.mkdir(parents=True, exist_ok=True)
    bundle = {
        "version": 1,
        "union": union.to_dict(),
        "by_task_class": {k: v.to_dict() for k, v in policies.items()},
        "changelog": [
            {"iteration": t.iteration, "task_class": t.task_class, "tool": t.tool, "action": t.action, "detail": t.detail, "reason": t.reason}
            for t in tightenings
        ],
        "rejected": rejected,
        "catalog": {"tools": len(TOOLS)},
    }
    (run_dir / "policy.json").write_text(json.dumps(bundle, indent=2), encoding="utf-8")
    (run_dir / "policy.openshell.yaml").write_text(compile_openshell(union), encoding="utf-8")
    lines = ["# Learned least-privilege policy", "", f"Union allowed tools: {len(union.allowed_tools)} / {len(TOOLS)}", ""]
    if tightenings:
        lines.append("## CEGIS tightenings")
        lines.extend(t.line() for t in tightenings)
    else:
        lines.append("## CEGIS tightenings")
        lines.append("- no counterexamples required tightening on the fit set")
    if rejected:
        lines.append("")
        lines.append("## Rejected tightenings")
        lines.extend(f"- {r}" for r in rejected)
    lines.append("")
    lines.append("## Known limits")
    lines.append("- Pattern DLP can miss rephrased or re-encoded secrets; held-out obfuscation templates measure this.")
    lines.append("- Policies are learned on fit personas and train templates; held-out results are the headline.")
    (run_dir / "policy.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
