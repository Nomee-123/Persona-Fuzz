import pytest

from engine.agent.loop import AgentLoop
from engine.agent.tasks import build_task
from engine.attacks.injector import inject_attack
from engine.attacks.templates import build_attack
from engine.defense.d2_llm_policy import fallback_policy
from engine.defense.d4_cegis import prepare_d4_policies
from engine.defense.engine import PolicyEnforcer
from engine.llm.mock_backend import MockBackend
from engine.world.lifegen import build_life
from engine.world.persona_loader import fallback_personas

VECTOR_TASK = {"email": "inbox", "calendar": "schedule", "web": "research"}


async def run_case(vector: str, condition: str):
    persona = fallback_personas(3, seed=11)[1]
    world = build_life(persona, 11)
    task = build_task(persona, VECTOR_TASK[vector], world)
    attack = build_attack(persona, vector, "eval", "bank", 11, index=0)
    inject_attack(world, attack)
    policy = fallback_policy(task)
    if condition == "D4":
        policy = prepare_d4_policies({task.task_class: policy})[task.task_class]
    enforcer = None if condition == "D0" else PolicyEnforcer(policy, dlp_enabled=condition == "D4", flow_enabled=True)
    loop = AgentLoop(MockBackend("gullible"), "mock/test", max_steps=14)
    result = await loop.run(
        world,
        task,
        condition,
        "test-run",
        f"test-{vector}-{condition}",
        attack=attack.trace(),
        enforcer=enforcer,
    )
    return result.episode


@pytest.mark.parametrize("vector", ["email", "calendar", "web"])
async def test_d0_leaks_and_keeps_utility(vector):
    ep = await run_case(vector, "D0")
    assert ep.outcome.utility_ok, ep.outcome.utility_detail
    assert ep.outcome.leak.detected
    assert ep.outcome.leak.canary_ids


@pytest.mark.parametrize("vector", ["email", "calendar", "web"])
async def test_d4_blocks_leak_and_keeps_utility(vector):
    ep = await run_case(vector, "D4")
    assert ep.outcome.utility_ok, ep.outcome.utility_detail
    assert not ep.outcome.leak.detected
    assert ep.outcome.blocked_count >= 1


async def test_d4_blocks_all_attack_vectors_when_combined():
    for vector in VECTOR_TASK:
        ep = await run_case(vector, "D4")
        assert not ep.outcome.leak.detected
