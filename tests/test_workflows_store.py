"""ALIVE-PI-02A: persistence, immutable versions, run/stage records, no execution."""

import asyncio
import copy
import json

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select, text
from sqlalchemy.exc import IntegrityError

from alive.app import create_app
from alive.models import Event
from alive.workflows import states, store
from alive.workflows.models import (
    ImmutableRecord,
    WorkflowDefinition,
    WorkflowRun,
    WorkflowStageRun,
)
from alive.workflows.spec import DefinitionError
from tests.conftest import TOKEN
from tests.test_workflows_spec import SEED_TEXT, seed, stage, workflow


def kernel(client):
    return client.app.state.kernel


def call(client, fn, *args, **kwargs):
    return client.portal.call(lambda: fn(kernel(client), *args, **kwargs))


def active_workflow(name="demo-flow", version=1, **over):
    return workflow(
        stage("prepare"),
        stage(
            "check",
            operation="evidence.validate_references",
            type="validation",
            depends_on=["prepare"],
        ),
        name=name,
        version=version,
        **over,
    )


def rows(client, model):
    async def read():
        async with kernel(client).db.sessions() as session:
            return (await session.scalars(select(model))).all()

    return client.portal.call(read)


def sql(client, statement, **params):
    async def run():
        async with kernel(client).db.sessions.begin() as session:
            return await session.execute(text(statement), params)

    return client.portal.call(run)


# --- registration and the shipped definition ----------------------------------------------------


def test_the_shipped_definition_is_registered_at_startup_as_a_draft(client):
    (view,) = call(client, store.list_definitions)
    assert (view["name"], view["version"], view["status"], view["source"]) == (
        "research-review", 1, "draft", "builtin",
    )  # fmt: skip
    assert view["integrity"]["verified"] is True and view["stage_count"] == 4
    assert client.app.state.workflow_seed == [("research-review.v1.json", "created")]


def test_definitions_survive_a_restart_unchanged(client, settings):
    first = call(client, store.get_definition, "research-review", 1)
    call(client, store.register_definition, active_workflow())
    client.__exit__(None, None, None)
    with TestClient(create_app(settings), headers={"Authorization": "Bearer " + TOKEN}) as again:
        assert again.app.state.workflow_seed == [("research-review.v1.json", "unchanged")]
        second = call(again, store.get_definition, "research-review", 1)
        assert second == first  # same id, same bytes, same hash
        assert {v["name"] for v in call(again, store.list_definitions)} == {
            "research-review",
            "demo-flow",
        }


def test_registering_the_same_bytes_again_is_a_no_op_and_different_bytes_are_refused(client):
    view, created = call(client, store.register_definition, active_workflow())
    again, created_again = call(
        client, store.register_definition, json.dumps(active_workflow(), indent=3)
    )
    assert (created, created_again) == (True, False) and again["id"] == view["id"]
    with pytest.raises(store.WorkflowConflict):
        call(client, store.register_definition, active_workflow(description="changed"))
    assert len(rows(client, WorkflowDefinition)) == 2  # the shipped one and this one


def test_multiple_immutable_versions_coexist(client):
    for version in (1, 2, 3):
        call(
            client,
            store.register_definition,
            active_workflow(version=version, title=f"Demo v{version}"),
        )
    versions = call(client, store.list_definitions, "demo-flow")
    assert [v["version"] for v in versions] == [3, 2, 1]
    assert len({v["definition_sha256"] for v in versions}) == 3
    assert call(client, store.get_definition, "demo-flow", 2)["definition"]["title"] == "Demo v2"


def test_concurrent_registration_of_one_version_has_exactly_one_winner(client):
    async def race():
        k = kernel(client)
        attempts = [
            store.register_definition(k, active_workflow(description=f"variant {i}"))
            for i in range(8)
        ]
        return await asyncio.gather(*attempts, return_exceptions=True)

    results = client.portal.call(race)
    created = [r for r in results if not isinstance(r, Exception) and r[1]]
    conflicts = [r for r in results if isinstance(r, store.WorkflowConflict)]
    assert len(created) == 1 and len(conflicts) == 7
    assert len([d for d in rows(client, WorkflowDefinition) if d.name == "demo-flow"]) == 1


def test_concurrent_registration_of_identical_content_is_idempotent(client):
    async def race():
        k = kernel(client)
        return await asyncio.gather(
            *[store.register_definition(k, active_workflow()) for _ in range(8)]
        )

    results = client.portal.call(race)
    assert sum(1 for _, created in results if created) == 1
    assert len({view["id"] for view, _ in results}) == 1


