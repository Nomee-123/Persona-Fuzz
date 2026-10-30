import json
from pathlib import Path

import pytest

from engine.config import CONTRACTS_DIR, FIXTURES_DIR
from engine.contracts import validate_episode, validate_persona, validate_summary

SAMPLE = FIXTURES_DIR / "sample_run"
PERSONAS = FIXTURES_DIR / "personas_fallback.jsonl"


def test_schemas_parse():
    for name in ("run_summary", "episode", "policy", "persona"):
        data = json.loads((CONTRACTS_DIR / f"{name}.schema.json").read_text(encoding="utf-8"))
        assert data["$schema"].startswith("https://json-schema.org/")


@pytest.mark.skipif(not (SAMPLE / "summary.json").exists(), reason="sample fixture not generated")
def test_sample_summary_and_episodes_validate():
    summary = json.loads((SAMPLE / "summary.json").read_text(encoding="utf-8"))
    validate_summary(summary)
    assert summary["synthetic_fixture"] is True
    assert summary["dataset_source"] == "fallback"
    lines = [json.loads(x) for x in (SAMPLE / "episodes.jsonl").read_text(encoding="utf-8").splitlines() if x.strip()]
    assert lines
    for row in lines[:30]:
        validate_episode(row)


@pytest.mark.skipif(not PERSONAS.exists(), reason="fallback personas not generated")
def test_fallback_personas_validate():
    rows = [json.loads(x) for x in PERSONAS.read_text(encoding="utf-8").splitlines() if x.strip()]
    assert len(rows) >= 100
    for row in rows[:10]:
        validate_persona(row)


def test_policy_schema_rejects_unknown_field():
    import jsonschema

    from engine.contracts import schema

    data = {"task_class": "inbox", "allowed_tools": [], "bogus": True}
    with pytest.raises(jsonschema.ValidationError):
        jsonschema.validate(data, schema("policy.schema.json"))
