import time
import uuid

from fastapi.testclient import TestClient
from pydantic import ValidationError

from alive.app import create_app
from alive.schemas import EventEnvelope
from tests.conftest import TOKEN


def test_security_and_degraded_startup(client, settings):
    assert client.get("/api/v1/health").json()["status"] == "ok"
    assert client.post("/api/v1/alive/start", headers={"Authorization": ""}).status_code == 401
    assert (
        client.post("/api/v1/alive/start", headers={"Origin": "https://evil.example"}).status_code
        == 403
    )
    caps = client.get("/api/v1/capabilities").json()
    assert caps["pgvector"]["search"] is False
    assert caps["pgvector"]["dimension"] == 384
    assert caps["pi"]["configured"] is False
    assert caps["ollama"]["available"] is False
    assert caps["browser"]["available"] is True
    assert caps["experiments"]["available"] is True
    assert (
        client.post("/api/v1/memories/search", json={"query": "a", "mode": "vector"}).status_code
        == 409
    )
    with TestClient(create_app(settings)) as second:
        assert second.get("/api/v1/health").json()["status"] == "degraded"


def test_capabilities_report_detected_ollama_and_pi_configuration(settings, monkeypatch):
    from tests.conftest import _boot

    settings.alive_ollama_url = "http://ollama.test:11434"
    settings.alive_browser_available = False
    monkeypatch.setattr(
        "alive.ollama.probe_cached",
        lambda url, model="", timeout=1.5: {
            "available": True,
            "url": url,
            "models": ["qwen2.5:0.5b", "all-minilm:l6-v2"],
            "chat_model": "qwen2.5:0.5b",
            "embedding_model": "all-minilm:l6-v2",
            "requested_chat_model": model,
            "reason": "Ollama reachable; local chat model available",
        },
    )
    _boot(settings)
    with TestClient(
        create_app(settings, include_experiments=False),
        headers={"Authorization": f"Bearer {TOKEN}"},
    ) as c:
        caps = c.get("/api/v1/capabilities").json()
    assert caps["ollama"]["available"] is True
    assert caps["ollama"]["chat_model"] == "qwen2.5:0.5b"
    assert caps["pi"]["configured"] is True
    assert caps["pi"]["provider"] == "ollama"
    assert caps["pi"]["model"] == "qwen2.5:0.5b"
    assert caps["browser"]["available"] is False
    assert caps["experiments"]["available"] is False


def test_observation_atomicity_duplicate_memory_and_goals(client):
    client.post("/api/v1/alive/start")
    observation = {
        "event_id": str(uuid.uuid4()),
        "event_type": "browser.dom_changed",
        "payload": {"text": "A green light appeared", "url": "http://local/demo"},
    }
    assert client.post("/api/v1/events", json=observation).json()["duplicate"] is False
    assert client.post("/api/v1/events", json=observation).json()["duplicate"] is True
    memory = client.get("/api/v1/memories").json()
    assert len(memory) == 1 and memory[0]["source_event_id"] == observation["event_id"]
    assert (
        len(client.post("/api/v1/memories/search", json={"query": "green"}).json()["results"]) == 1
    )
    goals = client.get("/api/v1/goals").json()
    assert goals[0]["origin"] == "curiosity"
    goal_id = goals[0]["id"]
    assert (
        client.post(f"/api/v1/goals/{goal_id}/transition", json={"status": "completed"}).status_code
        == 409
    )
    for status in ["accepted", "active", "completed"]:
        assert (
            client.post(f"/api/v1/goals/{goal_id}/transition", json={"status": status}).status_code
            == 200
        )
    assert (
        client.post(f"/api/v1/goals/{goal_id}/transition", json={"status": "active"}).status_code
        == 409
    )
    events = client.get("/api/v1/events").json()
    original = next(e for e in events if e["event_id"] == observation["event_id"])
    memory_event = next(e for e in events if e["event_type"] == "memory.created")
    assert original["correlation_id"] == memory_event["correlation_id"]
    assert memory_event["causation_id"] == original["event_id"]


def test_heartbeat_stop_and_mock_agent(client):
    client.post("/api/v1/alive/start")
    time.sleep(0.25)
    assert client.get("/api/v1/alive").json()["runtime"]["heartbeat_at"]
    run_id = client.post(
        "/api/v1/agents/runs", json={"objective": "Inspect the green light"}
    ).json()["id"]
    for _ in range(30):
        run = client.get("/api/v1/agents/runs/" + run_id).json()
        if run["status"] != "running":
            break
        time.sleep(0.02)
    assert run["status"] == "completed" and "green light" in run["result"]
    assert any(e["event_type"] == "agent.progress" for e in client.get("/api/v1/events").json())
    client.post("/api/v1/alive/stop")
    version = client.get("/api/v1/alive").json()["runtime"]["state_version"]
    time.sleep(0.2)
    assert client.get("/api/v1/alive").json()["runtime"]["state_version"] == version


def test_websocket_auth_history_and_cursors(client):
    client.post("/api/v1/goals", json={"title": "Remember unfinished work"})
    events = client.get("/api/v1/events").json()
    with client.websocket_connect("/api/v1/events/stream") as ws:
        ws.send_json({"token": TOKEN, "after": events[-1]["sequence_number"] - 1})
        received = ws.receive_json()
        assert received["event_id"] == events[-1]["event_id"]


def test_restart_continuity(settings):
    import asyncio

    from alive.db import Database
    from alive.models import Base

    async def schema():
        db = Database(settings.database_url)
        async with db.engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
        await db.engine.dispose()

    asyncio.run(schema())
    with TestClient(create_app(settings), headers={"Authorization": "Bearer " + TOKEN}) as first:
        identity = first.get("/api/v1/alive").json()["identity"]["id"]
        first.post("/api/v1/goals", json={"title": "Survive restart"})
    with TestClient(
        create_app(settings), headers={"Authorization": "Bearer " + TOKEN}
    ) as restarted:
        assert restarted.get("/api/v1/alive").json()["identity"]["id"] == identity
        assert restarted.get("/api/v1/goals").json()[0]["title"] == "Survive restart"
        assert restarted.get("/api/v1/events").json()


def test_envelope_rejects_invalid_schema():
    import pytest

    with pytest.raises(ValidationError):
        EventEnvelope(instance_id=uuid.uuid4(), event_type="bad type", source="test")
