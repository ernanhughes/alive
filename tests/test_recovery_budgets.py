import asyncio

import pytest
from fastapi.testclient import TestClient

from alive.app import create_app
from alive.cognitive_models import CognitiveControl, CognitiveObservation, Investigation
from alive.db import Database
from alive.models import Base, Event, Goal, now, uid
from tests.conftest import TOKEN
from tests.test_cognition import completed, observe, start


def test_interrupted_investigation_recovery_preserves_budget_and_identity(settings):
    async def schema():
        db = Database(settings.database_url)
        async with db.engine.begin() as connection:
            await connection.run_sync(Base.metadata.create_all)
        await db.engine.dispose()

    asyncio.run(schema())
    headers = {"Authorization": "Bearer " + TOKEN}
    with TestClient(create_app(settings), headers=headers) as first:
        identity = first.get("/api/v1/alive").json()["identity"]["id"]

        async def seed():
            k = first.app.state.kernel
            from sqlalchemy import select

            async with k.lock, k.db.sessions.begin() as session:
                event = await session.scalar(select(Event).limit(1))
                goal = Goal(
                    id=uid(), instance_id=identity, title="Interrupted controlled investigation"
                )
                session.add(goal)
                observation = CognitiveObservation(
                    id=uid(),
                    instance_id=identity,
                    source_event_id=event.id,
                    fingerprint="recovery-fixture",
                    content="controlled fixture",
                    provenance={},
                    attention={},
                    status="SELECTED",
                )
                session.add(observation)
                await session.flush()
                run = Investigation(
                    id=uid(),
                    instance_id=identity,
                    observation_id=observation.id,
                    goal_id=goal.id,
                    state="INVESTIGATING",
                    snapshot={"schema_version": 1, "source_event_ids": [event.id]},
                    history=[{"state": "INVESTIGATING", "at": now().isoformat()}],
                    budget={"calls": 4, "tokens": 50000, "tools": 3},
                    usage={"calls": 1, "tokens": 3000, "tools": 1},
                )
                session.add(run)
                control = await session.get(CognitiveControl, identity)
                control.mode = "running"
                control.reserved = {"calls": 4, "tokens": 50000, "tools": 3}
                return run.id

        run_id = first.portal.call(seed)
    with TestClient(create_app(settings), headers=headers) as second:
        assert second.get("/api/v1/alive").json()["identity"]["id"] == identity
        run = second.get("/api/v1/cognition/investigations/" + run_id).json()
        assert run["state"] == "CANCELLED" and len(run["experiences"]) == 1
        assert run["experiences"][0]["data"]["truncated"] is True
        control = second.get("/api/v1/cognition").json()["control"]
        assert control["mode"] == "paused"
        assert control["reserved"]["tokens"] == 0
        assert control["spent"]["session_tokens"] == 3000
        assert control["spent"]["experiment_calls"] == 1
        assert run["invocations"] == []


def test_invalid_model_response_never_executes(client, monkeypatch):
    from alive.providers import Generation, MetaProvider

    async def discover(*args):
        return {"status": "available", "models": ["muse-spark-1.3"]}

    async def invalid(*args, **kwargs):
        return Generation('{"malformed":true}', {"total_tokens": 20})

    monkeypatch.setattr(MetaProvider, "discover", discover)
    monkeypatch.setattr(MetaProvider, "structured", invalid)
    assert (
        client.post(
            "/api/v1/cognition/control", json={"command": "start", "provider": "meta"}
        ).status_code
        == 200
    )
    observe(client)
    run = completed(client)
    assert run["state"] == "FAILED" and run["error"] == "ValidationError"
    assert run["actions"] == [] and run["invocations"][0]["status"] == "failed"
    assert run["invocations"][0]["usage"]["total_tokens"] == 20
    assert run["usage"]["tokens"] > 20  # pessimistic charge retained after invalid result


def test_tool_and_per_request_budget_enforced_before_calls(client):
    start(client, tool_calls=0)
    observe(client)
    run = completed(client)
    assert run["state"] == "FAILED" and run["usage"]["calls"] == 0
    assert "Tool budget" in run["error"]


def test_request_budget_enforced_before_inference(client):
    start(client, request_tokens=512)
    observe(client)
    run = completed(client)
    assert run["state"] == "FAILED" and run["usage"]["calls"] == 0
    assert run["invocations"] == []
    assert "Per-request" in run["error"]


def test_provider_timeout_is_bounded_and_recorded(client, monkeypatch):
    from alive.providers import MetaProvider

    async def discover(*args):
        return {"status": "available", "models": ["muse-spark-1.3"]}

    async def slow(*args, **kwargs):
        await asyncio.sleep(10)

    monkeypatch.setattr(MetaProvider, "discover", discover)
    monkeypatch.setattr(MetaProvider, "structured", slow)
    client.post("/api/v1/cognition/configuration", json={"wall_seconds": 1})
    client.post("/api/v1/cognition/control", json={"command": "start", "provider": "meta"})
    observe(client)
    run = completed(client)
    assert run["state"] == "FAILED" and run["error"] == "TimeoutError"
    assert run["invocations"][0]["status"] == "cancelled"
    assert run["experiences"][0]["data"]["truncated"] is True


def test_persistent_benchmark_budget_and_paid_opt_in(tmp_path):
    from scripts.benchmark import BenchmarkBudget, run_benchmark

    budget = BenchmarkBudget(tmp_path / "ledger.json", 2, 100)
    call = budget.reserve(60, "observer", "fixed")
    budget.settle(call, {"total_tokens": 20}, 10, {"summary": "actual fixture output"})
    recovered = BenchmarkBudget(tmp_path / "ledger.json", 2, 100)
    assert recovered.data["tokens"] == 20
    recovered.reserve(70, "proposer", "fixed")
    with pytest.raises(RuntimeError, match="exhausted"):
        recovered.reserve(1, "critic", "fixed")
    with pytest.raises(ValueError, match="opt-in"):
        asyncio.run(run_benchmark(provider="meta"))
