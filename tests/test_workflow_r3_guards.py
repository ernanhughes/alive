import asyncio
import contextlib

import pytest
from sqlalchemy import select

from alive.cognitive_models import Investigation, ModelInvocation
from alive.models import Event, Goal, now, uid
from alive.pi.models import PiProviderRequest, PiRun
from alive.pi.states import REQUEST_TERMINAL, RUN_TERMINAL
from alive.schemas import Observation
from alive.workflows import adapters, context, store
from alive.workflows.examples import definition, fixture_authorization
from alive.workflows.models import WorkflowExecution, WorkflowRun, WorkflowStageRun
from alive.workflows.store import register_definition
from tests.workflow_execution_helpers import (
    call,
    lifecycle,
    observation,
    prepare,
    replace_adapters,
    reserved,
)
from tests.workflow_r2_helpers import gated_run, pi_environment


async def settled(kernel):
    async with kernel.db.sessions() as session:
        calls = (await session.scalars(select(ModelInvocation))).all()
        pi = (await session.scalars(select(PiRun))).all()
        requests = (await session.scalars(select(PiProviderRequest))).all()
        assert all((row.status != "reserved" for row in calls))
        assert all((row.state in RUN_TERMINAL for row in pi))
        assert all((row.state in REQUEST_TERMINAL for row in requests))
        return (len(calls), len(pi), len(requests))


def test_stage_cannot_reserve_a_second_real_model_invocation(client, settings, monkeypatch):
    upstream = pi_environment(client, settings, monkeypatch)
    original = adapters.role

    async def twice(ctx):
        await original(ctx)
        return await original(ctx)

    replace_adapters(monkeypatch, {"cognition.role": twice})

    async def probe(k):
        run, _ = await lifecycle(
            k, client.app.state.cognition, client.app.state.workflows, model=True
        )
        assert len(upstream.calls) == 1, "one authorized stage dispatched twice"
        assert await settled(k) == (1, 1, 1), "second invocation or Pi receipt accepted"
        assert run["status"] == "UNKNOWN", "an attempted duplicate effect was presented as success"
        assert run["terminal_reason"] == "model_stage_claim_required"
        await client.app.state.workflows.execute(run["id"])
        await client.app.state.workflows.recover()
        assert len(upstream.calls) == 1

    call(client, probe)
    assert all((v == 0 for v in call(client, reserved).values()))


@pytest.mark.parametrize("corruption", ["other_run", "other_inquiry"])
def test_inconsistent_associations_cannot_cross_actual_dispatch(
    client, settings, monkeypatch, corruption
):
    upstream = pi_environment(client, settings, monkeypatch)
    runner = client.app.state.workflows
    previous, _ = call(client, lambda k: lifecycle(k, client.app.state.cognition, runner))
    observation(client)

    async def before(k, grant_id):
        async with k.lock, k.db.sessions.begin() as session:
            invocation = (await session.scalars(select(ModelInvocation))).one()
            mine = await session.scalar(
                select(WorkflowStageRun).where(
                    WorkflowStageRun.model_invocation_id == invocation.id
                )
            )
            if corruption == "other_run":
                foreign = await session.scalar(
                    select(WorkflowStageRun).where(
                        WorkflowStageRun.run_id == previous["id"],
                        WorkflowStageRun.stage_id == "prepare",
                    )
                )
                mine.model_invocation_id = None
                await session.flush()
                foreign.state, foreign.model_invocation_id = ("RUNNING", invocation.id)
                invocation.input_json = {**invocation.input_json, "workflow_stage_id": foreign.id}
            else:
                invocation.investigation_id = previous["investigation_id"]

    async def probe(k):
        await gated_run(client, k, before)
        assert len(upstream.calls) == 0, f"{corruption} association crossed dispatch fence"
        await settled(k)

    call(client, probe)
    assert all((v == 0 for v in call(client, reserved).values()))


