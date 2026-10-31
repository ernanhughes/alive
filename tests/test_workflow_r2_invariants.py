import asyncio
import contextlib

import pytest
from sqlalchemy import select

from alive.cognitive_models import Investigation
from alive.workflows import adapters
from alive.workflows.context import Refused
from alive.workflows.examples import definition, fixture_authorization
from alive.workflows.models import WorkflowStageRun
from alive.workflows.store import register_definition
from tests.workflow_execution_helpers import (
    call,
    lifecycle,
    observation,
    prepare,
    replace_adapters,
    reserved,
)


@pytest.mark.parametrize("claimed", ["snapshot", "calls", "worker"])
def test_existing_inquiry_work_cannot_be_transferred_to_workflow(client, claimed):
    prepare(client)
    observation(client)

    async def probe(k):
        cognition = client.app.state.cognition
        async with cognition.workflow_inquiry() as inquiry:
            grant = await fixture_authorization(k, inquiry, model=False)
            task = None
            async with k.db.sessions.begin() as session:
                row = await session.get(Investigation, inquiry)
                if claimed == "snapshot":
                    row.snapshot = {"already": "owned"}
                elif claimed == "calls":
                    row.usage = {**row.usage, "calls": 1}
            if claimed == "worker":
                task = cognition.worker = asyncio.create_task(asyncio.Event().wait())
            try:
                refused = False
                try:
                    await client.app.state.workflows.start(grant)
                except Refused:
                    refused = True
                assert refused, "existing inquiry work was transferred"
            finally:
                if task:
                    task.cancel()
                    with contextlib.suppress(asyncio.CancelledError):
                        await task

    call(client, probe)


def test_completed_stage_cannot_be_claimed_again_even_by_current_run_owner(client, monkeypatch):
    prepare(client)
    observation(client)
    runner = client.app.state.workflows
    original = runner._stage

    async def repeat(run_id, owner, stage):
        await original(run_id, owner, stage)
        if stage.id == "prepare":
            refused = False
            try:
                await original(run_id, owner, stage)
            except Refused as error:
                refused = str(error) == "stage_claim_lost"
            assert refused, "same stage executed twice under one run claim"

    monkeypatch.setattr(runner, "_stage", repeat)
    run, _ = call(client, lambda k: lifecycle(k, client.app.state.cognition, runner))
    assert run["status"] == "COMPLETED", run


def test_control_dependency_blocks_stage_even_without_an_output_reference(client, monkeypatch):
    prepare(client)
    observation(client)
    runner = client.app.state.workflows
    original = runner._stage
    raw = definition(model=False)
    # This real immutable graph has a control dependency without data references.
    checkpoint = {**raw["stages"][0], "id": "checkpoint", "depends_on": ["prepare"]}
    raw["stages"].insert(1, checkpoint)
    raw["version"] = 2

    async def interrupt(run_id, owner, stage):
        if stage.id == "checkpoint":
            async with runner.k.db.sessions.begin() as session:
                previous = await session.scalar(
                    select(WorkflowStageRun).where(
                        WorkflowStageRun.run_id == run_id, WorkflowStageRun.stage_id == "prepare"
                    )
                )
                previous.state = "FAILED"
        await original(run_id, owner, stage)

    monkeypatch.setattr(runner, "_stage", interrupt)

    async def probe(k):
        async with client.app.state.cognition.workflow_inquiry() as inquiry:
            selected, _ = await register_definition(k, raw, status="active", source="admin")
            grant = await fixture_authorization(
                k,
                inquiry,
                model=False,
                changes={
                    "definition_id": selected["id"],
                    "definition_sha256": selected["definition_sha256"],
                },
            )
            run = await runner.start(grant)
            assert (await runner.execute(run["id"]))["status"] == "FAILED"
            async with k.db.sessions() as session:
                row = await session.scalar(
                    select(WorkflowStageRun).where(
                        WorkflowStageRun.run_id == run["id"],
                        WorkflowStageRun.stage_id == "checkpoint",
                    )
                )
                assert row.started_at is None, (
                    "control-dependent stage started without its prerequisite"
                )

    call(client, probe)


@pytest.mark.parametrize("fault", ["adapter", "output", "persistence"])
def test_bounded_failure_categories_do_not_disclose_internal_exception_text(
    client, monkeypatch, fault
):
    prepare(client)
    observation(client)
    runner = client.app.state.workflows
    if fault == "adapter":

        async def fail(_):
            raise RuntimeError("C:/secret password raw SQL prompt")

        replace_adapters(monkeypatch, {"context.prepare": fail})
    elif fault == "output":

        async def bad(_):
            return adapters.StageResult({"extra": "secret"})

        replace_adapters(monkeypatch, {"context.prepare": bad})
    else:

        async def fail(*_):
            raise RuntimeError("C:/secret password raw SQL prompt")

        monkeypatch.setattr(runner, "_persist_result", fail)
    run, _ = call(client, lambda k: lifecycle(k, client.app.state.cognition, runner))
    expected = {
        "adapter": "adapter_execution_failure",
        "output": "output_validation_failure",
        "persistence": "result_persistence_failure",
    }[fault]
    assert run["status"] == "FAILED" and run["terminal_reason"] == expected
    assert all(v == 0 for v in call(client, reserved).values())
    response = client.get(f"/api/v1/workflow-runs/{run['id']}/stages")
    assert response.json()["stages"][0]["error_category"] == expected
    assert "secret" not in response.text and "password" not in response.text
