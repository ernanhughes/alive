"""ALIVE-PI-02A: the read-only inspection API: authenticated, shaped, leak-free, never writable."""

import json

import pytest
from fastapi.testclient import TestClient

from alive.workflows import states, store
from tests.conftest import TOKEN
from tests.test_workflows_spec import stage, workflow

REAL_KEY = "sk-real-meta-credential-that-must-never-appear"


@pytest.fixture
def settings(settings):
    settings.alive_meta_api_key = REAL_KEY
    return settings


def call(client, fn, *args, **kwargs):
    return client.portal.call(lambda: fn(client.app.state.kernel, *args, **kwargs))


def demo(version=1):
    return workflow(
        stage("prepare"),
        stage(
            "check",
            operation="evidence.validate_references",
            type="validation",
            depends_on=["prepare"],
        ),
        name="demo-flow",
        version=version,
    )


@pytest.fixture
def run(client):
    call(client, store.register_definition, demo(), status="active")
    opened, _ = call(
        client, store.open_run, "demo-flow", 1, input_ref="input:42", input_sha256="a" * 64
    )
    call(client, store.advance_run, opened["id"], states.RUNNING)
    call(client, store.advance_stage, opened["id"], "prepare", states.RUNNING)
    return opened


READ_PATHS = [
    "/api/v1/workflow-operations",
    "/api/v1/workflows",
    "/api/v1/workflows/research-review",
    "/api/v1/workflows/research-review/versions/1",
    "/api/v1/workflows/research-review/versions/1/graph",
    "/api/v1/workflow-runs",
    "/api/v1/workflow-runs/00000000-0000-0000-0000-000000000000",
    "/api/v1/workflow-runs/00000000-0000-0000-0000-000000000000/stages",
]


# --- authentication -----------------------------------------------------------------------------


@pytest.mark.parametrize("path", READ_PATHS)
def test_every_read_requires_the_bearer_token(client, path):
    anonymous = TestClient(client.app)
    assert anonymous.get(path).status_code == 401
    wrong = TestClient(client.app, headers={"Authorization": "Bearer not-the-token"})
    assert wrong.get(path).status_code == 401
    assert client.get(path).status_code in (200, 404)  # authorised: found, or honestly unknown


@pytest.mark.parametrize("path", READ_PATHS)
@pytest.mark.parametrize("method", ["post", "put", "patch", "delete"])
def test_there_is_no_way_to_create_change_run_or_delete_anything(client, path, method):
    response = client.request(method.upper(), path, json={"name": "evil-flow"})
    assert response.status_code in (404, 405)


def test_no_execution_or_model_route_exists_under_the_workflow_prefixes(client):
    paths = {
        path: sorted(methods)
        for path, methods in client.app.openapi()["paths"].items()
        if "workflow" in path
    }
    assert len(paths) == 9, paths
    assert paths["/api/v1/workflow-runs/{run_id}/artifacts/{stage_id}"] == ["get"]
    assert all(methods == ["get"] for methods in paths.values())
    forbidden = ("/execute", "/start", "/cancel", "/model", "/rerun", "/register")
    assert not [p for p in paths if any(word in p for word in forbidden)]


# --- shapes -------------------------------------------------------------------------------------


def test_listing_and_detail_expose_the_exact_stored_structure(client):
    listing = client.get("/api/v1/workflows").json()["workflows"]
    assert [w["name"] for w in listing] == ["research-review"]
    assert listing[0]["latest_version"] == 1 and listing[0]["latest_status"] == "draft"
    detail = client.get("/api/v1/workflows/research-review/versions/1").json()
    stored = call(client, store.get_definition, "research-review", 1)
    assert detail == stored
    assert detail["integrity"] == {"verified": True}
    assert [s["id"] for s in detail["definition"]["stages"]] == [
        "prepare",
        "analyze",
        "validate",
        "record",
    ]


def test_multiple_versions_are_listed_newest_first(client):
    for version in (1, 2):
        call(client, store.register_definition, demo(version))
    entry = client.get("/api/v1/workflows/demo-flow").json()
    assert [v["version"] for v in entry["versions"]] == [2, 1]
    summary = next(
        w for w in client.get("/api/v1/workflows").json()["workflows"] if w["name"] == "demo-flow"
    )
    assert summary["latest_version"] == 2 and [v["version"] for v in summary["versions"]] == [2, 1]


