"""Disposable real-runtime observatory evidence. Loopback scripted provider, never paid.

Seed a NEW directory, then serve its restarted history on loopback:
  python -m scripts.workflow_observatory_demo --directory <empty-path> --seed
  python -m scripts.workflow_observatory_demo --directory <same-path> --serve 8018
Use --database-url only for an explicitly disposable PostgreSQL database.
"""

import argparse
import asyncio
import contextlib
import json
import os
import subprocess
import sys
import threading
from http.server import ThreadingHTTPServer
from pathlib import Path

from fastapi.testclient import TestClient
from sqlalchemy import func, select

from alive.app import create_app
from alive.cognitive_models import CognitiveMessage, ModelInvocation
from alive.intelligence.models import IntelligenceLearningUpdate
from alive.pi.models import PiProviderRequest, PiRun
from alive.workflows import store
from alive.workflows.context import Refused
from alive.workflows.examples import definition, fixture_authorization
from alive.workflows.models import WorkflowRun
from scripts.pi_integration import TOKEN, Provider, create_schema, provider_requests, settings_for
from scripts.workflows_execute_check import call


def inject(client, seed):
    lab_response = client.post("/api/v1/lab", json={"scenario": "relevant", "seed": seed})
    lab_response.raise_for_status()
    lab = lab_response.json()
    response = client.post(f"/api/v1/lab/{lab['id']}/inject", json={})
    response.raise_for_status()
    response = client.post(
        "/api/v1/events",
        json={
            "event_type": "browser.dom_changed",
            "payload": {
                "url": f"http://127.0.0.1:8000/world/{lab['id']}",
                "text": response.json()["text"],
            },
        },
    )
    response.raise_for_status()


async def counts(kernel):
    async with kernel.db.sessions() as session:
        return {
            model.__tablename__: await session.scalar(select(func.count()).select_from(model))
            for model in (
                ModelInvocation,
                PiRun,
                PiProviderRequest,
                WorkflowRun,
                CognitiveMessage,
                IntelligenceLearningUpdate,
            )
        }


def verify(client, manifest):
    before = call(client, counts)
    for run in manifest["runs"]:
        base = f"/api/v1/workflow-runs/{run['id']}"
        inspection = client.get(base + "/inspection")
        assert inspection.status_code == 200, inspection.text
        assert inspection.json()["run"]["status"] == run["status"]
        timeline = client.get(base + "/timeline?limit=500")
        assert timeline.status_code == 200, timeline.text
        assert not timeline.json()["has_more"]
        assert timeline.json()["events"]
        stages = client.get(base + "/stages").json()["stages"]
        for stage in stages:
            if stage["pi_run_id"]:
                receipt = client.get(base + f"/stages/{stage['id']}/pi-receipt")
                assert receipt.status_code == 200, receipt.text
                assert receipt.json()["receipt"]["reservation_ref"] == stage["model_invocation_id"]
            if stage["operation"] == "result.record" and stage["state"] == "COMPLETED":
                artifact = client.get(base + "/artifacts/record")
                assert artifact.status_code == 200, artifact.text
                assert artifact.json()["workflow_completed"] == (run["status"] == "COMPLETED")
    assert before == call(client, counts) == manifest["counts_after_seed"]
    return before


