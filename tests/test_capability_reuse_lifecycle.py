"""F8: each trusted implementation, reused under a different capability id, has a full lifecycle.

Execute, persist, observe, inspect and link, with the real runner and (for the model role) the
real pinned Pi against a scripted provider. The original operation ids are absent from the
catalogue, so nothing can fall back to a hardcoded name.
"""

import copy

import pytest
import yaml
from fastapi.testclient import TestClient

from alive.app import create_app
from alive.capabilities.manifest import ManifestError, parse
from alive.capabilities.registry import CapabilityRegistry
from alive.capabilities.trusted import TRUSTED, traits_of
from alive.workflows import observatory, store
from alive.workflows.examples import definition, fixture_authorization
from tests.conftest import MANIFESTS_DIR, TOKEN, _boot
from tests.workflow_execution_helpers import call, observation, prepare
from tests.workflow_r2_helpers import pi_environment

RENAMES = {
    "context.prepare": "review.assemble",
    "cognition.role": "review.reason",
    "evidence.validate_references": "review.check",
    "evidence.evaluate": "review.compare",
    "result.record": "review.record",
}


def renamed_registry():
    manifests = []
    for file in sorted(MANIFESTS_DIR.glob("*.yaml")):
        value = yaml.safe_load(file.read_text(encoding="utf-8"))
        value["id"] = RENAMES.get(value["id"], value["id"])
        manifests.append(parse(yaml.safe_dump(value, sort_keys=False)))
    return CapabilityRegistry(manifests)


def renamed_workflow(model):
    raw = copy.deepcopy(definition(model=model))
    for item in raw["stages"]:
        item["operation"] = RENAMES[item["operation"]]
    return raw


@pytest.fixture
def renamed_client(settings):
    app = create_app(settings, include_experiments=True, capability_registry=renamed_registry())
    _boot(settings)
    with TestClient(app, headers={"Authorization": f"Bearer {TOKEN}"}) as client:
        yield client


async def execute(client, raw, *, model):
    async with client.app.state.cognition.workflow_inquiry() as inquiry:
        grant = await fixture_authorization(
            client.app.state.kernel, inquiry, workflow=raw, model=model
        )
        started = await client.app.state.workflows.start(grant)
        return await client.app.state.workflows.execute(started["id"])


def test_prepare_compare_and_record_work_under_new_ids(renamed_client):
    client = renamed_client
    prepare(client)
    observation(client)
    final = call(client, lambda k: execute(client, renamed_workflow(False), model=False))
    assert final["status"] == "COMPLETED", final
    stages = client.get(f"/api/v1/workflow-runs/{final['id']}/stages").json()["stages"]
    assert [s["capability"]["id"] for s in stages] == [
        "review.assemble",
        "review.compare",
        "review.record",
    ]
    # compare passed its contract check, but evaluating is not checking citation identity.
    compare = stages[1]["validation"]
    assert compare["contract_status"] == "passed"
    assert compare["reference_identity_status"] == "not_established"
    # The writer's artifact is served because its retained implementation is the writer.
    artifact = client.get(f"/api/v1/workflow-runs/{final['id']}/artifacts/record")
    assert artifact.status_code == 200 and artifact.json()["assessment"]["semantic_status"]
    assert client.get(f"/api/v1/workflow-runs/{final['id']}/inspection").status_code == 200


