"""repository.inspect through the real WorkflowRunner: no mock executor, no model call."""

import contextlib
import os

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select

from alive.app import create_app
from alive.capabilities.registry import load_registry
from alive.capabilities.repository import capture_repository
from alive.models import Event
from alive.workflows import states, store
from alive.workflows.context import Refused
from alive.workflows.examples import fixture_authorization, stage
from tests.conftest import TOKEN, _boot
from tests.workflow_execution_helpers import call, counts, observation, prepare, reserved

PATHS = ["README.md", "docs/guide.md", "src/app.py", "tests/test_app.py"]
ATTACKS = [".env", "assets/logo.bin", "link-out"]
REF = "fixture-repo"


def workflow():
    inspect = stage(
        "inspect",
        "repository.inspect",
        "deterministic",
        {
            "repository_ref": "string",
            "snapshot_sha256": "string",
            "captured_at": "string",
            "files": "array",
            "omitted": "array",
            "provenance": "object",
        },
        inputs={"repository_ref": "$input.repository_ref", "paths": "$input.paths"},
    )
    inspect["limits"]["timeout_seconds"] = 30  # the manifest ceiling; a stage may not exceed it
    return {
        "schema_version": 1,
        "name": "repository-inspection",
        "version": 1,
        "title": "Repository inspection",
        "inputs": {
            "repository_ref": {"type": "string"},
            "paths": {"type": "array"},
        },
        "limits": {"max_wall_seconds": 120, "max_model_calls": 0, "max_total_output_tokens": 0},
        "stages": [inspect],
    }


@pytest.fixture
def repository(tmp_path):
    root = tmp_path / "repository"
    for name, text in {
        "README.md": "# Fixture\n",
        "docs/guide.md": "guide\n",
        "src/app.py": "print('hi')\n",
        "tests/test_app.py": "def test(): pass\n",
        ".env": "SECRET=1\n",
        ".gitignore": "*.bin\n",
    }.items():
        (root / name).parent.mkdir(parents=True, exist_ok=True)
        (root / name).write_text(text, encoding="utf-8")
    (root / "assets").mkdir()
    (root / "assets/logo.bin").write_bytes(b"\x00\x01")
    outside = tmp_path / "outside.txt"
    outside.write_text("not in the repository", encoding="utf-8")
    try:
        os.symlink(outside, root / "link-out")
    except (OSError, NotImplementedError):
        pass  # Unprivileged Windows: the omission is then simply "unavailable".
    return root


@pytest.fixture
def snapshot(repository):
    return capture_repository(REF, repository, PATHS + ATTACKS)


@pytest.fixture
def client(settings, snapshot):
    registry = load_registry(snapshots=[snapshot])
    app = create_app(settings, include_experiments=True, capability_registry=registry)
    _boot(settings)
    with TestClient(app, headers={"Authorization": f"Bearer {TOKEN}"}) as c:
        yield c


def grant_changes(snapshot, paths=PATHS):
    return {"inputs": {"repository_ref": REF, "paths": list(paths)}}, {
        "inspect": {
            "repository_ref": REF,
            "snapshot_sha256": snapshot.sha256,
            "paths": sorted(paths),
        }
    }


@contextlib.asynccontextmanager
async def authorized(client, snapshot, *, paths=PATHS, changes=None, resources=None):
    """The inquiry must stay open while the run is admitted and executed."""
    inputs, scope = grant_changes(snapshot, paths)
    async with client.app.state.cognition.workflow_inquiry() as inquiry:
        yield await fixture_authorization(
            client.app.state.kernel,
            inquiry,
            workflow=workflow(),
            model=False,
            changes=inputs | (changes or {}),
            resources=scope if resources is None else resources,
        )


def test_declared_capability_executes_with_exact_provenance_and_no_model_call(client, snapshot):
    prepare(client)
    observation(client)
    before = call(client, counts)

    async def run(k):
        async with authorized(client, snapshot) as grant:
            started = await client.app.state.workflows.start(grant)
            return await client.app.state.workflows.execute(started["id"])

    final = call(client, run)
    assert final["status"] == "COMPLETED", final
    (stage_run,) = call(client, store.get_stage_runs, final["id"])
    assert stage_run["capability"]["id"] == "repository.inspect"
    assert stage_run["capability"]["version"] == "1.0.0"
    assert stage_run["validation_status"] == "not_run"
    assert len(stage_run["evidence_refs"]) == len(PATHS)

    async def output(k):
        async with k.db.sessions() as session:
            event = await session.scalar(
                select(Event).where(Event.id == stage_run["output_ref"][6:])
            )
            return event.payload["output"]

    result = call(client, output)
    assert [f["path"] for f in result["files"]] == sorted(PATHS)
    assert result["snapshot_sha256"] == snapshot.sha256
    assert all(len(f["sha256"]) == 64 for f in result["files"])
    assert result["provenance"]["atomic_repository_snapshot"] is False
    # Secret, binary and escaping paths were never requested of the grant, so never returned.
    assert not {".env", "assets/logo.bin", "link-out"} & {f["path"] for f in result["files"]}
    assert call(client, counts)[:3] == before[:3]  # no model, Pi or learning rows
    assert all(value == 0 for value in call(client, reserved).values())


def test_hostile_paths_captured_as_omissions_not_content(snapshot):
    assert {p for p, _ in snapshot.omitted} >= {".env", "assets/logo.bin"}
    assert {f.path for f in snapshot.files} == set(PATHS)
    reasons = dict(snapshot.omitted)
    assert reasons[".env"] == "ignored_by_host_policy"
    assert reasons["assets/logo.bin"] == "ignored_by_host_policy"  # also .gitignore'd


@pytest.mark.parametrize("mode", ["no_capability", "wrong_hash", "no_resources", "extra_path"])
def test_execution_is_refused_without_exact_capability_authority(client, snapshot, mode):
    prepare(client)
    observation(client)
    changes = {
        "no_capability": {"capabilities": {}, "capability_binding_sha256": None},
        "wrong_hash": {"capability_binding_sha256": "0" * 64},
        # The owner approved two paths but the run input asks for four.
        "extra_path": {"inputs": {"repository_ref": REF, "paths": PATHS}},
    }.get(mode)
    resources = {} if mode == "no_resources" else None
    paths = PATHS[:2] if mode == "extra_path" else PATHS

    async def probe(k):
        async with authorized(
            client, snapshot, paths=paths, changes=changes, resources=resources
        ) as grant:
            refused = False
            try:
                started = await client.app.state.workflows.start(grant)
                final = await client.app.state.workflows.execute(started["id"])
                refused = final["status"] == states.FAILED
            except (Refused, ValueError):
                refused = True
            assert refused, "unauthorized capability produced a successful execution"

    call(client, probe)
    assert all(value == 0 for value in call(client, reserved).values())


def test_changed_capability_policy_cannot_run_a_pinned_execution(client, snapshot):
    prepare(client)
    observation(client)

    async def probe(k):
        async with authorized(client, snapshot) as grant:
            started = await client.app.state.workflows.start(grant)
            # A restart under a registry whose capability limits changed must not honour the pin.
            k.capabilities = load_registry(
                snapshots=[snapshot], limits={"repository.inspect": {"max_files": 1}}
            )
            final = await client.app.state.workflows.execute(started["id"])
            assert final["status"] == states.FAILED

    call(client, probe)
    assert all(value == 0 for value in call(client, reserved).values())
