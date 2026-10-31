"""Fast, direct checks of the contract seam: no app, database or provider."""

import asyncio
import copy
from pathlib import Path
from types import SimpleNamespace

import pytest
import yaml

from alive.capabilities.contracts import ContractError
from alive.capabilities.execution import checked_result, invoke
from alive.capabilities.manifest import ManifestError, parse
from alive.capabilities.registry import CapabilityRegistry, default_registry
from alive.workflows.adapters import StageResult
from alive.workflows.context import Refused
from alive.workflows.examples import stage
from alive.workflows.runner import executable
from alive.workflows.spec import parse_definition
from tests.test_capability_repository_execution import workflow
from tests.workflow_execution_helpers import replace_adapters

MANIFESTS = Path(__file__).resolve().parents[1] / "alive/capabilities/manifests"
GOOD = {"context": {}, "claims": [], "sources": []}


def pinned(operation="context.prepare"):
    registry = default_registry()
    cap = registry.get(operation)
    binding = {
        "identity": cap.identity,
        "manifest": cap.manifest,
        "stage_limits": {"timeout_seconds": 30, "max_output_tokens": 0},
    }
    return registry, binding, registry.grants_for({"s": binding})["s"]


def test_conforming_output_is_accepted_and_detached_from_adapter_state():
    registry, binding, grant = pinned()
    live = StageResult(copy.deepcopy(GOOD))
    checked = checked_result(registry, binding, grant, live)
    live.output["claims"].append({"mutated": "afterwards"})
    assert checked.output == GOOD


@pytest.mark.parametrize(
    "output",
    [
        GOOD | {"surprise": 1},
        {"context": {}, "claims": {}, "sources": []},
        {"context": {}, "claims": []},
    ],
)
def test_output_outside_the_declared_contract_is_refused(output):
    registry, binding, grant = pinned()
    with pytest.raises(ContractError):
        checked_result(registry, binding, grant, StageResult(output))


def test_output_size_ceiling_and_result_type_are_enforced():
    registry, binding, grant = pinned()
    grant["limits"]["max_output_bytes"] = 10
    with pytest.raises(Refused, match="capability_output_limit"):
        checked_result(registry, binding, grant, StageResult(copy.deepcopy(GOOD)))
    _, _, grant = pinned()
    with pytest.raises(Refused, match="capability_result_type"):
        checked_result(registry, binding, grant, copy.deepcopy(GOOD))


def test_a_capability_without_the_writer_permission_cannot_return_an_artifact():
    registry, binding, grant = pinned()
    with pytest.raises(Refused, match="capability_writer_not_authorized"):
        checked_result(
            registry, binding, grant, StageResult(copy.deepcopy(GOOD), artifact={"kind": "x"})
        )


def test_input_outside_the_declared_contract_is_refused_before_invocation(monkeypatch):
    registry, binding, grant = pinned()
    called = []

    async def adapter(context):
        called.append(context)

    replace_adapters(monkeypatch, {"context.prepare": adapter})
    context = SimpleNamespace(inputs={"unexpected": 1}, approved={})
    with pytest.raises(ContractError):
        asyncio.run(invoke(registry, binding, grant, context))
    assert not called


def test_stage_may_not_exceed_the_capability_timeout_or_pin_another_hash():
    registry = default_registry()
    raw = workflow()
    raw["stages"][0]["limits"]["timeout_seconds"] = 45
    with pytest.raises(ManifestError, match="exceeds capability contract"):
        registry.bind(parse_definition(raw, operations=registry.operations))
    raw["stages"][0]["limits"]["timeout_seconds"] = 30
    raw["stages"][0]["capability_version"] = "1.0.0"
    raw["stages"][0]["capability_sha256"] = "0" * 64
    with pytest.raises(ManifestError, match="hash mismatch"):
        registry.bind(parse_definition(raw, operations=registry.operations))
    raw["stages"][0]["capability_sha256"] = registry.get("repository.inspect").manifest_sha256
    assert registry.bind(parse_definition(raw, operations=registry.operations))


def declared(**changes):
    value = yaml.safe_load((MANIFESTS / "context.prepare@1.0.0.yaml").read_text(encoding="utf-8"))
    return value | changes


def test_grant_cannot_change_permissions_or_widen_limits():
    registry, binding, grant = pinned()
    assert registry.check_grant(binding, grant)  # control: the minted grant is accepted
    broader = copy.deepcopy(grant)
    broader["permissions"]["persistence"] = "workflow_result"
    with pytest.raises(ManifestError, match="permissions not approved"):
        registry.check_grant(binding, broader)
    wider = copy.deepcopy(grant)
    wider["limits"]["timeout_seconds"] += 1
    with pytest.raises(ManifestError, match="cannot widen"):
        registry.check_grant(binding, wider)


def test_deployment_configuration_may_narrow_but_never_widen_a_manifest_limit():
    manifest = parse(yaml.safe_dump(declared()))
    narrowed = CapabilityRegistry([manifest], limits={"context.prepare": {"timeout_seconds": 5}})
    assert narrowed.limits_for(narrowed.get("context.prepare"))["timeout_seconds"] == 5
    with pytest.raises(ManifestError, match="cannot widen"):
        CapabilityRegistry([manifest], limits={"context.prepare": {"timeout_seconds": 3601}})


def test_runner_checks_the_pinned_version_not_merely_the_latest():
    one = parse(yaml.safe_dump(declared()))
    two = parse(yaml.safe_dump(declared(version="2.0.0")))
    registry = CapabilityRegistry([one, two], disabled=("context.prepare@1.0.0",))
    grant = SimpleNamespace(
        operations=("context.prepare",),
        max_model_calls=0,
        max_output_tokens=0,
        wall_seconds=60,
        inputs={},
    )
    raw = {
        "schema_version": 1,
        "name": "pinned-version",
        "version": 1,
        "title": "Pinned version",
        "limits": {"max_wall_seconds": 120, "max_model_calls": 0, "max_total_output_tokens": 0},
        "stages": [
            stage(
                "prepare",
                "context.prepare",
                "deterministic",
                {"context": "object", "claims": "array", "sources": "array"},
            )
        ],
    }
    raw["stages"][0]["capability_version"] = "1.0.0"
    spec = parse_definition(raw, operations=registry.operations)
    with pytest.raises(Refused, match="operation_not_authorized_or_executable"):
        executable(spec, grant, registry)
    raw["stages"][0]["capability_version"] = "2.0.0"
    executable(parse_definition(raw, operations=registry.operations), grant, registry)