def test_the_model_role_and_reference_validation_work_under_new_ids(
    renamed_client, settings, monkeypatch
):
    client = renamed_client
    upstream = pi_environment(client, settings, monkeypatch)
    final = call(client, lambda k: execute(client, renamed_workflow(True), model=True))
    assert final["status"] == "COMPLETED", final
    assert len(upstream.calls) == 1  # one scripted provider request, no real inference
    stages = {
        s["stage_id"]: s
        for s in client.get(f"/api/v1/workflow-runs/{final['id']}/stages").json()["stages"]
    }
    assert stages["analyze"]["capability"]["id"] == "review.reason"
    assert stages["validate"]["capability"]["id"] == "review.check"
    # Reference identity is claimed because of the retained implementations, not the ids.
    assert stages["analyze"]["validation"]["reference_identity_status"] == "passed"
    assert stages["validate"]["validation"]["reference_identity_status"] == "passed"
    assert stages["prepare"]["validation"]["reference_identity_status"] == "not_established"
    # The Pi run is attached to the stage under the new id.
    inspected = call(client, observatory.inspected_run, final["id"])
    assert inspected["pi_links"].get(stages["analyze"]["id"])
    assert client.get(f"/api/v1/workflow-runs/{final['id']}/artifacts/record").status_code == 200
    # The record stage accepted its dependency as independent validation by implementation.
    assert stages["record"]["capability"]["id"] == "review.record"
    call(client, store.get_stage_runs, final["id"])


def test_traits_belong_to_reviewed_code_and_cannot_be_declared_in_yaml():
    assert "result.writer" in traits_of("result-record-v1")
    assert traits_of("context-prepare-v1") == frozenset()
    assert traits_of("not-installed") == frozenset()
    value = yaml.safe_load((MANIFESTS_DIR / "context.prepare@1.0.0.yaml").read_text("utf-8"))
    value["traits"] = ["result.writer"]
    with pytest.raises(ManifestError):
        parse(yaml.safe_dump(value))
    value.pop("traits")
    value["implementation"]["traits"] = ["result.writer"]
    with pytest.raises(ManifestError):
        parse(yaml.safe_dump(value))


def test_a_trait_change_changes_the_fingerprint():
    import dataclasses

    base = TRUSTED["result-record-v1"]
    assert dataclasses.replace(base, traits=frozenset()).fingerprint() != base.fingerprint()


# --- the guards behind the traits ---------------------------------------------------------------


def record_context(implementation):
    from types import SimpleNamespace

    inputs = {"result": {"r": 1}, "assessment": {"a": 1}}
    return SimpleNamespace(
        inputs=inputs,
        dependencies={
            "check": {
                "operation": "whatever.the.id.is",
                "implementation": implementation,
                "validation_status": "passed",
                "output": dict(inputs),
            }
        },
        run_id="run",
        stage_id="stage-row",
        stage=SimpleNamespace(id="record"),
        definition_hash="d" * 64,
        input_hash="i" * 64,
        approved={"source_event_ids": ["e1"]},
    )


@pytest.mark.parametrize(
    "implementation,accepted",
    [
        ("validate-references-v1", True),
        ("evidence-evaluate-v1", True),
        ("context-prepare-v1", False),  # a passed stage that is not an independent validator
        ("cognition-role-v1", False),  # a model's own output cannot validate itself
        ("not-installed-v1", False),
    ],
)
def test_record_accepts_a_dependency_by_what_it_ran_not_by_its_operation_id(
    implementation, accepted
):
    import asyncio

    from alive.workflows import adapters
    from alive.workflows.context import Refused

    if accepted:
        result = asyncio.run(adapters.record(record_context(implementation)))
        assert result.artifact["kind"] == "workflow_result"
    else:
        with pytest.raises(Refused, match="independent_validation_dependency_required"):
            asyncio.run(adapters.record(record_context(implementation)))


def test_only_a_stage_whose_implementation_writes_results_serves_an_artifact(renamed_client):
    client = renamed_client
    prepare(client)
    observation(client)
    final = call(client, lambda k: execute(client, renamed_workflow(False), model=False))
    assert client.get(f"/api/v1/workflow-runs/{final['id']}/artifacts/record").status_code == 200
    from alive.workflows.context import Refused
    from alive.workflows.runner import artifact_view

    for stage_id in ("prepare", "compare"):  # completed, but they are not result writers
        # The route maps every failure to one 404, which would hide an accidental crash, so the
        # reason is asserted where it is raised: an explicit refusal, not a KeyError.
        with pytest.raises(Refused, match="artifact_unavailable"):
            call(client, artifact_view, final["id"], stage_id)
        url = f"/api/v1/workflow-runs/{final['id']}/artifacts/{stage_id}"
        assert client.get(url).status_code == 404
