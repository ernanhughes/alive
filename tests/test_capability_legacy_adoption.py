"""F4: only genuinely historical definitions get the DAG-only contract; runtime enforces both."""

import copy

import pytest
from sqlalchemy import func, select

from alive.capabilities.trusted import LEGACY_DEFINITION_SHA256
from alive.workflows.examples import definition, fixture_authorization, stage
from alive.workflows.models import WorkflowCapabilityBinding, WorkflowDefinition
from alive.workflows.runner import output_valid
from alive.workflows.spec import (
    DefinitionError,
    definition_sha256,
    parse_definition,
)
from alive.workflows.store import builtin_definitions, register_definition
from tests.workflow_execution_helpers import (
    call,
    insert_historical,
    observation,
    prepare,
    replace_adapters,
)

BAD = {"context": {}, "claims": [], "sources": [], "extra": "x"}


def contrived(name="legacy-shape", version=1, pin=None):
    """A valid DAG whose stage declares an optional field the capability manifest does not."""
    raw = copy.deepcopy(definition(model=False))
    raw["name"], raw["version"] = name, version
    first = raw["stages"][0]
    first["output_schema"]["properties"]["extra"] = {"type": "string"}  # optional in the DAG
    if pin:
        first["capability_version"] = pin
    return raw


async def bindings(kernel, name):
    async with kernel.db.sessions() as session:
        row = await session.scalar(
            select(WorkflowCapabilityBinding)
            .join(
                WorkflowDefinition,
                WorkflowDefinition.id == WorkflowCapabilityBinding.definition_id,
            )
            .where(WorkflowDefinition.name == name)
        )
        return row.snapshot["stages"] if row else None


async def definition_count(kernel, name):
    async with kernel.db.sessions() as session:
        return await session.scalar(
            select(func.count())
            .select_from(WorkflowDefinition)
            .where(WorkflowDefinition.name == name)
        )


@pytest.mark.parametrize("pin", [None, "1.0.0"])
def test_a_new_definition_must_meet_the_full_capability_contract(client, pin):
    raw = contrived(pin=pin)
    with pytest.raises(DefinitionError, match="capability contract"):
        call(client, register_definition, raw, status="draft")
    # Refusal is atomic: no definition row survives without its binding.
    assert call(client, definition_count, "legacy-shape") == 0


def test_a_genuinely_historical_definition_is_adopted_under_its_original_contract(client):
    raw = contrived()
    call(client, insert_historical, raw)
    assert call(client, bindings, "legacy-shape") is None  # nothing retained yet
    view, created = call(client, register_definition, raw, status="active")
    assert created is False
    stages = call(client, bindings, "legacy-shape")
    assert stages["prepare"]["legacy_contract"] is True
    assert stages["prepare"]["identity"]["id"] == "context.prepare"


def test_a_historical_definition_that_pins_a_capability_is_not_adopted(client):
    raw = contrived(name="legacy-pinned", pin="1.0.0")
    call(client, insert_historical, raw)
    with pytest.raises(DefinitionError, match="capability contract"):
        call(client, register_definition, raw, status="active")
    assert call(client, bindings, "legacy-pinned") is None


def test_adoption_is_limited_to_legacy_operations_even_for_a_historical_row(client):
    """A new-style operation never inherits the old, looser contract."""
    raw = {
        "schema_version": 1,
        "name": "historical-repository",
        "version": 1,
        "title": "Historical repository",
        "inputs": {"repository_ref": {"type": "string"}, "paths": {"type": "array"}},
        "limits": {"max_wall_seconds": 120, "max_model_calls": 0, "max_total_output_tokens": 0},
        "stages": [
            stage(
                "inspect",
                "repository.inspect",
                "deterministic",
                {"files": "array", "surprise": "string"},  # undeclared by the manifest
                inputs={"repository_ref": "$input.repository_ref", "paths": "$input.paths"},
            )
        ],
    }
    raw["stages"][0]["limits"]["timeout_seconds"] = 30
    call(client, insert_historical, raw)
    with pytest.raises(DefinitionError, match="capability contract"):
        call(client, register_definition, raw, status="active")


def test_shipped_definitions_are_adopted_only_because_their_exact_hash_is_allowlisted(client):
    from alive.intelligence.fixture import DEFINITION

    shipped = dict(builtin_definitions())["research-review.v1.json"]
    for raw in (shipped, DEFINITION):
        digest = definition_sha256(parse_definition(raw))
        assert digest in LEGACY_DEFINITION_SHA256  # editing a shipped file must be a reviewed act
    assert call(client, bindings, "research-review")["prepare"]["legacy_contract"] is True
    assert len(LEGACY_DEFINITION_SHA256) == 2  # a new entry must come with a new test line here


def test_runtime_still_enforces_the_capability_contract_on_an_adopted_definition(
    client, monkeypatch
):
    prepare(client)
    observation(client)
    raw = contrived(name="legacy-runtime")
    spec = parse_definition(raw)
    output_valid(spec.stages[0], BAD)  # the old, DAG-only contract accepts this output

    async def overreach(_):
        from alive.workflows.adapters import StageResult

        return StageResult(dict(BAD))

    replace_adapters(monkeypatch, {"context.prepare": overreach})
    call(client, insert_historical, raw)

    async def run(k):
        async with client.app.state.cognition.workflow_inquiry() as inquiry:
            grant = await fixture_authorization(k, inquiry, workflow=raw, model=False)
            started = await client.app.state.workflows.start(grant)
            return await client.app.state.workflows.execute(started["id"])

    final = call(client, run)
    assert final["status"] == "FAILED"
    assert final["terminal_reason"] == "output_validation_failure"
