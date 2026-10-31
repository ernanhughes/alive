"""Read-model qualification against persisted executions, never frontend fixtures."""

import asyncio

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import func, select, update

from alive.cognitive_models import ModelInvocation
from alive.intelligence.models import IntelligenceLearningUpdate
from alive.models import Event
from alive.pi.models import PiProviderRequest, PiRun
from alive.workflows import store
from alive.workflows.context import digest
from alive.workflows.models import WorkflowDefinition, WorkflowRun, WorkflowStageRun
from tests.test_workflows_api import demo
from tests.workflow_execution_helpers import call, lifecycle, observation, prepare
from tests.workflow_r2_helpers import gated_run, pi_environment


@pytest.fixture
def run(client):
    call(client, store.register_definition, demo(), status="active")
    opened, _ = call(client, store.open_run, "demo-flow", 1)
    call(client, store.advance_run, opened["id"], "RUNNING")
    call(client, store.advance_stage, opened["id"], "prepare", "RUNNING")
    return opened


@pytest.mark.parametrize("suffix", ["inspection", "timeline", "stages/missing/pi-receipt"])
def test_observatory_auth_and_no_actions(client, run, suffix):
    path = f"/api/v1/workflow-runs/{run['id']}/{suffix}"
    for headers in ({}, {"Authorization": "Bearer invalid"}):
        with TestClient(client.app, headers=headers) as anonymous:
            assert anonymous.get(path).status_code == 401
    for method in ("POST", "PUT", "PATCH", "DELETE"):
        assert client.request(method, path).status_code == 405


def test_timeline_bounded_ordered_payload_redacted_and_no_effect(client, run):
    path = f"/api/v1/workflow-runs/{run['id']}"

    async def seed(k):
        async with k.lock, k.db.sessions.begin() as s:
            stage = await s.scalar(
                select(WorkflowStageRun).where(
                    WorkflowStageRun.run_id == run["id"], WorkflowStageRun.stage_id == "prepare"
                )
            )
            k.add_event(
                s,
                "workflow.stage.claimed",
                {"run_id": run["id"], "stage_id": stage.id, "secret": "NEVER-RENDER"},
                source="workflow",
                correlation=run["id"],
            )
            result = k.add_event(
                s,
                "workflow.stage.result",
                {"run_id": run["id"], "stage_id": stage.id, "output": {"prompt": "NEVER-RENDER"}},
                source="workflow",
                correlation=run["id"],
            )
            stage.output_ref = "event:" + str(result.event_id)
            stage.output_sha256 = digest(result.payload["output"])

    call(client, seed)

    async def counts(k):
        async with k.db.sessions() as s:
            return [
                await s.scalar(select(func.count()).select_from(model))
                for model in (
                    ModelInvocation,
                    PiRun,
                    PiProviderRequest,
                    WorkflowRun,
                    IntelligenceLearningUpdate,
                    Event,
                )
            ]

    before = call(client, counts)
    first = client.get(path + "/timeline?limit=1").json()
    assert first["has_more"] and len(first["events"]) == 1
    page = client.get(path + f"/timeline?after={first['next_after']}&limit=500").json()
    events = first["events"] + page["events"]
    assert [e["sequence"] for e in events] == sorted({e["sequence"] for e in events})
    assert any(e["event_type"] == "workflow.stage.result" for e in events)
    assert "NEVER-RENDER" not in str(page) and "payload" not in str(page)
    assert page["complete_transition_history"] is False
    inspected = client.get(path + "/inspection").json()
    assert inspected["definition"]["id"] == page["definition_id"]
    assert inspected["run"]["workflow"]["definition_sha256"] == page["definition_sha256"]
    assert call(client, counts) == before
    for query in ("limit=0", "limit=501", "after=-1"):
        assert client.get(path + "/timeline?" + query).status_code == 422


