import asyncio
from contextlib import asynccontextmanager

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.ext.asyncio import AsyncSession

from alive.app import create_app
from alive.cognitive_models import (
    CognitiveControl,
    CognitiveObservation,
    Investigation,
    ModelInvocation,
)
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


# --- F-002: a cancellation must never leave a ModelInvocation `reserved` ---------------------
# ALIVE-AUDIT-01 F-002: the reservation commits inside one transaction and the handler that
# settles a cancelled invocation only started after it, so a cancel delivered while that
# transaction exited stranded the row. These tests deliver a cancel at a chosen await (not by
# wall-clock timing) and assert the invariant: every invocation of a terminal run is settled,
# and the conservative charge for it is retained.


class Barrier:
    """Deliver a cancellation to the cognition worker at a precise point of one invocation."""

    def __init__(self, client, monkeypatch, *points):
        self.cog = client.app.state.cognition
        self.points, self.fired = set(points), []
        self.reserved, self.call_id = False, None
        barrier = self
        k = client.app.state.kernel
        original_add, original_begin = k.add_event, k.db.sessions.begin
        original_get = AsyncSession.get

        def cancel():
            barrier.cog.worker.cancel()

        def add_event(*args, **kwargs):
            result = original_add(*args, **kwargs)
            if len(args) > 1 and args[1] == "cognition.model_reserved":
                barrier.reserved, barrier.call_id = True, args[2]["invocation_id"]
                if (
                    "reservation_event" in barrier.points
                    and "reservation_event" not in barrier.fired
                ):
                    barrier.fired.append("reservation_event")
                    cancel()  # lands at the next await: the transaction's commit
            return result

        @asynccontextmanager
        async def begin():
            was_reserved = barrier.reserved
            async with original_begin() as session:
                yield session
            if (
                not was_reserved
                and barrier.reserved
                and "commit_exit" in barrier.points
                and "commit_exit" not in barrier.fired
                and asyncio.current_task() is barrier.cog.worker
            ):
                barrier.fired.append("commit_exit")
                cancel()
                await asyncio.sleep(0)  # the cancel is raised here, after the commit

        async def get(session, entity, ident, *args, **kwargs):
            if (
                entity is ModelInvocation
                and ident == barrier.call_id
                and "settlement" in barrier.points
                and "settlement" not in barrier.fired
            ):
                barrier.fired.append("settlement")
                cancel()
                await asyncio.sleep(0)  # raised here if this is the worker task itself
            return await original_get(session, entity, ident, *args, **kwargs)

        monkeypatch.setattr(k, "add_event", add_event)
        monkeypatch.setattr(k.db.sessions, "begin", begin)
        monkeypatch.setattr(AsyncSession, "get", get)

    def cancel_now(self):
        self.fired.append("dispatch")
        self.cog.worker.cancel()


def meta_available(monkeypatch):
    from alive.providers import MetaProvider

    async def discover(*args):
        return {"status": "available", "models": ["muse-spark-1.3"]}

    monkeypatch.setattr(MetaProvider, "discover", discover)
    return MetaProvider


def assert_every_invocation_settled(run, *, expect=None):
    """The invariant. Charged tokens equal the reservation unless the call validated."""
    terminal = {"COMPLETED", "ABSTAINED", "FAILED", "CANCELLED"}
    assert run["state"] in terminal, run["state"]
    statuses = [call["status"] for call in run["invocations"]]
    assert "reserved" not in statuses, statuses
    for call in run["invocations"]:
        if call["status"] != "validated":
            assert call["usage"]["charged_tokens"] == call["reserved_tokens"], call["usage"]
    assert run["usage"]["calls"] == len(run["invocations"]), run["usage"]
    if expect is not None:
        assert statuses == expect, statuses


def test_cancel_requested_during_the_reservation_event_never_strands_a_reserved_row(
    client, monkeypatch
):
    # Delivered before the reservation transaction commits: the outcome may be either "committed"
    # or "rolled back", and both must be consistent (no row and no charge, or a settled row and a
    # retained charge).
    barrier = Barrier(client, monkeypatch, "reservation_event")
    start(client)
    observe(client)
    run = completed(client)
    assert barrier.fired == ["reservation_event"]
    assert_every_invocation_settled(run)


