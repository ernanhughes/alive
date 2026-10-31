import asyncio
from types import SimpleNamespace

import pytest
from sqlalchemy import select, update

from alive.cognitive_models import ModelInvocation
from alive.models import Event, uid
from alive.pi.models import PiProviderRequest, PiRun
from alive.providers import Generation
from alive.society import mock_role
from alive.workflows import adapters, store
from alive.workflows.context import Refused, digest
from alive.workflows.examples import fixture_authorization
from alive.workflows.models import WorkflowExecution, WorkflowRun, WorkflowStageRun
from alive.workflows.runner import pi_facts
from tests.test_intelligence_receipts import graph
from tests.workflow_execution_helpers import (
    call,
    counts,
    lifecycle,
    observation,
    prepare,
    replace_adapters,
    reserved,
)


@pytest.mark.parametrize("mode", ["unknown", "lifecycle", "output"])
def test_process_exit_or_incomplete_receipt_cannot_complete_stage(client, mode):
    async def probe(k):
        identity, _, _ = await graph(k, mode)
        async with k.db.sessions() as session:
            stage = await session.get(WorkflowStageRun, identity)
            refused = False
            try:
                await pi_facts(session, k, stage)
            except Refused:
                refused = True
            assert refused, "incomplete Pi receipt was accepted"

    call(client, probe)


@pytest.mark.parametrize("mode", ["extra", "wrong_type", "nonfinite", "oversized"])
def test_declared_output_is_enforced_before_success(client, monkeypatch, mode):
    prepare(client)
    observation(client)
    data = {
        "extra": {"unregistered": True},
        "wrong_type": {"context": 1},
        "nonfinite": {"context": {"value": float("nan")}},
        "oversized": {"context": {"text": "a" * 70000}},
    }[mode]

    async def malformed(_):
        return adapters.StageResult(data)

    replace_adapters(monkeypatch, {"context.prepare": malformed})
    run, _ = call(
        client, lambda k: lifecycle(k, client.app.state.cognition, client.app.state.workflows)
    )
    assert run["status"] == "FAILED"
    stages = call(client, store.get_stage_runs, run["id"])
    assert stages[0]["state"] == "FAILED"
    assert stages[0]["output_ref"] is None


def test_source_authorization_is_checked_before_run_creation(client):
    prepare(client)
    observation(client)

    async def probe(k):
        async with client.app.state.cognition.workflow_inquiry() as inquiry:
            grant = await fixture_authorization(k, inquiry, model=False)
            async with k.db.sessions.begin() as session:
                event = await session.scalar(select(Event).where(Event.id == grant))
                source = await session.scalar(
                    select(Event).where(Event.id == event.payload["context_event_id"])
                )
                source.payload = source.payload | {"goal_id": uid()}
            refused = False
            try:
                await client.app.state.workflows.start(grant)
            except Refused:
                refused = True
            assert refused, "wrong-goal source was admitted"

    call(client, probe)


