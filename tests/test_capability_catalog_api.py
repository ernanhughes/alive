"""Catalogue API: safe metadata only, read-only, and exact-identity workflow references."""

import pytest
from fastapi.testclient import TestClient

from alive.app import create_app
from alive.capabilities.registry import load_registry
from alive.capabilities.repository import capture_repository
from tests.conftest import MANIFESTS_DIR, TOKEN, _boot
from tests.test_capability_repository_execution import REF, authorized, workflow
from tests.workflow_execution_helpers import call, observation, prepare

BASE = "/api/v1/capabilities/catalog"


def test_catalog_requires_the_existing_bearer(client):
    assert TestClient(client.app).get(BASE).status_code == 401


def test_catalog_lists_every_capability_with_honest_status(client):
    body = client.get(BASE).json()
    by_id = {c["id"]: c for c in body["capabilities"]}
    assert len(body["catalog_sha256"]) == 64
    assert by_id["repository.inspect"]["status"] == "available"
    assert by_id["repository.inspect"]["effect_class"] == "read"
    assert by_id["cognition.role"]["effect_class"] == "model"
    assert by_id["result.record"]["effect_class"] == "writes"
    # Underlying functionality existing is not a governed adapter.
    assert by_id["memory.retrieve"]["status"] == "unavailable"
    assert by_id["memory.retrieve"]["implementation_state"] == "missing"
    assert not by_id["memory.retrieve"]["workflow_available"]


def test_detail_exposes_contracts_and_never_paths_or_secrets(client):
    body = client.get(f"{BASE}/repository.inspect/versions/1.0.0").json()
    cap = body["capability"]
    assert cap["inputs"]["required"] == ["paths", "repository_ref"]
    assert cap["effective_limits"]["max_files"] == 20
    assert cap["implementation"]["id"] == "repository-inspector-v1"
    text = str(body).lower()
    for forbidden in (
        "alive.workflows",
        "alive.capabilities",
        ".py",
        "bearer",
        "password",
        "secret",
        TOKEN,
    ):
        assert forbidden not in text, forbidden
    assert body["workflows"] == []


@pytest.mark.parametrize(
    "path",
    [
        "/nope.nope",
        "/repository.inspect/versions/9.9.9",
        "/repository.inspect/versions/1.0",
        "/..%2Fetc",
        "/repository.inspect/versions/1.0.0%00",
    ],
)
def test_unknown_or_malformed_identity_is_refused(client, path):
    assert client.get(BASE + path).status_code in (404, 422)


@pytest.mark.parametrize("method", ["post", "put", "patch", "delete"])
def test_catalog_has_no_write_surface(client, method):
    for path in ("", "/repository.inspect", "/repository.inspect/versions/1.0.0"):
        assert getattr(client, method)(BASE + path).status_code in (404, 405)


def test_workflow_references_use_exact_retained_identity(settings, tmp_path):
    root = tmp_path / "repo"
    root.mkdir()
    (root / "README.md").write_text("x", encoding="utf-8")
    snapshot = capture_repository(REF, root, ["README.md"])
    app = create_app(
        settings, include_experiments=True, capability_registry=load_registry(snapshots=[snapshot])
    )
    _boot(settings)
    paths = ["README.md"]
    with TestClient(app, headers={"Authorization": f"Bearer {TOKEN}"}) as client:
        prepare(client)
        observation(client)

        async def register(_):
            async with authorized(client, snapshot, paths=paths):
                pass

        call(client, register)
        body = client.get(f"{BASE}/repository.inspect/versions/1.0.0").json()
        assert [(w["name"], w["version"], w["stages"]) for w in body["workflows"]] == [
            (workflow()["name"], 1, ["inspect"])
        ]
        other = client.get(f"{BASE}/context.prepare/versions/1.0.0").json()
        # Seeded built-ins legitimately use context.prepare; this workflow must not be attached.
        assert "repository-inspection" not in {w["name"] for w in other["workflows"]}


def pinned_reference_client(settings, tmp_path):
    root = tmp_path / "repo"
    root.mkdir()
    (root / "README.md").write_text("x", encoding="utf-8")
    snapshot = capture_repository(REF, root, ["README.md"])
    app = create_app(
        settings, include_experiments=True, capability_registry=load_registry(snapshots=[snapshot])
    )
    _boot(settings)
    return app, snapshot


@pytest.mark.parametrize("change", ["unchanged", "manifest", "implementation"])
def test_references_need_the_full_retained_identity(settings, tmp_path, change):
    """Same name and version is not the same capability: hash and implementation must match."""
    import dataclasses

    from alive.capabilities.manifest import parse
    from alive.capabilities.registry import CapabilityRegistry
    from alive.capabilities.trusted import TRUSTED

    app, snapshot = pinned_reference_client(settings, tmp_path)
    with TestClient(app, headers={"Authorization": f"Bearer {TOKEN}"}) as client:
        prepare(client)
        observation(client)

        async def register(_):
            async with authorized(client, snapshot, paths=["README.md"]):
                pass

        call(client, register)
        manifests = [parse(f.read_text("utf-8")) for f in sorted(MANIFESTS_DIR.glob("*.yaml"))]
        implementations = dict(TRUSTED)
        if change == "manifest":
            text = (MANIFESTS_DIR / "repository.inspect@1.0.0.yaml").read_text("utf-8")
            text = text.replace("Inspect an explicit", "Inspect a differently worded")
            manifests = [m for m in manifests if m.id != "repository.inspect"] + [parse(text)]
        if change == "implementation":
            implementations["repository-inspector-v1"] = dataclasses.replace(
                TRUSTED["repository-inspector-v1"], traits=frozenset({"changed.only.here"})
            )
        client.app.state.kernel.capabilities = CapabilityRegistry(
            manifests, implementations=implementations, snapshots=[snapshot]
        )
        body = client.get(f"{BASE}/repository.inspect/versions/1.0.0").json()
        listed = [w["name"] for w in body["workflows"]]
        assert ("repository-inspection" in listed) is (change == "unchanged")