def test_cancel_at_reservation_commit_exit_settles_the_invocation(client, monkeypatch):
    barrier = Barrier(client, monkeypatch, "commit_exit")
    start(client)
    observe(client)
    run = completed(client)
    assert barrier.fired == ["commit_exit"]  # the audit's F-002 window
    assert_every_invocation_settled(run, expect=["cancelled"])
    assert run["usage"]["tokens"] >= run["invocations"][0]["reserved_tokens"]


def test_cancel_during_provider_dispatch_settles_the_invocation(client, monkeypatch):
    MetaProvider = meta_available(monkeypatch)
    barrier = Barrier(client, monkeypatch)

    async def inflight(*args, **kwargs):
        barrier.cancel_now()
        await asyncio.sleep(0)

    monkeypatch.setattr(MetaProvider, "structured", inflight)
    client.post("/api/v1/cognition/control", json={"command": "start", "provider": "meta"})
    observe(client)
    run = completed(client)
    assert barrier.fired == ["dispatch"]
    assert_every_invocation_settled(run, expect=["cancelled"])


def test_response_received_then_cancel_at_settlement_still_records_the_failure(client, monkeypatch):
    from alive.providers import Generation

    MetaProvider = meta_available(monkeypatch)
    barrier = Barrier(client, monkeypatch, "settlement")

    async def invalid(*args, **kwargs):
        return Generation('{"malformed":true}', {"total_tokens": 20})

    monkeypatch.setattr(MetaProvider, "structured", invalid)
    client.post("/api/v1/cognition/control", json={"command": "start", "provider": "meta"})
    observe(client)
    run = completed(client)
    assert barrier.fired == ["settlement"]
    assert_every_invocation_settled(run, expect=["failed"])
    call = run["invocations"][0]
    assert call["output_json"]["validation"] == "rejected"  # the rejection is still recorded
    assert call["usage"]["total_tokens"] == 20  # and so is the provider's reported usage


def test_cancel_at_the_success_settlement_still_settles_the_invocation(client, monkeypatch):
    barrier = Barrier(client, monkeypatch, "settlement")  # fixture provider -> valid output
    start(client)
    observe(client)
    run = completed(client)
    assert barrier.fired == ["settlement"]
    assert_every_invocation_settled(run)
    assert run["invocations"][0]["status"] in {"cancelled", "validated"}


def test_a_cancel_after_a_successful_settlement_never_rewrites_the_validated_call(
    client, monkeypatch
):
    cog = client.app.state.cognition
    original_message, fired = cog.message, []

    async def message(run_id, sender, *args, **kwargs):
        if sender == "observer" and not fired:
            fired.append(sender)
            cog.worker.cancel()
            await asyncio.sleep(0)  # raised here: after the call validated, before the message
        return await original_message(run_id, sender, *args, **kwargs)

    monkeypatch.setattr(cog, "message", message)
    start(client)
    observe(client)
    run = completed(client)
    assert fired == ["observer"] and run["state"] == "CANCELLED"
    call = run["invocations"][0]
    assert call["status"] == "validated"  # the outer handler saw a settled row and left it alone
    assert call["output_json"] and call["error"] is None
    assert call["usage"]["charged_tokens"] <= call["reserved_tokens"]


def test_a_second_cancel_during_settlement_cannot_strand_the_invocation(client, monkeypatch):
    barrier = Barrier(client, monkeypatch, "commit_exit", "settlement")
    start(client)
    observe(client)
    run = completed(client)
    assert barrier.fired == ["commit_exit", "settlement"]
    assert_every_invocation_settled(run, expect=["cancelled"])


def test_provider_error_still_records_failed_with_the_conservative_charge(client, monkeypatch):
    from alive.providers import ProviderError

    MetaProvider = meta_available(monkeypatch)

    async def refused(*args, **kwargs):
        raise ProviderError("server_error", status=500)

    monkeypatch.setattr(MetaProvider, "structured", refused)
    client.post("/api/v1/cognition/control", json={"command": "start", "provider": "meta"})
    observe(client)
    run = completed(client)
    assert run["state"] == "FAILED"
    assert_every_invocation_settled(run, expect=["failed"])
    assert "HTTP 500" in run["invocations"][0]["error"]