def test_the_unique_constraint_is_the_backstop_when_application_checks_are_bypassed(client):
    call(client, store.register_definition, active_workflow())

    async def duplicate():
        async with kernel(client).db.sessions.begin() as session:
            session.add(
                WorkflowDefinition(
                    name="demo-flow", version=1, schema_version=1, title="x", definition_json={},
                    definition_sha256="0" * 64,
                )
            )  # fmt: skip

    with pytest.raises(IntegrityError):
        client.portal.call(duplicate)


def test_invalid_definitions_are_refused_before_anything_is_stored(client):
    before = len(rows(client, WorkflowDefinition))
    for bad in (
        workflow(stage("a", operation="shell.run")),
        workflow(stage("a", depends_on=["a"])),
        "{",
    ):
        with pytest.raises(DefinitionError):
            call(client, store.register_definition, bad)
    assert len(rows(client, WorkflowDefinition)) == before


def test_registration_events_carry_hashes_not_content(client):
    view, _ = call(client, store.register_definition, active_workflow())
    events = [e for e in rows(client, Event) if e.event_type == "workflow.definition.registered"]
    mine = next(e for e in events if e.payload["name"] == "demo-flow")
    assert mine.payload["definition_sha256"] == view["definition_sha256"]
    assert set(mine.payload) == {
        "definition_id",
        "name",
        "version",
        "definition_sha256",
        "status",
        "source",
    }


# --- activation and lifecycle -------------------------------------------------------------------


def test_activation_requires_every_operation_to_exist(client):
    with pytest.raises(DefinitionError) as error:
        call(
            client,
            store.register_definition,
            SEED_TEXT.replace("research-review", "research-copy"),
            status="active",
        )
    assert "evidence.record" in str(error.value)
    with pytest.raises(DefinitionError):  # a definition is *registered* as draft or active only
        call(client, store.register_definition, seed(), status="superseded")
    with pytest.raises(store.WorkflowConflict):
        call(client, store.set_status, "research-review", 1, "superseded")  # draft -> superseded
    with pytest.raises(DefinitionError):
        call(client, store.set_status, "research-review", 1, "active")  # names an unavailable op


def test_status_moves_forward_only_and_never_touches_the_hashed_content(client):
    view, _ = call(client, store.register_definition, active_workflow())
    assert view["status"] == "draft"
    active = call(client, store.set_status, "demo-flow", 1, "active")
    assert active["status"] == "active" and active["definition_sha256"] == view["definition_sha256"]
    with pytest.raises(store.WorkflowConflict):
        call(client, store.set_status, "demo-flow", 1, "draft")
    call(client, store.set_status, "demo-flow", 1, "superseded")
    call(client, store.set_status, "demo-flow", 1, "archived")
    with pytest.raises(store.WorkflowConflict):
        call(client, store.set_status, "demo-flow", 1, "active")
    assert call(client, store.get_definition, "demo-flow", 1)["integrity"]["verified"] is True


# --- immutability -------------------------------------------------------------------------------


def test_definition_content_cannot_be_changed_through_the_orm(client):
    call(client, store.register_definition, active_workflow())

    async def mutate(**changes):
        async with kernel(client).db.sessions.begin() as session:
            row = await session.scalar(
                select(WorkflowDefinition).where(WorkflowDefinition.name == "demo-flow")
            )
            for name, value in changes.items():
                setattr(row, name, value)

    for changes in (
        {"definition_json": {"stages": []}},
        {"definition_sha256": "f" * 64},
        {"name": "other-flow"},
        {"version": 9},
    ):
        with pytest.raises(ImmutableRecord):
            client.portal.call(lambda changes=changes: mutate(**changes))
    client.portal.call(lambda: mutate(status="archived"))  # lifecycle metadata is the exception


def test_a_definition_can_never_be_deleted(client):
    call(client, store.register_definition, active_workflow())

    async def delete():
        async with kernel(client).db.sessions.begin() as session:
            row = await session.scalar(
                select(WorkflowDefinition).where(WorkflowDefinition.name == "demo-flow")
            )
            await session.delete(row)

    with pytest.raises(ImmutableRecord):
        client.portal.call(delete)


def test_tampering_underneath_the_application_is_detected_on_read(client):
    call(client, store.register_definition, active_workflow())
    assert call(client, store.get_definition, "demo-flow", 1)["integrity"]["verified"] is True
    tampered = json.dumps(copy.deepcopy(workflow(stage("evil"))))
    sql(
        client,
        "UPDATE workflow_definitions SET definition_json = :j WHERE name = 'demo-flow'",
        j=tampered,
    )
    assert call(client, store.get_definition, "demo-flow", 1)["integrity"]["verified"] is False
    assert [
        v["integrity"]["verified"] for v in call(client, store.list_definitions, "demo-flow")
    ] == [False]


