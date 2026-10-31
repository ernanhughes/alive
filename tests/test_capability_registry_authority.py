"""F6/F7: one application registry answers every question; old history never needs it."""

import pytest
import yaml
from fastapi.testclient import TestClient
from sqlalchemy import update

from alive.app import create_app
from alive.capabilities.manifest import parse
from alive.capabilities.registry import CapabilityRegistry, load_registry
from alive.workflows import observatory, store
from alive.workflows.examples import fixture_authorization, stage
from alive.workflows.models import WorkflowExecution
from tests.conftest import MANIFESTS_DIR, TOKEN, _boot
from tests.workflow_execution_helpers import call, lifecycle, observation, prepare


def custom_directory(tmp_path):
    """A YAML-only capability: a new id that reuses an installed trusted implementation."""
    value = yaml.safe_load((MANIFESTS_DIR / "context.prepare@1.0.0.yaml").read_text("utf-8"))
    value["id"] = "context.review"
    directory = tmp_path / "extra"
    directory.mkdir(parents=True)
    (directory / "context.review@1.0.0.yaml").write_text(yaml.safe_dump(value), "utf-8")
    return directory


def review_workflow():
    return {
        "schema_version": 1,
        "name": "yaml-only-review",
        "version": 1,
        "title": "YAML only review",
        "limits": {"max_wall_seconds": 120, "max_model_calls": 0, "max_total_output_tokens": 0},
        "stages": [
            stage(
                "review",
                "context.review",
                "deterministic",
                {"context": "object", "claims": "array", "sources": "array"},
            )
        ],
    }


def test_a_yaml_only_capability_is_consistent_across_every_surface(settings, tmp_path):
    registry = load_registry(custom_directory(tmp_path))
    app = create_app(settings, include_experiments=True, capability_registry=registry)
    _boot(settings)
    with TestClient(app, headers={"Authorization": f"Bearer {TOKEN}"}) as client:
        prepare(client)
        observation(client)

        async def run(k):
            async with client.app.state.cognition.workflow_inquiry() as inquiry:
                grant = await fixture_authorization(
                    k, inquiry, workflow=review_workflow(), model=False
                )
                started = await client.app.state.workflows.start(grant)
                return await client.app.state.workflows.execute(started["id"])

        final = call(client, run)  # registration, grant and execution
        assert final["status"] == "COMPLETED", final

        catalogue = {
            c["id"]: c for c in client.get("/api/v1/capabilities/catalog").json()["capabilities"]
        }
        assert catalogue["context.review"]["workflow_available"] is True

        operations = {
            o["id"]: o for o in client.get("/api/v1/workflow-operations").json()["operations"]
        }
        assert operations["context.review"]["executable"] is True

        graph = client.get("/api/v1/workflows/yaml-only-review/versions/1/graph").json()
        assert graph["nodes"][0]["available"] is True  # was False: default catalogue consulted

        inspection = client.get(f"/api/v1/workflow-runs/{final['id']}/inspection").json()
        assert inspection["run"]["id"] == final["id"]
        stages = client.get(f"/api/v1/workflow-runs/{final['id']}/stages").json()["stages"]
        assert stages[0]["capability"]["id"] == "context.review"


def test_a_definition_graph_marks_a_disabled_capability_unavailable(settings, tmp_path):
    base = load_registry(custom_directory(tmp_path))
    app = create_app(settings, include_experiments=True, capability_registry=base)
    _boot(settings)
    with TestClient(app, headers={"Authorization": f"Bearer {TOKEN}"}) as client:
        prepare(client)
        observation(client)

        async def register(k):
            async with client.app.state.cognition.workflow_inquiry() as inquiry:
                await fixture_authorization(k, inquiry, workflow=review_workflow(), model=False)

        call(client, register)
        client.app.state.kernel.capabilities = load_registry(
            custom_directory(tmp_path / "again"), disabled=("context.review",)
        )
        graph = client.get("/api/v1/workflows/yaml-only-review/versions/1/graph").json()
        assert graph["nodes"][0]["available"] is False


