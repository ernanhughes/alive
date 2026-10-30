import copy

import httpx
import pytest
from sqlalchemy import select

from alive.cognitive_models import CognitiveMessage
from alive.models import Event
from alive.workflows.context import digest
from alive.workflows.models import WorkflowExecution, WorkflowRun, WorkflowStageRun
from tests.workflow_execution_helpers import call, lifecycle, observation, prepare, reserved
from tests.workflow_r2_helpers import pi_environment


def test_uncited_model_claim_is_contract_checked_but_never_semantically_verified(
    client, settings, monkeypatch
):
    import json

    upstream = pi_environment(client, settings, monkeypatch)
    original = upstream.role_output

    def uncited(body):
        response = original(body).json()
        result = json.loads(response["choices"][0]["message"]["content"])
        assert result["claims"]
        for claim in result["claims"]:
            claim["evidence_refs"] = []
        response["choices"][0]["message"]["content"] = json.dumps(result)
        return httpx.Response(200, json=response)

    upstream.respond = uncited
    run, _ = call(
        client,
        lambda k: lifecycle(k, client.app.state.cognition, client.app.state.workflows, model=True),
    )
    assert run["status"] == "COMPLETED" and len(upstream.calls) == 1
    result = client.get(f"/api/v1/workflow-runs/{run['id']}/artifacts/record").json()
    assert result["result"]["claims"] and all(
        not c["evidence_refs"] for c in result["result"]["claims"]
    )
    assert result["assessment"]["semantic_status"] == "unverified"
    assert not result["independent_feedback"]
    stages = client.get(f"/api/v1/workflow-runs/{run['id']}/stages").json()["stages"]
    for stage in stages:
        assert stage["validation"]["semantic_status"] == "unverified"
        assert stage["validation"]["independent_verification"] is False
        assert stage["validation"]["uncited_claims_permitted"] is True


@pytest.mark.parametrize("terminal", ["COMPLETED", "FAILED", "CANCELLED", "UNKNOWN"])
def test_artifact_reports_terminal_run_separately_from_completed_stage(
    client, monkeypatch, terminal
):
    prepare(client)
    observation(client)
    runner = client.app.state.workflows
    original = runner._finish

    async def finish(run_id, owner):
        if terminal == "COMPLETED":
            return await original(run_id, owner)
        if terminal == "CANCELLED":
            async with runner.k.db.sessions.begin() as session:
                (await session.get(WorkflowExecution, run_id)).cancel_requested = True
            return await original(run_id, owner)
        if terminal == "FAILED":
            raise RuntimeError("secret C:/private password SQL prompt")
        # A quiescent interrupted image after artifact persistence, before finish.
        await runner._abandon(run_id, owner, "interrupted_requires_review", "UNKNOWN")

    monkeypatch.setattr(runner, "_finish", finish)
    run, _ = call(client, lambda k: lifecycle(k, client.app.state.cognition, runner))
    assert run["status"] == terminal
    response = client.get(f"/api/v1/workflow-runs/{run['id']}/artifacts/record")
    assert response.status_code == 200
    artifact = response.json()
    assert artifact["run_status"] == terminal
    assert artifact["workflow_completed"] is (terminal == "COMPLETED")
    assert artifact["terminal_reason"] == run["terminal_reason"]
    assert artifact["stage_state"] == "COMPLETED"
    assert artifact["stage_uncertainty"] == "none"
    assert artifact["stage_validation"]["semantic_status"] == "unverified"
    assert artifact["stage_validation"]["independent_verification"] is False
    assert artifact["independent_feedback"] is False
    assert "secret" not in response.text and "C:/private" not in response.text
    for stage in client.get(f"/api/v1/workflow-runs/{run['id']}/stages").json()["stages"]:
        assert stage["validation"]["semantic_status"] == "unverified"
        assert stage["validation"]["independent_verification"] is False
    assert all(value == 0 for value in call(client, reserved).values())


@pytest.mark.parametrize("tamper", ["event_output", "artifact", "rebuilt_hash", "other_stage"])
def test_historical_artifact_hash_chain_is_enforced(client, tamper):
    prepare(client)
    observation(client)
    run, _ = call(
        client, lambda k: lifecycle(k, client.app.state.cognition, client.app.state.workflows)
    )

    async def corrupt(k):
        async with k.db.sessions.begin() as session:
            rows = (
                await session.scalars(
                    select(WorkflowStageRun).where(WorkflowStageRun.run_id == run["id"])
                )
            ).all()
            row = next(r for r in rows if r.stage_id == "record")
            event = await session.scalar(select(Event).where(Event.id == row.output_ref[6:]))
            artifact = await session.get(CognitiveMessage, row.id)
            if tamper == "other_stage":
                row.output_ref = next(r for r in rows if r.stage_id == "prepare").output_ref
            elif tamper == "event_output":
                event.payload = {
                    **event.payload,
                    "output": {**event.payload["output"], "sha256": "f" * 64},
                }
            else:
                artifact.content = {**artifact.content, "result": {"forged": True}}
                if tamper == "rebuilt_hash":
                    output = {**event.payload["output"], "sha256": digest(artifact.content)}
                    event.payload = {**event.payload, "output": output}

    call(client, corrupt)
    assert client.get(f"/api/v1/workflow-runs/{run['id']}/artifacts/record").status_code == 404


def test_success_releases_slot_for_another_admitted_inquiry(client):
    prepare(client)
    ids = []
    for _ in range(2):
        observation(client)
        run, _ = call(
            client, lambda k: lifecycle(k, client.app.state.cognition, client.app.state.workflows)
        )
        assert run["status"] == "COMPLETED"
        ids.append(run["id"])

        async def vacant(k):
            async with k.db.sessions() as session:
                assert (await session.get(WorkflowExecution, run["id"])).slot is None

        call(client, vacant)
    assert len(set(ids)) == 2


def test_legacy_grant_retains_forensic_read_but_cannot_authorize_new_execution(client):
    prepare(client)
    observation(client)
    run, grant_id = call(
        client, lambda k: lifecycle(k, client.app.state.cognition, client.app.state.workflows)
    )

    async def legacy_image(k):
        async with k.db.sessions.begin() as session:
            event = await session.scalar(select(Event).where(Event.id == grant_id))
            payload = copy.deepcopy(event.payload)
            payload.pop("context_provenance")
            event.payload = payload
            (await session.get(WorkflowExecution, run["id"])).authorization_sha256 = digest(payload)
            assert (await session.get(WorkflowRun, run["id"])).status == "COMPLETED"

    call(client, legacy_image)
    result = client.get(f"/api/v1/workflow-runs/{run['id']}/artifacts/record")
    assert result.status_code == 200 and result.json()["context_provenance"]["approved"] is None
