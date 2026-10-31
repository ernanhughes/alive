"""Live owner admission: real captures/goals, no laboratory or fixture grants."""

import asyncio
import copy
import json
from datetime import timedelta
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import func, select, update

from alive.admission import service
from alive.admission.models import Admission
from alive.bespoke.recipes import load_catalogue
from alive.capabilities.manifest import parse
from alive.capabilities.registry import CapabilityRegistry
from alive.cognitive_models import CognitiveControl, Investigation, Laboratory, ModelInvocation
from alive.intelligence.models import IntelligenceLearningUpdate
from alive.models import Event, Instance, now, uid
from alive.pi.models import PiRun
from alive.sources import capture, custody
from alive.sources.cli import principal
from alive.sources.models import SourceApproval, SourceCapture
from alive.workflows import store as workflows
from alive.workflows.context import Refused, authorized
from alive.workflows.models import WorkflowDefinition, WorkflowExecution, WorkflowRun

BASE = "/api/v1/admissions"
PROFILE = Path(__file__).resolve().parents[1] / "alive/admission/repository-inspection.json"
CONTENT = "OWNER_CAPTURE_ONLY_NOT_BROWSER_AUTHORITY\n"


def call(client, work, *args, **kwargs):
    return client.portal.call(lambda: work(client.app.state.kernel, *args, **kwargs))


def accepted_goal(client, title="Inspect the approved repository"):
    response = client.post("/api/v1/goals", json={"title": title})
    assert response.status_code == 200, response.text
    goal = response.json()
    response = client.post(f"/api/v1/goals/{goal['id']}/transition", json={"status": "accepted"})
    assert response.status_code == 200, response.text
    return goal["id"]


@pytest.fixture
def owner_case(bare_client, tmp_path):
    client = bare_client
    root = tmp_path / "real-owner-repository"
    root.mkdir()
    (root / "README.md").write_bytes(CONTENT.encode())
    call(client, workflows.register_definition, json.loads(PROFILE.read_text()), status="active")

    async def approve_source(kernel):
        candidate = await custody.create_capture(
            kernel,
            source_type="repository",
            label="Owner repository",
            locator="owner-repository",
            classification="owner_internal",
            capture_method="owner_cli_repository",
            content=capture.repository_content(root, ["README.md"]),
        )
        approval = await custody.approve(
            kernel,
            candidate["id"],
            confirm_sha256=candidate["content_sha256"],
            operations=["repository.inspect"],
            scope={"items": ["README.md"]},
            ttl_seconds=3600,
            principal=principal(),
            request_id=uid(),
        )
        return candidate, approval

    captured, approved = call(client, approve_source)
    profile = client.get(BASE + "/profile")
    assert profile.status_code == 200, profile.text
    request = {
        "goal_ref": accepted_goal(client),
        "approval_ref": approved["id"],
        "recipe_sha256": profile.json()["recipe_sha256"],
        "objective": {
            "kind": "inspect_implementation",
            "requested_outcome": "Inspect captured files",
        },
        "paths": ["README.md"],
        "ttl_seconds": 300,
        "idempotency_key": uid(),
    }
    return client, request, captured, approved


def prepare_review(case):
    client, request, _, _ = case
    response = client.post(BASE, json=request)
    assert response.status_code == 200, response.text
    return response.json()


def approve_review(client, review, **overrides):
    return call(
        client,
        service.approve,
        review["id"],
        **{
            "confirm_sha256": review["review_sha256"],
            "principal": principal(),
        }
        | overrides,
    )


async def snapshot(kernel):
    async with kernel.db.sessions() as session:
        counts = {
            model.__tablename__: await session.scalar(select(func.count()).select_from(model))
            for model in (
                WorkflowRun,
                WorkflowExecution,
                Investigation,
                ModelInvocation,
                PiRun,
                IntelligenceLearningUpdate,
                Laboratory,
            )
        }
        counts["workflow_authorizations"] = await session.scalar(
            select(func.count())
            .select_from(Event)
            .where(
                Event.source == "workflow-owner",
                Event.event_type == "workflow.execution.authorized",
            )
        )
        control = await session.get(CognitiveControl, kernel.instance_id)
        return counts, dict(control.reserved)


def start(client, review, digest=None):
    return client.post(
        BASE + f"/{review['id']}/start",
        json={
            "review_sha256": digest or review["review_sha256"],
        },
    )


