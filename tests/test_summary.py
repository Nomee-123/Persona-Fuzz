import json

import pytest

from engine.agent.trace import Episode
from engine.config import FIXTURES_DIR
from engine.contracts import validate_summary
from engine.defense.d2_llm_policy import fallback_policy
from engine.defense.policy_ir import union_policies
from engine.metrics.summarize import build_summary
from engine.world.persona_loader import fallback_personas

SAMPLE = FIXTURES_DIR / "sample_run"


@pytest.mark.skipif(not (SAMPLE / "episodes.jsonl").exists(), reason="sample fixture not generated")
def test_fixture_summary_recomputes_from_episodes():
    episodes = [Episode.model_validate(json.loads(x)) for x in (SAMPLE / "episodes.jsonl").read_text(encoding="utf-8").splitlines() if x.strip()]
    persona = fallback_personas(1, seed=1)[0]
    policy = fallback_policy(__import__("engine.agent.tasks", fromlist=["build_task"]).build_task(persona, "inbox"))
    summary = build_summary(
        run_id="recompute",
        config={
            "dataset": "fixture",
            "n_eval": 10,
            "n_fit": 8,
            "agent_label": "Persona-Fuzz Agent · Gateway",
            "model": "offline/mock",
            "attack_types": ["email", "calendar", "web"],
            "canary_categories": ["bank", "medical", "personal", "financial", "identity"],
            "compute_label": "Offline deterministic mock (fixture)",
            "region": "local",
            "enforcement": "gateway",
        },
        episodes=episodes,
        union=policy,
        policies={"inbox": policy},
        openshell_yaml="version: 1\n",
        curve=[{"iter": 0, "train_leak": 1.0, "heldout_leak": 1.0, "utility": 1.0, "policy_bytes": 0}],
        per_model=[],
        synthetic_fixture=True,
        dataset_source="fallback",
        started_at="2026-10-30T00:00:00+00:00",
        finished_at="2026-10-30T00:01:00+00:00",
        example_trace_ids={"persona_id": "p", "episode_id": episodes[0].episode_id},
    )
    validate_summary(summary)
    headline = [e for e in episodes if e.episode_id.startswith("headline-") and e.condition == "D0"]
    assert summary["metrics"]["total_runs"] == len(headline)
    assert summary["metrics"]["leaks_before"] == sum(1 for e in headline if e.outcome.leak.detected)
    assert 0 <= summary["metrics"]["improvement"] <= 1
    assert summary["synthetic_fixture"] is True


def test_summary_flags_offline_fixture_and_low_potency():
    persona = fallback_personas(1, seed=2)[0]
    from engine.agent.tasks import build_task

    policy = fallback_policy(build_task(persona, "inbox"))
    summary = build_summary(
        run_id="empty",
        config={
            "dataset": "fixture",
            "n_eval": 0,
            "n_fit": 0,
            "agent_label": "Persona-Fuzz Agent · Gateway",
            "model": "offline/mock",
            "attack_types": [],
            "canary_categories": [],
            "compute_label": "Offline deterministic mock (fixture)",
            "region": "local",
            "enforcement": "gateway",
        },
        episodes=[],
        union=union_policies([policy]),
        policies={"inbox": policy},
        openshell_yaml="version: 1\n",
        curve=[],
        per_model=[],
        synthetic_fixture=True,
        dataset_source="fallback",
        started_at="2026-10-30T00:00:00+00:00",
        finished_at="2026-10-30T00:01:00+00:00",
        example_trace_ids={"persona_id": "", "episode_id": ""},
    )
    validate_summary(summary)
    assert summary["metrics"]["attack_potency_low"] is True
    assert any(n.startswith("synthetic_fixture") for n in summary["notes"])
    assert any(n.startswith("attack_potency_low") for n in summary["notes"])