@pytest.mark.parametrize("phase", ["before_reservation", "after_reservation", "during_dispatch"])
def test_goal_cancellation_route_prevents_new_dispatch_and_preserves_possible_effects(
    client, settings, monkeypatch, phase
):
    upstream = pi_environment(client, settings, monkeypatch)
    runner, egress = (client.app.state.workflows, client.app.state.pi.egress)
    reached, release = (asyncio.Event(), asyncio.Event())
    original = egress._dispatch
    if phase == "after_reservation":

        async def gated(request_id):
            reached.set()
            await release.wait()
            return await original(request_id)

        monkeypatch.setattr(egress, "_dispatch", gated)
    if phase == "during_dispatch":
        upstream.block = asyncio.Event()

    async def probe(k):
        async with client.app.state.cognition.workflow_inquiry() as inquiry:
            grant_id = await fixture_authorization(k, inquiry, model=True)
            run = await runner.start(grant_id)
            task = None
            try:
                if phase != "before_reservation":
                    task = asyncio.create_task(runner.execute(run["id"]))
                    if phase == "after_reservation":
                        await asyncio.wait_for(reached.wait(), 30)
                    else:
                        async with asyncio.timeout(30):
                            while not upstream.calls:
                                await asyncio.sleep(0.01)
                response = await asyncio.to_thread(
                    client.post,
                    f"/api/v1/goals/{run['goal_id']}/transition",
                    json={"status": "cancelled"},
                )
                assert response.status_code == 200
                release.set()
                if upstream.block:
                    upstream.block.set()
                final = (
                    await asyncio.wait_for(task, 30) if task else await runner.execute(run["id"])
                )
                expected_calls = int(phase == "during_dispatch")
                assert len(upstream.calls) == expected_calls, (
                    "dispatch crossed acknowledged goal cancellation"
                )
                assert final["status"] == ("UNKNOWN" if expected_calls else "FAILED")
                if expected_calls:
                    async with k.db.sessions() as session:
                        assert list(await session.scalars(select(ModelInvocation.status))) == [
                            "validated"
                        ]
                        assert list(await session.scalars(select(PiRun.state))) == ["SETTLED"]
                        assert list(await session.scalars(select(PiProviderRequest.state))) == [
                            "settled"
                        ]
                assert (await runner.execute(run["id"]))["status"] == final["status"]
                await runner.recover()
                assert len(upstream.calls) == expected_calls
                await settled(k)
            finally:
                release.set()
                if upstream.block:
                    upstream.block.set()
                if task and (not task.done()):
                    task.cancel()
                    with contextlib.suppress(asyncio.CancelledError):
                        await task

    call(client, probe)
    assert all((v == 0 for v in call(client, reserved).values()))


@pytest.mark.parametrize(
    "phase", ["deterministic", "before_dispatch", "after_dispatch", "run_deadline"]
)
def test_real_stage_timeout_keeps_category_effects_and_settlement(
    client, settings, monkeypatch, phase
):
    model = phase in {"before_dispatch", "after_dispatch"}
    upstream = pi_environment(client, settings, monkeypatch) if model else None
    if not model:
        prepare(client)
        observation(client)
    runner = client.app.state.workflows
    raw = definition(model=model)
    raw["version"] = 19
    target = "analyze" if model else "prepare"
    for stage in raw["stages"]:
        if stage["id"] == target:
            stage["limits"]["timeout_seconds"] = 10 if phase == "run_deadline" else 2
    if not model:

        async def slow(_):
            await asyncio.Event().wait()

        replace_adapters(monkeypatch, {"context.prepare": slow})
    elif phase == "after_dispatch":
        upstream.block = asyncio.Event()
    else:

        async def before(_):
            await asyncio.Event().wait()

        monkeypatch.setattr(client.app.state.pi.egress, "_dispatch", before)

    async def probe(k):
        async with client.app.state.cognition.workflow_inquiry() as inquiry:
            selected, _ = await register_definition(k, raw, status="active", source="admin")
            grant = await fixture_authorization(
                k,
                inquiry,
                model=model,
                changes={
                    "definition_id": selected["id"],
                    "definition_sha256": selected["definition_sha256"],
                },
            )
            run = await runner.start(grant)
            if phase == "run_deadline":
                from datetime import timedelta

                async with k.db.sessions.begin() as session:
                    (await session.get(WorkflowExecution, run["id"])).deadline = now() + timedelta(
                        seconds=1
                    )
            final = await asyncio.wait_for(runner.execute(run["id"]), 30)
            count = int(phase == "after_dispatch")
            assert (len(upstream.calls) if upstream else 0) == count
            assert final["terminal_reason"] == "timeout", (
                "stage TimeoutError lost its bounded category"
            )
            assert final["status"] == ("UNKNOWN" if count else "FAILED")
            rows = await store.get_stage_runs(k, run["id"])
            row = next((s for s in rows if s["stage_id"] == target))
            assert row["error_category"] == "timeout"
            assert row["uncertainty"] == ("unknown_outcome" if count else "none")
            await settled(k)
            async with k.db.sessions() as session:
                pi_states = list(await session.scalars(select(PiRun.state)))
                request_states = list(await session.scalars(select(PiProviderRequest.state)))
            if phase == "after_dispatch":
                assert pi_states == ["UNKNOWN"] and request_states == ["ambiguous"]
            elif phase == "before_dispatch":
                assert pi_states == ["CANCELLED"] and request_states == ["rejected"]
            else:
                assert pi_states == request_states == []
            await runner.execute(run["id"])
            await runner.recover()
            assert (len(upstream.calls) if upstream else 0) == count

    call(client, probe)
    assert all((v == 0 for v in call(client, reserved).values()))


