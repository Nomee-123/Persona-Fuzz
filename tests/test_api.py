import json

import pytest
from fastapi.testclient import TestClient

from engine.api.app import app

client = TestClient(app)


def test_health_and_summary():
    health = client.get("/api/health")
    assert health.status_code == 200
    assert health.json()["status"] == "ok"
    summary = client.get("/api/run")
    assert summary.status_code == 200
    data = summary.json()
    assert data["run_id"]
    assert "metrics" in data
    assert data["synthetic_fixture"] is True


def test_episodes_and_policy_and_export():
    eps = client.get("/api/episodes", params={"limit": 5})
    assert eps.status_code == 200
    body = eps.json()
    assert body["total"] >= 1
    assert len(body["episodes"]) <= 5
    first = body["episodes"][0]["episode_id"]
    one = client.get(f"/api/episodes/{first}")
    assert one.status_code == 200
    policy = client.get("/api/policy")
    assert policy.status_code == 200
    openshell = client.get("/api/policy/openshell")
    assert openshell.status_code == 200
    assert "version" in openshell.text
    export = client.get("/api/export")
    assert export.status_code == 200
    assert export.headers["content-type"] == "application/zip"


def test_episode_vector_filter():
    filtered = client.get("/api/episodes", params={"vector": "email", "attack": "true", "limit": 3})
    assert filtered.status_code == 200
    body = filtered.json()
    assert body["total"] >= 1
    assert all((row.get("attack") or {}).get("vector") == "email" for row in body["episodes"])


def test_unknown_run_returns_404():
    assert client.get("/api/run", params={"run_id": "definitely-not-a-run"}).status_code == 404