def test_graph_is_derived_plain_data_with_stable_ids(client):
    graph = client.get("/api/v1/workflows/research-review/versions/1/graph").json()
    assert [n["id"] for n in graph["nodes"]] == ["prepare", "analyze", "validate", "record"]
    assert graph["edges"][0] == {"from": "prepare", "to": "analyze"}
    assert next(n for n in graph["nodes"] if n["id"] == "record")["available"] is False
    assert "mermaid" not in json.dumps(graph).lower() and "flowchart" not in json.dumps(graph)
    again = client.get("/api/v1/workflows/research-review/versions/1/graph").json()
    assert again == graph and graph["definition_sha256"]


def test_operations_listing_states_what_exists_and_what_does_not(client):
    operations = {
        o["id"]: o for o in client.get("/api/v1/workflow-operations").json()["operations"]
    }
    assert (
        operations["cognition.role"]["available"]
        and operations["cognition.role"]["kind"] == "pi_agent"
    )
    assert not operations["evidence.record"]["available"]
    assert "Cognition.finish" in operations["evidence.record"]["unavailable_reason"]


def test_runs_and_stage_records_are_readable(client, run):
    listing = client.get("/api/v1/workflow-runs").json()["runs"]
    assert [r["id"] for r in listing] == [run["id"]]
    assert client.get("/api/v1/workflow-runs", params={"status": "COMPLETED"}).json()["runs"] == []
    assert client.get("/api/v1/workflow-runs", params={"workflow": "demo-flow"}).json()["runs"]
    detail = client.get(f"/api/v1/workflow-runs/{run['id']}").json()
    assert detail["status"] == "RUNNING" and detail["workflow"]["name"] == "demo-flow"
    stages = client.get(f"/api/v1/workflow-runs/{run['id']}/stages").json()["stages"]
    assert [(s["stage_id"], s["state"]) for s in stages] == [
        ("prepare", "RUNNING"),
        ("check", "PENDING"),
    ]
    assert all(s["pi_run_id"] is None and s["uncertainty"] == "none" for s in stages)


# --- bad requests -------------------------------------------------------------------------------


@pytest.mark.parametrize(
    "path,status",
    [
        ("/api/v1/workflows/no-such-flow", 404),
        ("/api/v1/workflows/research-review/versions/99", 404),
        ("/api/v1/workflows/research-review/versions/0", 422),
        ("/api/v1/workflows/research-review/versions/abc", 422),
        ("/api/v1/workflows/Bad_Name", 422),
        ("/api/v1/workflows/..%2F..%2Fetc", 404),
        ("/api/v1/workflow-runs/no-such-run", 404),
        ("/api/v1/workflow-runs/" + "x" * 80, 422),
        ("/api/v1/workflow-runs?limit=0", 422),
        ("/api/v1/workflow-runs?limit=100000", 422),
        ("/api/v1/workflow-runs?workflow=Bad%20Name", 422),
    ],
)
def test_unknown_and_malformed_requests_get_clean_errors(client, path, status):
    assert client.get(path).status_code == status


# --- nothing sensitive leaves ---------------------------------------------------------------------


def test_no_response_contains_credentials_tokens_or_local_paths(client, settings, run):
    paths = READ_PATHS[:6] + [
        "/api/v1/workflows/demo-flow/versions/1",
        "/api/v1/workflows/demo-flow/versions/1/graph",
        f"/api/v1/workflow-runs/{run['id']}",
        f"/api/v1/workflow-runs/{run['id']}/stages",
    ]
    blob = "".join(client.get(path).text for path in paths)
    assert len(blob) > 2000
    for secret in (REAL_KEY, TOKEN, str(settings.alive_workspace), str(settings.database_url)):
        assert secret not in blob
    for marker in ("C:\\\\", "/home/", "/Users/", "alive.db", "sqlite", "Traceback"):
        assert marker not in blob


def test_errors_do_not_echo_internals(client):
    text = client.get("/api/v1/workflows/research-review/versions/99").text
    assert (
        "Traceback" not in text
        and "sqlalchemy" not in text.lower()
        and "select " not in text.lower()
    )
