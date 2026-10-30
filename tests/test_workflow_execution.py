import asyncio
import copy
from datetime import timedelta
from types import SimpleNamespace

import pytest
from sqlalchemy import select, update

from alive.cognitive_models import CognitiveMessage
from alive.models import Event, now, uid
from alive.workflows import adapters, states, store
from alive.workflows.context import OWNER, Refused
from alive.workflows.examples import fixture_authorization
from alive.workflows.models import (
    WorkflowDefinition,
    WorkflowExecution,
    WorkflowRun,
    WorkflowStageRun,
)
from alive.workflows.runner import WorkflowRunner, artifact_view
from tests.workflow_execution_helpers import call, counts, lifecycle, observation, prepare, reserved


def test_deterministic_procedure_records_real_artifact_and_zero_learning(client):
    prepare(client)
    observation(client)
    before = call(client, counts)
    run, grant = call(
        client, lambda k: lifecycle(k, client.app.state.cognition, client.app.state.workflows)
    )
    assert run["status"] == "COMPLETED", run
    stages = call(client, store.get_stage_runs, run["id"])
    assert len(stages) == 3 and all(s["state"] == "COMPLETED" for s in stages)
    assert [s["operation"] for s in stages] == [
        "context.prepare",
        "evidence.evaluate",
        "result.record",
    ]
    result = call(client, artifact_view, run["id"], "record")
    assert result["assessment"]["semantic_status"] == "controlled_sources_only"
    assert not result["independent_feedback"] and result["intelligence_episode_id"] is None
    assert call(client, counts)[:3] == before[:3]
    assert all(value == 0 for value in call(client, reserved).values())
    after = call(client, counts)

    async def replay(_):
        repeated = await client.app.state.workflows.start(grant)
        assert repeated["id"] == run["id"]
        assert (await client.app.state.workflows.execute(run["id"]))["status"] == "COMPLETED"

    call(client, replay)
    for _ in range(3):
        assert client.get(f"/api/v1/workflow-runs/{run['id']}/artifacts/record").status_code == 200
    assert call(client, counts) == after


@pytest.mark.parametrize(
    "mode", ["missing", "untrusted", "expired", "scope", "budget", "operation"]
)
def test_admission_is_separate_from_definition_or_bearer(client, mode):
    prepare(client)
    observation(client)

    async def probe(k):
        async with client.app.state.cognition.workflow_inquiry() as inquiry:
            changes = {
                "expired": {"expires_at": (now() - timedelta(seconds=1)).isoformat()},
                "scope": {"goal_id": uid()},
                "budget": {"max_output_tokens": 1},
                "operation": {"operations": ["context.prepare"]},
            }.get(mode)
            grant = await fixture_authorization(k, inquiry, model=False, changes=changes)
            if mode == "missing":
                grant = uid()
            if mode == "untrusted":
                async with k.db.sessions.begin() as session:
                    await session.execute(
                        update(Event).where(Event.id == grant).values(source="browser")
                    )
            refused = False
            try:
                await client.app.state.workflows.start(grant)
            except (Refused, ValueError):
                refused = True
            assert refused, "unapproved admission created an execution"
            async with k.db.sessions() as session:
                assert not (await session.scalars(select(WorkflowExecution))).all()

    call(client, probe)
    assert all(value == 0 for value in call(client, reserved).values())


@pytest.mark.parametrize(
    "mode", ["context", "definition", "revoked", "withdrawn", "budget", "stage"]
)
def test_changes_after_admission_fail_closed_and_release_governor(client, mode):
    prepare(client)
    observation(client)

    async def probe(k):
        async with client.app.state.cognition.workflow_inquiry() as inquiry:
            authorization = await fixture_authorization(k, inquiry, model=False)
            run = await client.app.state.workflows.start(authorization)
            async with k.db.sessions.begin() as session:
                event = await session.scalar(select(Event).where(Event.id == authorization))
                if mode == "context":
                    await session.execute(
                        update(Event)
                        .where(Event.id == event.payload["context_event_id"])
                        .values(payload={})
                    )
                elif mode == "definition":
                    await session.execute(
                        update(WorkflowDefinition)
                        .where(WorkflowDefinition.id == event.payload["definition_id"])
                        .values(definition_sha256="0" * 64)
                    )
                elif mode in ("revoked", "withdrawn"):
                    k.add_event(
                        session,
                        "workflow.execution.revoked"
                        if mode == "revoked"
                        else "workflow.context.withdrawn",
                        {"authorization_id": authorization}
                        if mode == "revoked"
                        else {"source_event_id": event.payload["context_event_id"]},
                        source=OWNER,
                    )
                elif mode == "budget":
                    await session.execute(
                        update(WorkflowRun)
                        .where(WorkflowRun.id == run["id"])
                        .values(budget_json={})
                    )
                else:
                    await session.execute(
                        update(WorkflowStageRun)
                        .where(
                            WorkflowStageRun.run_id == run["id"],
                            WorkflowStageRun.stage_id == "prepare",
                        )
                        .values(operation="memory.retrieve")
                    )
            result = await client.app.state.workflows.execute(run["id"])
            assert result["status"] == states.FAILED

    call(client, probe)
    assert all(value == 0 for value in call(client, reserved).values())