def test_real_owner_can_inspect_approved_capture_without_laboratory_or_model(owner_case):
    client, _, captured, _ = owner_case
    assert client.app.state.cognition.mode == "stopped"
    review = prepare_review(owner_case)
    before, _ = call(client, snapshot)
    assert before["laboratory_environments"] == before["workflow_authorizations"] == 0
    assert CONTENT not in json.dumps(
        review
    )  # the review presents a digest/inventory, not file data
    assert review["authorization_state"] == "pending"
    grant = review["terms"]["proposed_grant_data"]
    assert grant["max_model_calls"] == grant["max_output_tokens"] == 0
    assert not grant["outbound_approved"] and grant["operations"] == ["repository.inspect"]
    assert grant["models"] == {} and grant["role_contracts"] == {}
    assert approve_review(client, review)["authorization_state"] == "approved"
    response = start(client, review)
    assert response.status_code == 200, response.text
    completed = response.json()
    assert completed["run"]["status"] == "COMPLETED", completed
    run_id = completed["run"]["id"]
    stages = client.get(f"/api/v1/workflow-runs/{run_id}/stages").json()["stages"]
    assert len(stages) == 1 and stages[0]["capability"]["version"] == "1.1.0"

    async def output(kernel):
        async with kernel.db.sessions() as session:
            event = await session.scalar(
                select(Event).where(Event.id == stages[0]["output_ref"][6:])
            )
            return event.payload["output"]

    result = call(client, output)
    assert result["files"][0]["content"] == CONTENT
    assert result["files"][0]["path"] == "README.md"
    assert result["source_sha256"] == captured["content_sha256"]
    assert result["semantic_status"] == "unverified"
    assert client.get(f"/api/v1/workflow-runs/{run_id}/inspection").status_code == 200
    after, reserved = call(client, snapshot)
    assert after["laboratory_environments"] == 0
    assert (
        after["workflow_runs"]
        == after["workflow_executions"]
        == after["workflow_authorizations"]
        == 1
    )
    assert (
        after["model_invocations"]
        == after["pi_runs"]
        == after["intelligence_learning_updates"]
        == 0
    )
    assert all(value == 0 for value in reserved.values())


def test_source_approval_and_prepared_review_do_not_create_execution_authority(owner_case):
    client, _, _, _ = owner_case
    before = call(client, snapshot)
    review = prepare_review(owner_case)
    assert call(client, snapshot) == before
    assert start(client, review).status_code == 409
    assert call(client, snapshot) == before
    assert TestClient(client.app).get(BASE + "/profile").status_code == 401
    for action in ("approve", "authorize", "grant"):
        assert client.post(BASE + f"/{review['id']}/{action}", json={}).status_code in (404, 405)


@pytest.mark.parametrize(
    "field,value",
    [
        ("operations", ["repository.inspect", "cognition.role"]),
        ("models", {"observer": "unapproved"}),
        ("max_model_calls", 1),
        ("outbound_approved", True),
        ("workflow", {"name": "arbitrary"}),
    ],
)
def test_browser_requests_cannot_expand_the_closed_profile(owner_case, field, value):
    client, request, _, _ = owner_case
    assert client.post(BASE, json=request | {field: value}).status_code == 422
    assert call(client, snapshot)[0]["workflow_authorizations"] == 0


@pytest.mark.parametrize("change", ["digest", "principal"])
def test_local_confirmation_must_match_review_and_operating_system_owner(owner_case, change):
    client, _, _, _ = owner_case
    review = prepare_review(owner_case)
    override = (
        {"confirm_sha256": "0" * 64}
        if change == "digest"
        else {"principal": principal() + "-other"}
    )
    with pytest.raises(Refused, match="exact_local_owner_confirmation_required"):
        approve_review(client, review, **override)
    assert start(client, review).status_code == 409
    assert call(client, snapshot)[0]["workflow_authorizations"] == 0


def test_retries_and_completed_replay_return_one_execution_and_release_governor(owner_case):
    client, request, _, _ = owner_case
    review = prepare_review(owner_case)
    assert client.post(BASE, json=request).json() == review
    changed = copy.deepcopy(request)
    changed["objective"]["requested_outcome"] = "A different request"
    assert client.post(BASE, json=changed).status_code == 409
    approve_review(client, review)
    first = start(client, review)
    assert first.status_code == 200, first.text
    before = call(client, snapshot)
    assert start(client, review).json() == first.json()
    assert client.get(BASE + f"/{review['id']}").json() == first.json()
    assert call(client, snapshot) == before
    assert before[0]["workflow_runs"] == 1
    assert all(value == 0 for value in before[1].values())