def test_the_database_itself_rejects_unknown_statuses_and_states(client):
    call(client, store.register_definition, active_workflow())
    for statement in (
        "UPDATE workflow_definitions SET status = 'rogue' WHERE name = 'demo-flow'",
        "UPDATE workflow_definitions SET version = 0 WHERE name = 'demo-flow'",
    ):
        with pytest.raises(IntegrityError):
            sql(client, statement)


# --- runs and stage records ---------------------------------------------------------------------


def open_run(client, **over):
    call(client, store.register_definition, active_workflow(), status="active")
    return call(
        client, store.open_run, "demo-flow", 1, input_ref="input:1", input_sha256="a" * 64, **over
    )


def test_a_run_needs_an_active_definition_and_gets_one_pending_record_per_stage(client):
    call(client, store.register_definition, active_workflow(), status="draft")
    with pytest.raises(store.WorkflowConflict):
        call(client, store.open_run, "demo-flow", 1)
    call(client, store.set_status, "demo-flow", 1, "active")
    run, created = call(
        client, store.open_run, "demo-flow", 1, input_ref="input:1", input_sha256="b" * 64
    )
    assert created and run["status"] == states.PENDING and run["terminal"] is False
    stages = call(client, store.get_stage_runs, run["id"])
    assert [(s["stage_id"], s["state"], s["attempt"]) for s in stages] == [
        ("prepare", "PENDING", 1), ("check", "PENDING", 1),
    ]  # fmt: skip
    assert {s["type"] for s in stages} == {"deterministic", "validation"}


def test_a_run_keeps_the_exact_definition_it_was_opened_against(client):
    run, _ = open_run(client)
    sha = run["workflow"]["definition_sha256"]
    call(
        client,
        store.register_definition,
        active_workflow(version=2, title="Changed"),
        status="active",
    )
    call(client, store.set_status, "demo-flow", 1, "superseded")
    after = call(client, store.get_run, run["id"])
    assert after["workflow"] == run["workflow"] and after["workflow"]["definition_sha256"] == sha
    assert call(client, store.get_definition, "demo-flow", 1)["definition_sha256"] == sha


def test_history_cannot_be_repointed_or_deleted(client):
    run, _ = open_run(client)

    async def mutate(model, where, **changes):
        async with kernel(client).db.sessions.begin() as session:
            row = await session.scalar(select(model).where(where))
            for name, value in changes.items():
                setattr(row, name, value)

    for changes in (
        {"workflow_version": 2},
        {"definition_sha256": "c" * 64},
        {"workflow_name": "x"},
    ):
        with pytest.raises(ImmutableRecord):
            client.portal.call(
                lambda changes=changes: mutate(WorkflowRun, WorkflowRun.id == run["id"], **changes)
            )
    with pytest.raises(ImmutableRecord):
        client.portal.call(
            lambda: mutate(
                WorkflowStageRun, WorkflowStageRun.run_id == run["id"], operation="shell.run"
            )
        )
    with pytest.raises(IntegrityError):  # RESTRICT: a definition with history cannot be removed
        sql(client, "DELETE FROM workflow_definitions WHERE name = 'demo-flow'")
    with pytest.raises(IntegrityError):
        sql(client, "DELETE FROM workflow_runs WHERE id = :i", i=run["id"])


def test_run_and_stage_state_machines_are_monotonic(client):
    run, _ = open_run(client)
    with pytest.raises(states.IllegalTransition):
        call(client, store.advance_run, run["id"], states.COMPLETED)  # PENDING -> COMPLETED
    call(client, store.advance_run, run["id"], states.RUNNING)
    call(client, store.advance_stage, run["id"], "prepare", states.RUNNING)
    done = call(
        client, store.advance_stage, run["id"], "prepare", states.COMPLETED, output_sha256="d" * 64
    )
    assert done["terminal"] and done["output_sha256"] == "d" * 64 and done["finished_at"]
    with pytest.raises(states.IllegalTransition):
        call(client, store.advance_stage, run["id"], "prepare", states.RUNNING)  # terminal is final
    finished = call(
        client, store.advance_run, run["id"], states.UNKNOWN, reason="ambiguous_dispatch"
    )
    assert finished["terminal"] and finished["terminal_reason"] == "ambiguous_dispatch"
    for later in (states.RUNNING, states.COMPLETED, states.CANCELLED, states.FAILED):
        with pytest.raises(states.IllegalTransition):
            call(client, store.advance_run, run["id"], later)  # UNKNOWN never resumes