def test_independent_run_claims_execute_once(client, monkeypatch):
    prepare(client)
    observation(client)
    calls = []
    original = adapters.ADAPTERS["context.prepare"]

    async def counted(ctx):
        calls.append(ctx.run_id)
        await asyncio.sleep(0.05)
        return await original(ctx)

    monkeypatch.setattr(
        adapters, "ADAPTERS", dict(adapters.ADAPTERS) | {"context.prepare": counted}
    )
    monkeypatch.setattr("alive.workflows.runner.ADAPTERS", adapters.ADAPTERS)

    async def probe(k):
        async with client.app.state.cognition.workflow_inquiry() as inquiry:
            authorization = await fixture_authorization(k, inquiry, model=False)
            runner = client.app.state.workflows
            run = await runner.start(authorization)
            other_kernel = SimpleNamespace(
                db=k.db,
                instance_id=k.instance_id,
                lock=asyncio.Lock(),
                add_event=k.add_event,
                settings=k.settings,
                ready=True,
            )
            other = WorkflowRunner(other_kernel, client.app.state.cognition)
            results = await asyncio.gather(runner.execute(run["id"]), other.execute(run["id"]))
            assert "COMPLETED" in [r["status"] for r in results]
            assert calls == [run["id"]]
            async with k.db.sessions() as session:
                claims = (
                    await session.scalars(
                        select(Event).where(
                            Event.event_type == "workflow.execution.claimed",
                            Event.payload["run_id"].as_string() == run["id"],
                        )
                    )
                ).all()
                assert len(claims) == 1

    call(client, probe)


@pytest.mark.parametrize("phase", ["prepare", "record", "settlement"])
def test_cancellation_or_persistence_failure_has_no_false_success(client, monkeypatch, phase):
    prepare(client)
    observation(client)
    original = client.app.state.kernel.add_event

    def fail(session, kind, payload=None, **kwargs):
        if phase == "settlement" and kind == "workflow.execution.completed":
            raise RuntimeError("injected persistence failure")
        return original(session, kind, payload, **kwargs)

    monkeypatch.setattr(client.app.state.kernel, "add_event", fail)
    if phase != "settlement":
        operation = "context.prepare" if phase == "prepare" else "result.record"

        async def cancel(_):
            raise asyncio.CancelledError()

        monkeypatch.setattr(
            "alive.workflows.runner.ADAPTERS", dict(adapters.ADAPTERS) | {operation: cancel}
        )
    run, _ = call(
        client, lambda k: lifecycle(k, client.app.state.cognition, client.app.state.workflows)
    )
    assert run["status"] in ("FAILED", "CANCELLED")
    assert all(value == 0 for value in call(client, reserved).values())
    assert call(client, counts)[:3] == (0, 0, 0)


def test_record_cannot_trust_a_literal_model_validation_boolean(client):
    prepare(client)
    observation(client)

    async def probe(k):
        async with client.app.state.cognition.workflow_inquiry() as inquiry:
            grant = await fixture_authorization(k, inquiry, model=False)
            async with k.db.sessions.begin() as session:
                event = await session.scalar(select(Event).where(Event.id == grant))
                definition = await session.get(WorkflowDefinition, event.payload["definition_id"])
                changed = copy.deepcopy(definition.definition_json)
                changed["stages"][-1]["inputs"] = {"result": "true", "assessment": "true"}
                # Deliberate DB corruption cannot change the selected immutable procedure.
                await session.execute(
                    update(WorkflowDefinition)
                    .where(WorkflowDefinition.id == definition.id)
                    .values(definition_json=changed)
                )
            with pytest.raises(Refused):
                await client.app.state.workflows.start(grant)

    call(client, probe)


def test_artifact_tampering_and_cross_instance_refused(client):
    prepare(client)
    observation(client)
    run, _ = call(
        client, lambda k: lifecycle(k, client.app.state.cognition, client.app.state.workflows)
    )

    async def corrupt(k):
        async with k.db.sessions.begin() as session:
            stage = await session.scalar(
                select(WorkflowStageRun).where(
                    WorkflowStageRun.run_id == run["id"], WorkflowStageRun.stage_id == "record"
                )
            )
            await session.execute(
                update(CognitiveMessage)
                .where(CognitiveMessage.id == stage.id)
                .values(content={"result": "tampered"})
            )
        with pytest.raises(Refused):
            await artifact_view(SimpleNamespace(db=k.db, instance_id=uid()), run["id"], "record")

    call(client, corrupt)
    assert client.get(f"/api/v1/workflow-runs/{run['id']}/artifacts/record").status_code == 404