def seed_run(client, *, status, usage=None):
    """A non-terminal investigation with one invocation in `status` (no worker involved)."""

    async def seed():
        k = client.app.state.kernel
        from sqlalchemy import select

        identity = k.instance_id
        async with k.lock, k.db.sessions.begin() as session:
            event = await session.scalar(select(Event).limit(1))
            goal = Goal(id=uid(), instance_id=identity, title="Seeded terminal-reconciliation run")
            session.add(goal)
            observation = CognitiveObservation(
                id=uid(),
                instance_id=identity,
                source_event_id=event.id,
                fingerprint="f002-" + uid(),
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
                usage={"calls": 1, "tokens": 1000, "tools": 0},
            )
            session.add(run)
            await session.flush()
            session.add(
                ModelInvocation(
                    id=uid(),
                    investigation_id=run.id,
                    role="observer",
                    provider="meta",
                    model="muse-spark-1.3",
                    status=status,
                    input_json={},
                    usage=usage or {},
                    reserved_tokens=1000,
                )
            )
            return run.id

    return client.portal.call(seed)


def finish_run(client, run_id, target="FAILED"):
    cog = client.app.state.cognition

    async def finish():
        await cog.finish(run_id, target, {"effect": "none", "reason": "test"}, error="test")

    client.portal.call(finish)
    return client.get("/api/v1/cognition/investigations/" + run_id).json()


def test_finish_reconciles_a_reserved_invocation_as_interrupted(client):
    # Safety net: whatever path made the run terminal, a still-reserved row is settled and its
    # conservative charge is retained. "interrupted" because completion is genuinely unknown.
    run = finish_run(client, seed_run(client, status="reserved"))
    assert run["state"] == "FAILED"
    call = run["invocations"][0]
    assert call["status"] == "interrupted"
    assert call["usage"]["charged_tokens"] == call["reserved_tokens"] == 1000
    assert "terminal" in call["error"]
    assert run["usage"]["tokens"] == 1000  # never refunded


@pytest.mark.parametrize("status", ["validated", "failed", "cancelled", "interrupted"])
def test_finish_never_rewrites_an_invocation_that_is_already_settled(client, status):
    usage = {"total_tokens": 7, "charged_tokens": 7}
    run = finish_run(client, seed_run(client, status=status, usage=usage))
    call = run["invocations"][0]
    assert call["status"] == status and call["usage"] == usage and call["error"] is None


def test_timeout_in_durable_reservation_exit_settles_invocation(client, monkeypatch):
    """ALIVE-AUDIT-01's F-002 reproduction, promoted from the audit.

    Unlike the barrier tests it uses the real wall-clock timeout, so the run ends FAILED through
    `asyncio.timeout` rather than CANCELLED. A context wrapper delays the reservation transaction's
    exit until the one-second timeout has fired; the provider must never be entered.
    """
    from alive.providers import MetaProvider

    async def discover(*args):
        return {"status": "available", "models": ["muse-spark-1.3"]}

    async def forbidden(*args, **kwargs):
        raise AssertionError("Provider must not be entered in this scheduling case")

    monkeypatch.setattr(MetaProvider, "discover", discover)
    monkeypatch.setattr(MetaProvider, "structured", forbidden)
    k = client.app.state.kernel
    original_begin, original_add = k.db.sessions.begin, k.add_event
    marker = {"reserved": False, "delayed": False}

    def add_event(*args, **kwargs):
        result = original_add(*args, **kwargs)
        if len(args) > 1 and args[1] == "cognition.model_reserved":
            marker["reserved"] = True
        return result

    @asynccontextmanager
    async def begin():
        async with original_begin() as session:
            yield session
        if marker["reserved"] and not marker["delayed"]:
            marker["delayed"] = True
            await asyncio.sleep(2)

    monkeypatch.setattr(k, "add_event", add_event)
    monkeypatch.setattr(k.db.sessions, "begin", begin)
    client.post("/api/v1/cognition/configuration", json={"wall_seconds": 1})
    client.post("/api/v1/cognition/control", json={"command": "start", "provider": "meta"})
    observe(client)
    run = completed(client)
    assert marker["delayed"] and run["state"] == "FAILED", run
    assert_every_invocation_settled(run, expect=["cancelled"])