@pytest.mark.parametrize(
    "corruption",
    [
        "owner",
        "hash",
        "version",
        "stage",
        "event_attempt",
        "opened_identity",
        "result_hash",
        "malformed_payload",
    ],
)
def test_corrupt_or_foreign_history_refused(client, run, corruption):
    async def corrupt(k):
        async with k.lock, k.db.sessions.begin() as s:
            if corruption == "hash":
                await s.execute(
                    update(WorkflowDefinition)
                    .where(WorkflowDefinition.id == run["workflow"]["definition_id"])
                    .values(definition_sha256="0" * 64)
                )
            elif corruption in ("owner", "version"):
                values = (
                    {"instance_id": "other"} if corruption == "owner" else {"workflow_version": 999}
                )
                # A real other instance is required by the FK; switching the reader tests ownership.
                if corruption == "owner":
                    k.instance_id = "other"
                else:
                    await s.execute(
                        update(WorkflowRun).where(WorkflowRun.id == run["id"]).values(**values)
                    )
            elif corruption == "stage":
                await s.execute(
                    update(WorkflowStageRun)
                    .where(WorkflowStageRun.run_id == run["id"])
                    .values(operation="unknown.operation")
                )
            elif corruption in {"opened_identity", "malformed_payload"}:
                payload = (
                    ["invalid"]
                    if corruption == "malformed_payload"
                    else {
                        "run_id": run["id"],
                        "name": "wrong",
                        "version": 1,
                        "definition_sha256": run["workflow"]["definition_sha256"],
                    }
                )
                await s.execute(
                    update(Event)
                    .where(
                        Event.correlation_id == run["id"], Event.event_type == "workflow.run.opened"
                    )
                    .values(payload=payload)
                )
            elif corruption == "result_hash":
                stage = await s.scalar(
                    select(WorkflowStageRun).where(
                        WorkflowStageRun.run_id == run["id"], WorkflowStageRun.stage_id == "prepare"
                    )
                )
                result = k.add_event(
                    s,
                    "workflow.stage.result",
                    {"run_id": run["id"], "stage_id": stage.id, "output": {"answer": "tampered"}},
                    source="workflow",
                    correlation=run["id"],
                )
                stage.output_ref = "event:" + str(result.event_id)
                stage.output_sha256 = "0" * 64
            else:
                k.add_event(
                    s,
                    "workflow.stage.claimed",
                    {"run_id": run["id"], "stage_id": "foreign"},
                    source="workflow",
                    correlation=run["id"],
                )

    old = client.app.state.kernel.instance_id
    try:
        call(client, corrupt)
        assert client.get(f"/api/v1/workflow-runs/{run['id']}/timeline").status_code == 404
    finally:
        client.app.state.kernel.instance_id = old


def test_actual_pi_receipt_binding_and_deterministic_history(client, settings, monkeypatch):
    upstream = pi_environment(client, settings, monkeypatch)

    async def before_dispatch(k, _):
        run_id = next(iter(client.app.state.workflows.tasks))
        inspected = await asyncio.to_thread(
            client.get, f"/api/v1/workflow-runs/{run_id}/inspection"
        )
        assert inspected.json()["run"]["status"] == "RUNNING"
        stages = await asyncio.to_thread(client.get, f"/api/v1/workflow-runs/{run_id}/stages")
        assert any(
            s["state"] == "RUNNING" and s["model_invocation_id"] for s in stages.json()["stages"]
        )
        assert len(inspected.json()["pi_links"]) == 1
        timeline = await asyncio.to_thread(client.get, f"/api/v1/workflow-runs/{run_id}/timeline")
        assert timeline.status_code == 200
        assert any(e["event_type"] == "pi.run.prepared" for e in timeline.json()["events"])
        assert not upstream.calls, "Observation dispatched the paused Pi call"

    identity = call(client, lambda k: gated_run(client, k, before_dispatch))
    result = call(client, store.get_run, identity)
    assert result["status"] == "COMPLETED" and len(upstream.calls) == 1
    base = f"/api/v1/workflow-runs/{result['id']}"
    stages = client.get(base + "/stages").json()["stages"]
    model = next(s for s in stages if s["pi_run_id"])
    response = client.get(base + f"/stages/{model['id']}/pi-receipt")
    assert response.status_code == 200, response.text
    assert response.json()["receipt"]["reservation_ref"] == model["model_invocation_id"]
    events = client.get(base + "/timeline").json()["events"]
    assert any(e["event_type"] == "pi.provider_request.dispatched" for e in events)
    assert all(e["stage_id"] == model["stage_id"] for e in events if e["pi_run_id"])
    assert client.get(base + "/stages/foreign/pi-receipt").status_code == 404
    deterministic = next(s for s in stages if not s["pi_run_id"])
    assert client.get(base + f"/stages/{deterministic['id']}/pi-receipt").status_code == 404

    async def corrupt(k):
        async with k.lock, k.db.sessions.begin() as s:
            await s.execute(
                update(ModelInvocation)
                .where(ModelInvocation.id == model["model_invocation_id"])
                .values(
                    input_json={"workflow_run_id": result["id"], "workflow_stage_id": "foreign"}
                )
            )

    call(client, corrupt)
    assert client.get(base + f"/stages/{model['id']}/pi-receipt").status_code == 404
    assert len(upstream.calls) == 1


def test_completed_deterministic_replay_counts(client):
    prepare(client)
    observation(client)
    result, _ = call(
        client, lambda k: lifecycle(k, client.app.state.cognition, client.app.state.workflows)
    )
    assert result["status"] == "COMPLETED"
    base = f"/api/v1/workflow-runs/{result['id']}"
    assert len(client.get(base + "/inspection").json()["graph"]["nodes"]) == 3
    for _ in range(3):
        assert client.get(base + "/timeline").status_code == 200
        assert client.get(base + "/artifacts/record").json()["independent_feedback"] is False

    async def count(k):
        async with k.db.sessions() as s:
            return await s.scalar(select(func.count()).select_from(ModelInvocation))

    assert call(client, count) == 0
