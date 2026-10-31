"""F1/F2: the runner executes the implementation its binding names, and that identity is exact."""

import dataclasses
import json
from pathlib import Path

import pytest
import yaml
from fastapi.testclient import TestClient
from sqlalchemy import select

from alive.app import create_app
from alive.capabilities import trusted
from alive.capabilities.manifest import parse
from alive.capabilities.registry import CapabilityRegistry
from alive.capabilities.trusted import TRUSTED, TrustedImplementation
from alive.models import Event
from alive.workflows import store
from alive.workflows.examples import fixture_authorization, stage
from tests.conftest import TOKEN, _boot
from tests.workflow_execution_helpers import call, observation, prepare

MANIFESTS = Path(__file__).resolve().parents[1] / "alive/capabilities/manifests"
ALTERNATIVE = "context-prepare-alternative-v1"
BASE = TRUSTED["context-prepare-v1"]


def alternative():
    """A second reviewed implementation with the same ceiling but different code."""
    return dataclasses.replace(
        BASE,
        id=ALTERNATIVE,
        adapter="tests.fixture_adapters:marker_prepare",
        source_files=("tests/fixture_adapters.py",),
    )


def declared(version="1.0.0", implementation="context-prepare-v1"):
    value = yaml.safe_load((MANIFESTS / "context.prepare@1.0.0.yaml").read_text(encoding="utf-8"))
    value["version"] = version
    value["implementation"]["id"] = implementation
    return parse(yaml.safe_dump(value, sort_keys=False))


def builtin_manifests():
    return [parse(f.read_text(encoding="utf-8")) for f in sorted(MANIFESTS.glob("*.yaml"))]


def registry_with(*prepare_versions):
    """Built-ins minus context.prepare, plus the given (version, implementation) pairs."""
    others = [m for m in builtin_manifests() if m.id != "context.prepare"]
    mine = [declared(version, impl) for version, impl in prepare_versions]
    return CapabilityRegistry(
        [*others, *mine], implementations={**TRUSTED, ALTERNATIVE: alternative()}
    )


def single_stage(version=None):
    raw = {
        "schema_version": 1,
        "name": "rebound-prepare",
        "version": 1,
        "title": "Rebound prepare",
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
    if version:
        raw["stages"][0]["capability_version"] = version
        raw["version"] = int(version[0]) + 1  # a different pin is a different definition
    return raw


def run_workflow(settings, registry, raw):
    app = create_app(settings, include_experiments=True, capability_registry=registry)
    _boot(settings)
    with TestClient(app, headers={"Authorization": f"Bearer {TOKEN}"}) as client:
        prepare(client)
        observation(client)

        async def run(k):
            async with client.app.state.cognition.workflow_inquiry() as inquiry:
                grant = await fixture_authorization(k, inquiry, workflow=raw, model=False)
                started = await client.app.state.workflows.start(grant)
                return await client.app.state.workflows.execute(started["id"])

        final = call(client, run)
        (stage_run,) = call(client, store.get_stage_runs, final["id"])

        async def output(k):
            async with k.db.sessions() as session:
                event = await session.scalar(
                    select(Event).where(Event.id == stage_run["output_ref"][6:])
                )
                return event.payload["output"]

        return final, stage_run, call(client, output) if stage_run["output_ref"] else None


def test_runner_executes_the_implementation_the_binding_names_not_the_global_default(settings):
    # The only context.prepare in this catalogue is bound to the alternative implementation.
    final, stage_run, output = run_workflow(
        settings, registry_with(("1.0.0", ALTERNATIVE)), single_stage()
    )
    assert final["status"] == "COMPLETED", final
    assert output["context"] == {"marker": "bound-alternative"}
    assert stage_run["capability"]["implementation_id"] == ALTERNATIVE


def test_a_pinned_older_version_runs_its_own_implementation_while_a_newer_one_exists(settings):
    registry = registry_with(("1.0.0", "context-prepare-v1"), ("2.0.0", ALTERNATIVE))
    final, stage_run, output = run_workflow(settings, registry, single_stage("1.0.0"))
    assert final["status"] == "COMPLETED", final
    assert stage_run["capability"]["version"] == "1.0.0"
    assert output["context"] != {"marker": "bound-alternative"}  # the real prepare ran
    final, stage_run, output = run_workflow(settings, registry, single_stage("2.0.0"))
    assert output["context"] == {"marker": "bound-alternative"}


def test_the_runtime_has_no_way_to_substitute_a_callback():
    import inspect

    from alive.capabilities.execution import invoke

    assert "adapter" not in inspect.signature(invoke).parameters
    import alive.workflows.adapters as adapters
    import alive.workflows.runner as runner

    assert not hasattr(adapters, "ADAPTERS") and not hasattr(runner, "ADAPTERS")


def test_a_changed_implementation_mapping_makes_a_pinned_identity_refuse():
    first = registry_with(("1.0.0", "context-prepare-v1"))
    pinned = first.get("context.prepare").identity
    # Same id, kind, effects, permissions and source: only the selected adapter differs.
    moved = dataclasses.replace(BASE, adapter="alive.workflows.adapters:record")
    second = CapabilityRegistry(
        [*[m for m in builtin_manifests() if m.id != "context.prepare"], declared()],
        implementations={**TRUSTED, "context-prepare-v1": moved},
    )
    assert (
        second.get("context.prepare").identity["implementation_sha256"]
        != pinned["implementation_sha256"]
    )
    with pytest.raises(ValueError):
        second.adapter_for(pinned)
    assert first.adapter_for(pinned)


@pytest.mark.parametrize(
    "change",
    [
        {"adapter": "alive.workflows.adapters:record"},
        {"kind": "validation"},
        {"side_effects": "write"},
        {"legacy_binding": "alive.somewhere:different"},
        {"interface": "stage-context/v2"},
        {"permission_ceiling": frozenset({"evidence.read", "workflow.write"})},
        {"source_files": ("alive/workflows/adapters.py",)},
    ],
)
def test_every_field_that_selects_code_changes_the_fingerprint(change):
    assert dataclasses.replace(BASE, **change).fingerprint() != BASE.fingerprint()


def test_actual_source_bytes_change_the_fingerprint_but_line_endings_do_not(tmp_path, monkeypatch):
    monkeypatch.setattr(trusted, "ROOT", tmp_path)
    (tmp_path / "a.py").write_bytes(b"def f():\n    return 1\n")
    impl = TrustedImplementation(
        "x-v1", "deterministic", "read", "a:f", None, None, frozenset(), ("a.py",)
    )
    before = impl.fingerprint()
    (tmp_path / "a.py").write_bytes(b"def f():\r\n    return 1\r\n")
    assert impl.fingerprint() == before
    (tmp_path / "a.py").write_bytes(b"def f():\n    return 2\n")
    assert impl.fingerprint() != before


def test_fingerprint_covers_the_helper_module_that_the_record_adapter_depends_on():
    assert "alive/workflows/context.py" in TRUSTED["result-record-v1"].source_files
    assert json.loads(json.dumps(sorted(TRUSTED)))  # the allowlist stays plain data