def test_bad_model_owner_has_no_dispatch_or_reservation(client, settings, monkeypatch):
    settings.alive_model_transport = "pi"
    dispatched = []

    async def catalog(_):
        return {"status": "available", "models": [settings.alive_meta_model]}

    monkeypatch.setattr("alive.cognition.MetaProvider.discover", catalog)

    class Gateway:
        async def structured(self, request):
            dispatched.append(request)
            return Generation(
                mock_role("observer", request.data).model_dump_json(),
                {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0},
                0,
            )

    monkeypatch.setattr("alive.cognition.gateway_for", lambda *_: Gateway())
    prepare(client, "meta")
    observation(client)

    async def probe(k):
        async with client.app.state.cognition.workflow_inquiry() as inquiry:
            approval = await fixture_authorization(k, inquiry, model=True)
            run = await client.app.state.workflows.start(approval)
            owner = uid()
            async with k.db.sessions.begin() as session:
                event = await session.scalar(select(Event).where(Event.id == approval))
                source = await session.scalar(
                    select(Event).where(Event.id == event.payload["context_event_id"])
                )
                context = source.payload["context"]
                execution = await session.get(WorkflowExecution, run["id"])
                execution.owner = owner
                await session.execute(
                    update(WorkflowRun).where(WorkflowRun.id == run["id"]).values(status="RUNNING")
                )
                stage = await session.scalar(
                    select(WorkflowStageRun).where(
                        WorkflowStageRun.run_id == run["id"], WorkflowStageRun.stage_id == "analyze"
                    )
                )
                stage.state, stage.input_sha256 = (
                    "RUNNING",
                    digest({"role": "observer", "context": context}),
                )
                stage_id = stage.id
            try:
                await client.app.state.cognition.call_role(
                    inquiry,
                    "observer",
                    context,
                    output_ceiling=1536,
                    workflow_claim=(run["id"], stage_id, "wrong-owner"),
                )
            except Refused:
                pass
            assert dispatched == []
            async with k.db.sessions() as session:
                assert not (await session.scalars(select(ModelInvocation))).all()
            # Explicit test recovery closes the synthetic claimed attempt.
            await client.app.state.workflows.recover()

    call(client, probe)
    assert all(value == 0 for value in call(client, reserved).values())


def test_restart_reconciles_ambiguous_stage_without_dispatch(client):
    prepare(client)
    observation(client)

    async def probe(k):
        async with client.app.state.cognition.workflow_inquiry() as inquiry:
            approval = await fixture_authorization(k, inquiry, model=False)
            run = await client.app.state.workflows.start(approval)
            async with k.db.sessions.begin() as session:
                await session.execute(
                    update(WorkflowRun).where(WorkflowRun.id == run["id"]).values(status="RUNNING")
                )
                stage = await session.scalar(
                    select(WorkflowStageRun).where(
                        WorkflowStageRun.run_id == run["id"], WorkflowStageRun.stage_id == "prepare"
                    )
                )
                call_row = ModelInvocation(
                    id=uid(),
                    investigation_id=inquiry,
                    role="observer",
                    provider="meta",
                    model="synthetic",
                    status="reserved",
                    input_json={},
                    reserved_tokens=100,
                )
                session.add(call_row)
                await session.flush()
                stage.state, stage.model_invocation_id = "RUNNING", call_row.id
                pi = PiRun(
                    id=uid(),
                    instance_id=k.instance_id,
                    operation="cognition.role",
                    idempotency_key=uid(),
                    reservation_ref=call_row.id,
                    state="UNKNOWN",
                    approved_request_json={},
                    approved_request_sha256="0" * 64,
                    requested_json={},
                    token_sha256="0" * 64,
                )
                session.add(pi)
                await session.flush()
                session.add(PiProviderRequest(run_id=pi.id, seq=1, state="ambiguous"))
            before = (await counts(k))[:3]
            await client.app.state.workflows.recover()
            result = await store.get_run(k, run["id"])
            assert result["status"] == "UNKNOWN"
            stages = await store.get_stage_runs(k, run["id"])
            assert stages[0]["state"] == "UNKNOWN"
            assert stages[0]["uncertainty"] != "none"
            assert (await counts(k))[:3] == before
            async with k.db.sessions() as session:
                invocation = await session.get(ModelInvocation, call_row.id)
                assert invocation.status == "interrupted"
                assert invocation.usage["charged_tokens"] == 100
            await client.app.state.workflows.recover()
            assert (await store.get_run(k, run["id"]))["status"] == "UNKNOWN"

    call(client, probe)
    assert all(value == 0 for value in call(client, reserved).values())


def test_record_requires_actual_validation_dependency():
    context = SimpleNamespace(
        inputs={"result": {"opinion": "true"}, "assessment": {"valid": True}},
        dependencies={
            "model": {
                "operation": "cognition.role",
                "implementation": "cognition-role-v1",  # what the runner records from the snapshot
                "validation_status": "passed",
                "output": {},
            }
        },
    )
    with pytest.raises(Refused, match="independent_validation_dependency_required"):
        asyncio.run(adapters.record(context))