@pytest.mark.parametrize("violation", ["action_kind", "source_ids", "ok"])
def test_context_contract_is_enforced(client, violation):
    prepare(client)
    observation(client)

    async def probe(k):
        async with client.app.state.cognition.workflow_inquiry() as inquiry:
            async with k.db.sessions() as session:
                goal = (await session.get(Investigation, inquiry)).goal_id
            event_id = uid()
            ctx = {
                "observation": "page text",
                "claims": [],
                "sources": [],
                "memories": [],
                "source_event_ids": [event_id],
                "requested_action_kind": "record_analysis",
            }
            if violation == "action_kind":
                ctx["requested_action_kind"] = "send_external_message"
            elif violation == "source_ids":
                ctx["source_event_ids"] = [uid()]
            payload = {"goal_id": goal, "text": "t", "context": ctx}
            await k.ingest(
                Observation(event_id=event_id, event_type="browser.dom_changed", payload=payload)
            )
            grant = await fixture_authorization(
                k,
                inquiry,
                model=False,
                changes={
                    "context_event_id": event_id,
                    "context_sha256": context.digest(payload),
                    "context_provenance": {
                        "source": "extension",
                        "event_type": "browser.dom_changed",
                        "custody": "untrusted_browser",
                        "consent": "exact_content_and_scope",
                    },
                },
            )
            try:
                await client.app.state.workflows.start(grant)
                return "admitted"
            except context.Refused as error:
                return "refused:" + str(error)

    outcome = call(client, probe)
    assert (outcome == "admitted") == (violation == "ok"), outcome


@pytest.mark.parametrize(
    "field",
    [
        "definition_sha256",
        "workflow_name",
        "workflow_version",
        "input_sha256",
        "authorization_ref",
        "goal_id",
    ],
)
def test_run_identity_corruption_is_rejected_at_the_fence(client, settings, monkeypatch, field):
    upstream = pi_environment(client, settings, monkeypatch)
    runner = client.app.state.workflows
    egress = client.app.state.pi.egress
    original = egress._dispatch
    reached, release = (asyncio.Event(), asyncio.Event())

    async def gated(request_id):
        reached.set()
        await release.wait()
        return await original(request_id)

    egress._dispatch = gated

    async def probe(k):
        async with client.app.state.cognition.workflow_inquiry() as inquiry:
            grant = await fixture_authorization(k, inquiry, model=True)
            run = await runner.start(grant)
            task = asyncio.create_task(runner.execute(run["id"]))
            await asyncio.wait_for(reached.wait(), 60)
            async with k.lock, k.db.sessions.begin() as session:
                row = await session.get(WorkflowRun, run["id"])
                from sqlalchemy import update

                raw = {
                    "definition_sha256": {"definition_sha256": "0" * 64},
                    "workflow_name": {"workflow_name": "something-else"},
                    "workflow_version": {"workflow_version": 99},
                }.get(field)
                if raw:
                    await session.execute(
                        update(WorkflowRun).where(WorkflowRun.id == run["id"]).values(**raw)
                    )
                elif field == "input_sha256":
                    row.input_sha256 = "1" * 64
                elif field == "authorization_ref":
                    other = await session.scalar(select(Event).where(Event.id != grant))
                    row.authorization_ref = other.id
                else:
                    goal = Goal(instance_id=k.instance_id, title="other")
                    session.add(goal)
                    await session.flush()
                    row.goal_id = goal.id
            release.set()
            with contextlib.suppress(ValueError):
                await asyncio.wait_for(task, 60)
            return len(upstream.calls)

    calls = call(client, probe)
    assert calls == 0, f"{field} corruption crossed the dispatch fence"
