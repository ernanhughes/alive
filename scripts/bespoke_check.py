"""Disposable BESPOKE-01 demonstration. Existing fixture owner, no model or paid inference."""

import argparse
import asyncio
import contextlib
import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path
from time import perf_counter

from fastapi.testclient import TestClient
from sqlalchemy import select

from alive.app import create_app
from alive.bespoke.handoff import trusted_handoff
from alive.capabilities.registry import load_registry
from alive.capabilities.repository import capture_repository
from alive.config import Settings
from alive.models import Event, uid
from alive.workflows.examples import fixture_authorization
from scripts.workflows_execute_check import inject

TOKEN = "bespoke-disposable-qualification-token"
ROOT = Path(__file__).resolve().parents[1]


def call(client, function, *args):
    return client.portal.call(lambda: function(client.app.state.kernel, *args))


def scenario(folder, *, repository=False, database_url=None, evaluate=False):
    folder.mkdir(parents=True, exist_ok=True)
    url = database_url or f"sqlite+aiosqlite:///{folder / 'bespoke.db'}"
    environment = os.environ | {
        "DATABASE_URL": url,
        "ALIVE_WORKSPACE": str(folder),
        "ALIVE_API_TOKEN": TOKEN,
    }
    subprocess.run(
        [sys.executable, "-m", "alembic", "upgrade", "head"],
        cwd=ROOT,
        env=environment,
        check=True,
        capture_output=True,
    )
    settings = Settings(
        _env_file=None,
        database_url=url,
        alive_workspace=folder,
        alive_api_token=TOKEN,
        alive_meta_api_key="",
        alive_heartbeat_seconds=1,
        alive_embeddings_enabled=False,
    )
    snapshots = []
    if repository:
        root = folder / "captured-repository"
        root.mkdir(exist_ok=True)
        (root / "README.md").write_text("# Captured demonstration\n", encoding="utf-8")
        snapshots = [capture_repository("fixture-repo", root, ["README.md"])]
    app = create_app(settings, capability_registry=load_registry(snapshots=snapshots))
    with TestClient(app, headers={"Authorization": f"Bearer {TOKEN}"}) as client:
        client.post(
            "/api/v1/cognition/control", json={"command": "start", "provider": "mock"}
        ).raise_for_status()

        async def stop_driver(kernel):
            cognition = app.state.cognition
            cognition.task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await cognition.task

        call(client, stop_driver)
        inject(client, 104)
        client.portal.call(app.state.cognition.perceive)
        manager = app.state.cognition.workflow_inquiry()
        inquiry = client.portal.call(manager.__aenter__)
        raw = json.loads(
            (
                ROOT
                / "docs/bespoke/workflows"
                / ("repository-inspection.json" if repository else "source-comparison.json")
            ).read_text()
        )

        async def approve(kernel):
            changes, resources = None, None
            if repository:
                changes = {"inputs": {"repository_ref": "fixture-repo", "paths": ["README.md"]}}
                resources = {
                    "inspect": {
                        "repository_ref": "fixture-repo",
                        "snapshot_sha256": snapshots[0].sha256,
                        "paths": ["README.md"],
                    }
                }
            ref = await fixture_authorization(
                kernel, inquiry, model=False, workflow=raw, changes=changes, resources=resources
            )
            async with kernel.db.sessions() as session:
                event = await session.scalar(select(Event).where(Event.id == ref))
                return ref, event.payload

        ref, grant = call(client, approve)
        request = {
            "approval_ref": ref,
            "goal_ref": grant["goal_id"],
            "investigation_ref": inquiry,
            "source_ref": grant["context_event_id"],
            "source_sha256": grant["context_sha256"],
            "objective": {
                "kind": "inspect_implementation" if repository else "compare_claims",
                "requested_outcome": "Inspect approved files"
                if repository
                else "Compare controlled claims",
            },
            "constraints": {"permissions": ["repository.read", "evidence.read", "workflow.write"]},
            "idempotency_key": uid(),
        }
        start = perf_counter()
        response = client.post("/api/v1/bespoke/recommend", json=request)
        response.raise_for_status()
        recommendation = response.json()
        elapsed = perf_counter() - start
        assert recommendation["selection"]["state"] == "recommended", recommendation
        discussion = client.post(
            "/api/v1/bespoke/recommend",
            json=request
            | {
                "objective": {
                    "kind": "explore_arguments",
                    "requested_outcome": "Explore a captured discussion",
                },
                "idempotency_key": uid(),
            },
        ).json()
        scientific = client.post(
            "/api/v1/bespoke/recommend",
            json=request
            | {
                "objective": {
                    "kind": "assess_claims",
                    "requested_outcome": (
                        "Compare scientific claims in controlled sources; "
                        "no extraction or semantic verification"
                    ),
                },
                "idempotency_key": uid(),
            },
        ).json()

        evaluation = []
        if evaluate:
            from scripts.bespoke_evaluate import run_cases

            evaluation = run_cases(client, request, repository=repository)

        async def execute(kernel):
            authority = await trusted_handoff(
                kernel, app.state.bespoke_recipes, recommendation["id"], ref
            )
            run = await app.state.workflows.start(authority)
            return await app.state.workflows.execute(run["id"])

        run = call(client, execute)
        assert run["status"] == "COMPLETED", run
        assert client.get(f"/api/v1/workflow-runs/{run['id']}/inspection").status_code == 200
        client.portal.call(manager.__aexit__, None, None, None)
        return {
            "recommendation": recommendation,
            "run": run,
            "scientific_controlled_fixture": scientific,
            "discussion": discussion,
            "installed_capabilities": client.get("/api/v1/capabilities/catalog").json(),
            "selection_seconds": elapsed,
            "record_bytes": len(response.content),
            "model_calls": 0,
            "evaluation": evaluation,
            "paid_inference": False,
        }, settings


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--workspace", type=Path)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--database-url", help="Explicitly disposable PostgreSQL database only")
    parser.add_argument("--serve", action="store_true")
    args = parser.parse_args()
    with tempfile.TemporaryDirectory(prefix="alive-bespoke-") as scratch:
        workspace = (args.workspace or Path(scratch)).resolve()
        source, settings = scenario(workspace / "sources", database_url=args.database_url)
        repository, _ = scenario(workspace / "repository", repository=True)
        result = {
            "protocol": "bespoke-demonstration/v1",
            "source_comparison": source,
            "repository": repository,
        }
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
        print(
            json.dumps(
                {
                    "output": str(args.output),
                    "source_state": source["run"]["status"],
                    "repository_state": repository["run"]["status"],
                }
            ),
            flush=True,
        )
        if args.serve:
            import uvicorn

            uvicorn.run(create_app(settings), host="127.0.0.1", port=8026)


if __name__ == "__main__":
    main()