@pytest.mark.parametrize(
    "change", ["withdraw", "expired", "source_digest", "recipe", "capability", "workflow"]
)
def test_changed_review_prerequisites_refuse_execution(owner_case, change):
    client, _, captured, approval = owner_case
    review = prepare_review(owner_case)
    approve_review(client, review)

    async def mutate(kernel):
        if change == "withdraw":
            await custody.withdraw(
                kernel, approval["id"], reason="Owner withdrew content", principal=principal()
            )
        elif change in ("expired", "source_digest", "workflow"):
            async with kernel.db.sessions.begin() as session:
                if change == "expired":
                    await session.execute(
                        update(SourceApproval)
                        .where(SourceApproval.id == approval["id"])
                        .values(expires_at=now() - timedelta(seconds=1))
                    )
                elif change == "source_digest":
                    await session.execute(
                        update(SourceCapture)
                        .where(SourceCapture.id == captured["id"])
                        .values(content_sha256="0" * 64)
                    )
                else:
                    await session.execute(
                        update(WorkflowDefinition)
                        .where(
                            WorkflowDefinition.id
                            == review["terms"]["proposed_grant_data"]["definition_id"]
                        )
                        .values(definition_sha256="0" * 64)
                    )
        elif change == "recipe":
            kernel.bespoke_recipes = tuple(
                r.model_copy(update={"description": "Changed after review"})
                if r.id == service.PROFILE
                else r
                for r in load_catalogue()
            )
        else:
            kernel.capabilities = CapabilityRegistry(
                [parse(cap.content) for cap in kernel.capabilities.list()],
                disabled=["repository.inspect@1.1.0"],
            )

    call(client, mutate)
    assert start(client, review).status_code == 409
    counts, reserved = call(client, snapshot)
    assert counts["workflow_runs"] == counts["workflow_authorizations"] == 0
    assert all(value == 0 for value in reserved.values())


def test_an_expired_source_cannot_prepare_a_review(owner_case):
    client, request, _, approval = owner_case

    async def expire(kernel):
        async with kernel.db.sessions.begin() as session:
            await session.execute(
                update(SourceApproval)
                .where(SourceApproval.id == approval["id"])
                .values(expires_at=now() - timedelta(seconds=1))
            )

    call(client, expire)
    assert client.post(BASE, json=request).status_code == 409


def test_review_integrity_refuses_sql_tampering(owner_case):
    client, _, _, _ = owner_case
    review = prepare_review(owner_case)
    terms = copy.deepcopy(review["terms"])
    terms["proposed_grant_data"]["max_model_calls"] = 1

    async def tamper(kernel):
        async with kernel.db.sessions.begin() as session:
            await session.execute(
                update(Admission).where(Admission.id == review["id"]).values(terms=terms)
            )

    call(client, tamper)
    assert client.get(BASE + f"/{review['id']}").status_code == 409
    assert start(client, review).status_code == 409


def test_source_scope_cannot_be_broadened_or_repeated(owner_case):
    client, request, _, _ = owner_case
    for paths in (["README.md", "private.txt"], ["README.md", "README.md"], ["../README.md"]):
        assert client.post(BASE, json=request | {"paths": paths}).status_code == 409


def test_review_for_one_goal_cannot_authorize_another_goal(owner_case):
    client, request, _, _ = owner_case
    first = prepare_review(owner_case)
    second = client.post(
        BASE,
        json=request
        | {
            "goal_ref": accepted_goal(client, "A separate owner goal"),
            "idempotency_key": uid(),
        },
    )
    assert second.status_code == 200, second.text
    assert second.json()["review_sha256"] != first["review_sha256"]
    assert start(client, second.json(), first["review_sha256"]).status_code == 409


def test_cross_instance_review_and_source_substitution_are_refused(owner_case):
    client, request, captured, _ = owner_case
    review = prepare_review(owner_case)
    foreign = copy.copy(client.app.state.kernel)
    foreign.instance_id = uid()

    async def foreign_source(kernel):
        async with kernel.db.sessions.begin() as session:
            session.add(Instance(id=foreign.instance_id, name="Other instance"))
        async with kernel.db.sessions() as session:
            original = await session.get(SourceCapture, captured["id"])
            content = copy.deepcopy(original.content)
        candidate = await custody.create_capture(
            foreign,
            source_type="repository",
            label="Other source",
            locator="other",
            classification="owner_internal",
            capture_method="owner_cli_repository",
            content=content,
        )
        return await custody.approve(
            foreign,
            candidate["id"],
            confirm_sha256=candidate["content_sha256"],
            operations=["repository.inspect"],
            scope={"items": ["README.md"]},
            ttl_seconds=3600,
            principal=principal(),
            request_id=uid(),
        )

    other_approval = call(client, foreign_source)
    assert (
        client.post(BASE, json=request | {"approval_ref": other_approval["id"]}).status_code == 409
    )
    with pytest.raises(Refused):
        client.portal.call(service.get, foreign, review["id"])


