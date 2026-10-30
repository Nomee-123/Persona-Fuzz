from __future__ import annotations

import json
from functools import lru_cache
from typing import Any

import jsonschema

from .config import CONTRACTS_DIR


@lru_cache(maxsize=8)
def schema(name: str) -> dict[str, Any]:
    return json.loads((CONTRACTS_DIR / name).read_text(encoding="utf-8"))


def validate(instance: Any, schema_name: str) -> None:
    jsonschema.validate(instance=instance, schema=schema(schema_name))


def validate_episode(data: dict[str, Any]) -> None:
    validate(data, "episode.schema.json")


def validate_summary(data: dict[str, Any]) -> None:
    validate(data, "run_summary.schema.json")


def validate_persona(data: dict[str, Any]) -> None:
    validate(data, "persona.schema.json")


def validate_policy(data: dict[str, Any]) -> None:
    validate(data, "policy.schema.json")