def test_stage_records_only_accept_known_fields_and_unique_attempts(client):
    run, _ = open_run(client)
    with pytest.raises(ValueError):
        call(client, store.advance_stage, run["id"], "prepare", states.RUNNING, state="COMPLETED")
    with pytest.raises(ValueError):
        call(
            client, store.advance_stage, run["id"], "prepare", states.RUNNING, operation="shell.run"
        )

    async def second_attempt_one():
        async with kernel(client).db.sessions.begin() as session:
            session.add(
                WorkflowStageRun(
                    run_id=run["id"],
                    stage_id="prepare",
                    attempt=1,
                    stage_type="deterministic",
                    operation="context.prepare",
                )
            )

    with pytest.raises(IntegrityError):
        client.portal.call(second_attempt_one)


def test_a_pi_run_reference_requires_an_existing_receipt(client):
    run, _ = open_run(client)
    call(client, store.advance_run, run["id"], states.RUNNING)
    with pytest.raises(IntegrityError):
        call(
            client,
            store.advance_stage,
            run["id"],
            "prepare",
            states.RUNNING,
            pi_run_id="11111111-1111-1111-1111-111111111111",
        )

    async def receipt():
        from alive.pi.models import PiRun

        async with kernel(client).db.sessions.begin() as session:
            session.add(
                PiRun(
                    id="11111111-1111-1111-1111-111111111111",
                    instance_id=kernel(client).instance_id,
                    operation="cognition.role",
                    idempotency_key="synthetic-workflow-fk",
                    approved_request_json={},
                    approved_request_sha256="0" * 64,
                    requested_json={},
                    token_sha256="0" * 64,
                )
            )

    client.portal.call(receipt)
    stage = call(
        client,
        store.advance_stage,
        run["id"],
        "prepare",
        states.RUNNING,
        pi_run_id="11111111-1111-1111-1111-111111111111",
    )
    assert stage["pi_run_id"] == "11111111-1111-1111-1111-111111111111"


def test_idempotency_keys_never_create_a_second_run(client):
    call(client, store.register_definition, active_workflow(), status="active")
    first, created = call(client, store.open_run, "demo-flow", 1, idempotency_key="k1")
    second, created_again = call(client, store.open_run, "demo-flow", 1, idempotency_key="k1")
    assert (created, created_again) == (True, False) and first["id"] == second["id"]
    assert call(client, store.count_runs) == 1


def test_a_run_links_to_existing_inquiry_identifiers_only(client):
    with pytest.raises(IntegrityError):
        open_run(client, goal_id="not-a-goal")  # the foreign key is real


def test_history_survives_a_restart(client, settings):
    run, _ = open_run(client)
    call(client, store.advance_run, run["id"], states.RUNNING)
    client.__exit__(None, None, None)
    with TestClient(create_app(settings), headers={"Authorization": "Bearer " + TOKEN}) as again:
        assert call(again, store.get_run, run["id"])["status"] == states.RUNNING
        assert len(call(again, store.get_stage_runs, run["id"])) == 2


# --- PI-02A never executes anything -------------------------------------------------------------


def test_registering_inspecting_and_recording_make_no_provider_call_and_start_no_process(
    client, monkeypatch
):
    import asyncio.subprocess as aio_subprocess
    import subprocess

    from alive.providers import MetaProvider

    def forbidden(*args, **kwargs):
        raise AssertionError("workflow code must not call a provider or start a process")

    monkeypatch.setattr(MetaProvider, "structured", forbidden)
    monkeypatch.setattr(MetaProvider, "discover", forbidden)
    monkeypatch.setattr(subprocess, "Popen", forbidden)
    monkeypatch.setattr(asyncio, "create_subprocess_exec", forbidden)
    monkeypatch.setattr(aio_subprocess, "Process", forbidden)
    run, _ = open_run(client)
    call(client, store.advance_run, run["id"], states.RUNNING)
    call(client, store.advance_stage, run["id"], "prepare", states.RUNNING)
    call(client, store.list_definitions)
    call(client, store.get_stage_runs, run["id"])
    for path in (
        "/api/v1/workflows",
        "/api/v1/workflow-operations",
        f"/api/v1/workflow-runs/{run['id']}",
    ):
        assert client.get(path).status_code == 200


def test_the_workflow_package_never_imports_pi_execution_or_a_provider_client():
    import pathlib
    import re

    package = pathlib.Path(store.__file__).parent
    for source in package.glob("*.py"):
        text_ = source.read_text(encoding="utf-8")
        assert not re.search(
            r"^\s*(from|import)\s+alive\.(providers\b|pi\b(?!\.models\b))", text_, re.M
        ), source.name
        assert "MetaProvider" not in text_ and "alive_meta_api_key" not in text_, source.name
