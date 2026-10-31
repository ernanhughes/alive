"""Actual registry, custody, scoped grants, runner, artifacts and historical projections."""

import pytest

from alive.capabilities.registry import default_registry
from alive.cognitive_models import CognitiveMessage
from alive.models import uid
from alive.sources import custody, documents
from alive.validation.workflows import definition
from alive.workflows import store
from alive.workflows.context import Refused
from alive.workflows.examples import fixture_authorization
from tests.test_validation_capabilities import inputs
from tests.workflow_execution_helpers import call, observation, prepare


async def approved(kernel, text, kind, operations):
    if kind == "repository":
        # Reuse the real capture builder rather than guessing its content contract.
        from tests.test_source_custody import repo_content

        content = repo_content({"a.py": text})
    else:
        content = documents.extract(text.encode(), "markdown")
    row = await custody.create_capture(
        kernel,
        source_type=kind,
        label="Synthetic validation",
        locator="synthetic-only",
        classification="owner_internal",
        capture_method="test",
        content=content,
    )
    approval = await custody.approve(
        kernel,
        row["id"],
        confirm_sha256=row["content_sha256"],
        operations=operations,
        scope={"all": True},
        ttl_seconds=3600,
        principal="independent-fixture-owner",
        request_id=uid(),
    )
    source = await custody.resolve(kernel, approval["resources"], operations[0])
    batch = inputs(source, locator="none", start=0, end=0, quote="")
    if kind == "repository":
        batch["findings"][0]["evidence"][0]["locator"] = {
            "kind": "file_lines",
            "start": 1,
            "end": 1,
            "quote": text.splitlines()[0],
        }
    else:
        batch["findings"][0]["evidence"][0]["locator"] = {
            "kind": "section",
            "start": 0,
            "end": 0,
            "quote": "",
        }
    return approval, batch


async def execute(kernel, client, raw, parameters, resources, *, between=None):
    async with client.app.state.cognition.workflow_inquiry() as inquiry:
        grant = await fixture_authorization(
            kernel,
            inquiry,
            model=False,
            workflow=raw,
            changes={"inputs": parameters},
            resources=resources,
        )
        run = await client.app.state.workflows.start(grant)
        if between:
            await between(kernel)
        finished = await client.app.state.workflows.execute(run["id"])
        return finished, await store.get_stage_runs(kernel, run["id"])


@pytest.mark.parametrize("kind", ["repository", "document", "comparison"])
def test_distinct_deterministic_workflows_run_and_replay_without_inference(client, kind):
    prepare(client)
    observation(client)
    raw = definition(kind)

    async def scenario(kernel):
        if kind == "comparison":
            a, left = await approved(
                kernel, "alpha\n", "repository", ["evidence.validate_references"]
            )
            b, right = await approved(
                kernel, "beta\n", "repository", ["evidence.validate_references"]
            )
            parameters = {
                f"{side}_{key}": value
                for side, batch in (("left", left), ("right", right))
                for key, value in batch.items()
            }
            parameters.update(
                fields=[],
                left_id=left["findings"][0]["evidence"][0]["id"],
                right_id=right["findings"][0]["evidence"][0]["id"],
            )
            resources = {"left": a["resources"], "right": b["resources"]}
        else:
            operations = (
                ["repository.inspect", "evidence.validate_references", "evidence.verify-locators"]
                if kind == "repository"
                else ["document.extract", "evidence.verify-locators"]
            )
            approval, parameters = await approved(
                kernel,
                "alpha\n" if kind == "repository" else "# Synthetic\nalpha\n",
                kind,
                operations,
            )
            resources = {
                stage["id"]: approval["resources"]
                for stage in raw["stages"]
                if stage["id"] not in {"compose", "record"}
            }
            if kind == "repository":
                parameters["paths"] = ["a.py"]
        result, stages = await execute(kernel, client, raw, parameters, resources)
        assert result["status"] == "COMPLETED", [
            (s["stage_id"], s["state"], s.get("error_detail")) for s in stages
        ]
        assert await client.app.state.workflows.execute(result["id"]) == result
        async with kernel.db.sessions() as session:
            record = next(stage for stage in stages if stage["stage_id"] == "record")
            artifact = (await session.get(CognitiveMessage, record["id"])).content
        assert artifact["result"]["records"]["validation"]["semantic_support"] == "unverified"
        assert artifact["assessment"]["independent_verification"] is False
        if kind == "comparison":
            assert artifact["result"]["records"]["comparison"]["status"] == "changed"
        return result, stages

    result, stages = call(client, scenario)
    assert all(
        stage["model_invocation_id"] is None and stage["pi_run_id"] is None for stage in stages
    )
    response = client.get(f"/api/v1/workflow-runs/{result['id']}/inspection")
    assert response.status_code == 200