def seed(settings, directory):
    hold = threading.Event()
    hold.set()

    class LocalProvider(Provider):
        def reply(self, payload):
            if self.command == "POST":
                hold.wait(30)
            with contextlib.suppress(BrokenPipeError, ConnectionResetError):
                super().reply(payload)

    server = ThreadingHTTPServer(("127.0.0.1", 0), LocalProvider)
    server.daemon_threads = True
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    settings.alive_meta_base_url = f"http://127.0.0.1:{server.server_address[1]}/v1"
    provider_requests.clear()
    headers = {"Authorization": "Bearer " + TOKEN}
    runs = []
    try:
        with TestClient(create_app(settings), headers=headers) as client:
            client.post(
                "/api/v1/cognition/control", json={"command": "start", "provider": "meta"}
            ).raise_for_status()

            async def stop_driver(_):
                task = client.app.state.cognition.task
                task.cancel()
                with contextlib.suppress(asyncio.CancelledError):
                    await task

            call(client, stop_driver)
            for label, model, version in (
                ("research", True, 2),
                ("research_v3", True, 3),
                ("deterministic", False, 1),
                ("goal_cancel", False, 1),
                ("ambiguous", True, 2),
                ("partial", True, 2),
            ):
                inject(client, 100 + len(runs))

                async def execute(kernel):
                    cognition, runner = client.app.state.cognition, client.app.state.workflows
                    await cognition.perceive()
                    async with cognition.workflow_inquiry() as inquiry:
                        changes = None
                        if version == 3:
                            raw = definition(model=True)
                            raw["version"] = 3
                            # A distinct declared dependency graph, same governed operations.
                            raw["stages"][-1]["depends_on"] = ["prepare", "validate"]
                            view, _ = await store.register_definition(kernel, raw, status="active")
                            changes = {
                                "definition_id": view["id"],
                                "definition_sha256": view["definition_sha256"],
                            }
                        grant = await fixture_authorization(
                            kernel, inquiry, model=model, changes=changes
                        )
                        run = await runner.start(grant)
                        original = runner._finish
                        try:
                            if label == "goal_cancel":
                                response = await asyncio.to_thread(
                                    client.post,
                                    f"/api/v1/goals/{run['goal_id']}/transition",
                                    json={"status": "cancelled"},
                                )
                                response.raise_for_status()
                            if label == "partial":

                                async def interrupted(*args):
                                    raise Refused("fixture_finalize_interrupted")

                                runner._finish = interrupted
                            if label == "ambiguous":
                                hold.clear()
                                previous = len(provider_requests)
                                task = asyncio.create_task(runner.execute(run["id"]))
                                async with asyncio.timeout(45):
                                    while len(provider_requests) == previous:
                                        await asyncio.sleep(0.01)
                                task.cancel()
                                await asyncio.gather(task, return_exceptions=True)
                                hold.set()
                                final = await store.get_run(kernel, run["id"])
                            else:
                                final = await runner.execute(run["id"])
                        finally:
                            hold.set()
                            runner._finish = original
                        expected = (
                            "UNKNOWN"
                            if label == "ambiguous"
                            else "FAILED"
                            if label in {"goal_cancel", "partial"}
                            else "COMPLETED"
                        )
                        assert final["status"] == expected, final
                        return {
                            "label": label,
                            "id": final["id"],
                            "status": final["status"],
                            "workflow": final["workflow"],
                        }

                runs.append(call(client, execute))
            assert len(provider_requests) == 4
            manifest = {
                "baseline": "PI-02C",
                "runs": runs,
                "provider_requests": 4,
                "counts_after_seed": call(client, counts),
                "paid_inference": "NOT_RUN",
            }
            verify(client, manifest)
        with TestClient(create_app(settings), headers=headers) as restarted:
            verify(restarted, manifest)
            assert len(provider_requests) == 4
        manifest["restart_replay"] = (
            "PASS: unchanged invocation/Pi/request/run/artifact/learning counts"
        )
        (directory / "manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
        print(json.dumps(manifest, indent=2))
    finally:
        hold.set()
        server.shutdown()
        thread.join(timeout=5)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--directory", type=Path, required=True)
    parser.add_argument("--database-url")
    parser.add_argument("--seed", action="store_true")
    parser.add_argument("--serve", type=int)
    args = parser.parse_args()
    directory = args.directory.resolve()
    settings = settings_for(directory, 1)
    settings.alive_allowed_origins = [f"http://127.0.0.1:{args.serve or 8018}"]
    if args.database_url:
        settings.database_url = args.database_url
    if args.seed:
        if directory.exists() and any(directory.iterdir()):
            raise SystemExit("Seed requires a new empty task-owned directory")
        directory.mkdir(parents=True, exist_ok=True)
        if args.database_url:
            subprocess.run(
                [sys.executable, "-m", "alembic", "upgrade", "head"],
                check=True,
                env=os.environ | {"DATABASE_URL": args.database_url, "ALIVE_API_TOKEN": TOKEN},
            )
        else:
            create_schema(settings)
        seed(settings, directory)
    else:
        manifest = json.loads((directory / "manifest.json").read_text())
        with TestClient(
            create_app(settings), headers={"Authorization": "Bearer " + TOKEN}
        ) as client:
            verify(client, manifest)
        print("PASS: restarted history reads preserve all six durable counts")
    if args.serve:
        import uvicorn

        settings.alive_meta_api_key = ""  # history serving cannot dispatch paid inference
        uvicorn.run(create_app(settings), host="127.0.0.1", port=args.serve, access_log=False)


if __name__ == "__main__":
    main()