def test_owner_revocation_is_final_and_cannot_create_authority(owner_case):
    client, _, _, _ = owner_case
    review = prepare_review(owner_case)
    approve_review(client, review)
    assert (
        call(client, service.revoke, review["id"], principal=principal())["authorization_state"]
        == "revoked"
    )
    assert start(client, review).status_code == 409
    with pytest.raises(Refused, match="admission_expired_or_revoked"):
        approve_review(client, review)
    assert call(client, snapshot)[0]["workflow_authorizations"] == 0


def test_cancellation_of_running_read_releases_reservation(owner_case, monkeypatch):
    client, _, _, _ = owner_case
    review = prepare_review(owner_case)
    approve_review(client, review)
    original = CapabilityRegistry.adapter
    entered = asyncio.Event()
    release = asyncio.Event()

    def adapter(registry, operation, version=None):
        actual = original(registry, operation, version)
        if operation != "repository.inspect" or version != "1.1.0":
            return actual

        async def paused(context):
            entered.set()
            await release.wait()
            return await actual(context)

        return paused

    monkeypatch.setattr(CapabilityRegistry, "adapter", adapter)

    async def cancel_during_read(kernel):
        task = asyncio.create_task(service.start(client.app, review["id"], review["review_sha256"]))
        try:
            await asyncio.wait_for(entered.wait(), 30)
            await service.cancel(client.app, review["id"])
            await asyncio.gather(task, return_exceptions=True)
            return await service.get(kernel, review["id"])
        finally:
            release.set()
            if not task.done():
                task.cancel()
                await asyncio.gather(task, return_exceptions=True)

    result = call(client, cancel_during_read)
    assert result["run"]["status"] == "CANCELLED", result
    counts, reserved = call(client, snapshot)
    assert counts["workflow_runs"] == 1 and counts["model_invocations"] == 0
    assert all(value == 0 for value in reserved.values())


def test_ingest_cannot_forge_owner_admission_events(owner_case):
    client, _, _, _ = owner_case
    for source, event_type in (
        ("admission-owner", "workflow.owner.context"),
        ("admission-owner", "admission.owner.approved"),
        ("workflow-owner", "workflow.execution.authorized"),
    ):
        response = client.post(
            "/api/v1/events",
            json={"event_type": event_type, "source": source, "payload": {}},
        )
        assert response.status_code == 422, (source, event_type, response.text)


@pytest.mark.parametrize("approved", [False, True])
def test_a_hand_published_grant_cannot_stand_in_for_the_start_receipt(owner_case, approved):
    client, _, _, _ = owner_case
    review = prepare_review(owner_case)
    if approved:
        approve_review(client, review)
    grant = review["terms"]["proposed_grant_data"]

    async def forge(kernel):
        async with kernel.lock, kernel.db.sessions.begin() as session:
            forged = kernel.add_event(
                session, "workflow.execution.authorized", grant, source="workflow-owner"
            )
        async with kernel.db.sessions() as session:
            with pytest.raises(Refused) as caught:
                await authorized(session, kernel, str(forged.event_id))
        return str(caught.value)

    reason = call(client, forge)
    assert reason == (
        "admission_grant_identity_changed" if approved else "local_owner_approval_required"
    )
    assert call(client, snapshot)[0]["workflow_runs"] == 0


def test_start_requires_the_exact_digest_of_an_approved_review(owner_case):
    client, _, _, _ = owner_case
    review = prepare_review(owner_case)
    approve_review(client, review)
    assert start(client, review, "0" * 64).status_code == 409
    assert call(client, snapshot)[0]["workflow_authorizations"] == 0
    assert start(client, review).status_code == 200


def test_an_approval_receipt_from_any_other_source_is_not_owner_approval(owner_case):
    client, _, _, _ = owner_case
    review = prepare_review(owner_case)

    async def forge(kernel):
        async with kernel.lock, kernel.db.sessions.begin() as session:
            receipt = kernel.add_event(
                session,
                "admission.owner.approved",
                {
                    "admission_id": review["id"],
                    "review_sha256": review["review_sha256"],
                    "principal": principal(),
                },
                source="admission",
            )
            await session.flush()
            await session.execute(
                update(Admission)
                .where(Admission.id == review["id"])
                .values(approval_ref=str(receipt.event_id))
            )

    call(client, forge)
    assert start(client, review).status_code == 409
    assert call(client, snapshot)[0]["workflow_authorizations"] == 0