def test_old_implicit_reference_definition_keeps_its_original_implementation():
    from alive.workflows.examples import definition as old
    from alive.workflows.spec import parse_definition

    registry = default_registry()
    from alive.capabilities.manifest import ManifestError

    try:
        bindings = registry.bind(parse_definition(old(model=True), operations=registry.operations))
    except ManifestError:
        bindings = {}
    assert bindings.get("validate", {}).get("identity", {}).get("version") == "1.0.0"
    assert bindings["validate"]["identity"]["implementation_id"] == "validate-references-v1"
    assert (
        registry.get("evidence.validate_references", "1.1.0").identity["implementation_id"]
        == "captured-references-v1"
    )


@pytest.mark.parametrize("fault", ["withdrawn", "scope_digest", "source_ref", "cancelled"])
def test_custody_and_cancellation_remain_enforced_at_execution(client, fault):
    prepare(client)
    observation(client)
    raw = definition("repository")

    async def scenario(kernel):
        approval, parameters = await approved(
            kernel,
            "alpha\n",
            "repository",
            [
                "repository.inspect",
                "evidence.validate_references",
                "evidence.verify-locators",
            ],
        )
        parameters["paths"] = ["a.py"]
        resources = {name: approval["resources"] for name in ("read", "references", "locators")}
        control, _ = await execute(kernel, client, raw, parameters, resources)
        assert control["status"] == "COMPLETED"
        return approval, parameters, resources, control["id"]

    approval, parameters, resources, original = call(client, scenario)
    observation(client)

    async def attack(kernel):
        async with client.app.state.cognition.workflow_inquiry() as inquiry:
            changed = dict(parameters)
            if fault == "scope_digest":
                changed["scoped_sha256"] = "0" * 64
            elif fault == "source_ref":
                changed["source_ref"] = uid()
            grant = await fixture_authorization(
                kernel,
                inquiry,
                model=False,
                workflow=raw,
                changes={"inputs": changed},
                resources=resources,
            )
            run = await client.app.state.workflows.start(grant)
            if fault == "withdrawn":
                await custody.withdraw(
                    kernel,
                    approval["id"],
                    reason="synthetic withdrawal",
                    principal="independent-fixture-owner",
                )
            elif fault == "cancelled":
                await client.app.state.workflows.cancel(run["id"])
            result = await client.app.state.workflows.execute(run["id"])
            assert result["status"] == ("CANCELLED" if fault == "cancelled" else "FAILED")

    call(client, attack)
    # Withdrawal/failure/cancellation never rewrites the completed version or its report.
    assert client.get(f"/api/v1/workflow-runs/{original}/artifacts/record").status_code == 200


def test_validation_source_cannot_cross_instances(client):
    import copy

    async def scenario(kernel):
        approval, _ = await approved(kernel, "alpha\n", "repository", ["evidence.verify-locators"])
        assert await custody.resolve(kernel, approval["resources"], "evidence.verify-locators")
        foreign = copy.copy(kernel)
        foreign.instance_id = uid()
        with pytest.raises(Refused, match="source_instance_mismatch"):
            await custody.resolve(foreign, approval["resources"], "evidence.verify-locators")

    call(client, scenario)


def test_disabling_the_new_contract_does_not_change_an_old_implicit_binding():
    from alive.capabilities.registry import load_registry
    from alive.workflows.examples import definition as old
    from alive.workflows.spec import parse_definition

    registry = load_registry(disabled=("evidence.validate_references@1.1.0",))
    assert not registry.get("evidence.validate_references", "1.1.0").executable
    assert registry.get("evidence.validate_references", "1.0.0").executable
    spec = parse_definition(old(model=True), operations=registry.operations)
    assert registry.bind(spec)["validate"]["identity"]["version"] == "1.0.0"