def test_no_production_call_falls_back_to_the_default_catalogue():
    """parse_definition/check_activatable/graph_of default to the built-in map for tests only."""
    import ast
    from pathlib import Path

    root = Path(__file__).resolve().parents[1] / "alive"
    guarded = {"parse_definition", "check_activatable", "graph_of", "check_structure"}
    offenders = []
    for path in root.rglob("*.py"):
        for node in ast.walk(ast.parse(path.read_text(encoding="utf-8"))):
            if not (isinstance(node, ast.Call) and isinstance(node.func, ast.Name)):
                continue
            if node.func.id in guarded and not any(k.arg == "operations" for k in node.keywords):
                # check_activatable/check_structure take it positionally as the second argument.
                if node.func.id in {"check_activatable", "check_structure"} and len(node.args) >= 2:
                    continue
                offenders.append(f"{path.relative_to(root)}:{node.lineno} {node.func.id}")
    assert offenders == []


# --- F7 -----------------------------------------------------------------------------------------


def test_a_pi02_run_without_a_snapshot_stays_inspectable_after_its_operation_is_removed(client):
    prepare(client)
    observation(client)
    final, _ = call(
        client, lambda k: lifecycle(k, client.app.state.cognition, client.app.state.workflows)
    )
    assert final["status"] == "COMPLETED"

    async def become_pre_pi03(k):
        async with k.db.sessions.begin() as session:
            await session.execute(
                update(WorkflowExecution)
                .where(WorkflowExecution.run_id == final["id"])
                .values(capability_snapshot={}, capability_snapshot_sha256=None)
            )
        keep = [
            parse(f.read_text("utf-8"))
            for f in sorted(MANIFESTS_DIR.glob("*.yaml"))
            if not f.name.startswith(("context.prepare", "evidence.evaluate", "result.record"))
        ]
        k.capabilities = CapabilityRegistry(keep)  # the operations this run used are gone

    call(client, become_pre_pi03)
    inspected = call(client, observatory.inspected_run, final["id"])
    assert [n["operation"] for n in inspected["graph"]["nodes"]] == [
        "context.prepare",
        "evidence.evaluate",
        "result.record",
    ]
    stages = call(client, store.get_stage_runs, final["id"])
    assert all("capability" not in s for s in stages)  # never attributed from today's catalogue
    assert client.get(f"/api/v1/workflow-runs/{final['id']}/inspection").status_code == 200


@pytest.mark.parametrize("mode", ["removed", "replaced"])
def test_a_run_with_a_snapshot_keeps_its_own_identity_when_the_catalogue_changes(client, mode):
    prepare(client)
    observation(client)
    final, _ = call(
        client, lambda k: lifecycle(k, client.app.state.cognition, client.app.state.workflows)
    )
    before = call(client, store.get_stage_runs, final["id"])

    async def change(k):
        if mode == "removed":
            keep = [
                parse(f.read_text("utf-8"))
                for f in sorted(MANIFESTS_DIR.glob("*.yaml"))
                if not f.name.startswith("context.prepare")
            ]
            k.capabilities = CapabilityRegistry(keep)
        else:
            value = yaml.safe_load(
                (MANIFESTS_DIR / "context.prepare@1.0.0.yaml").read_text("utf-8")
            )
            value["version"] = "2.0.0"
            value["description"] = "A later revision"
            keep = [parse(f.read_text("utf-8")) for f in sorted(MANIFESTS_DIR.glob("*.yaml"))]
            k.capabilities = CapabilityRegistry([*keep, parse(yaml.safe_dump(value))])

    call(client, change)
    after = call(client, store.get_stage_runs, final["id"])
    assert [s.get("capability") for s in after] == [s.get("capability") for s in before]
    assert after[0]["capability"]["version"] == "1.0.0"
