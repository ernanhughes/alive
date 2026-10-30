"""Real PI-02B procedures, pinned Pi and a loopback scripted provider. Never paid inference."""

import argparse
import asyncio
import contextlib
import json
import os
import subprocess
import sys
import tempfile
import threading
from http.server import ThreadingHTTPServer
from pathlib import Path
from types import SimpleNamespace

from fastapi.testclient import TestClient
from sqlalchemy import func, select

from alive.app import create_app
from alive.cognitive_models import CognitiveMessage, ModelInvocation
from alive.db import Database
from alive.intelligence.models import IntelligenceLearningUpdate
from alive.models import Event
from alive.pi.models import PiRun
from alive.workflows import store
from alive.workflows.examples import fixture_authorization
from alive.workflows.runner import WorkflowRunner, artifact_view
from scripts.pi_integration import (
    FAKE_KEY,
    TOKEN,
    Provider,
    create_schema,
    provider_requests,
    settings_for,
)


def call(client, work, *args):
    return client.portal.call(lambda: work(client.app.state.kernel, *args))


def inject(client, seed):
    lab = client.post("/api/v1/lab", json={"scenario": "relevant", "seed": seed}).json()
    view = client.post(f"/api/v1/lab/{lab['id']}/inject", json={}).json()
    response = client.post(
        "/api/v1/events",
        json={
            "event_type": "browser.dom_changed",
            "payload": {
                "url": f"http://127.0.0.1:8000/world/{lab['id']}",
                "text": view["text"],
            },
        },
    )
    response.raise_for_status()


async def durable_counts(kernel):
    async with kernel.db.sessions() as session:
        counts = [
            await session.scalar(select(func.count()).select_from(model))
            for model in (ModelInvocation, PiRun, CognitiveMessage, IntelligenceLearningUpdate)
        ]
        counts.append(
            await session.scalar(
                select(func.count()).select_from(Event).where(Event.source == "workflow")
            )
        )
        return counts


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--database-url", help="Explicit disposable test database; defaults to temporary SQLite"
    )
    parser.add_argument(
        "--process-probe",
        action="store_true",
        help="PostgreSQL: independent-process lease exclusion and successor replay",
    )
    args = parser.parse_args()
    assert not args.process_probe or (
        args.database_url and args.database_url.startswith("postgresql+")
    )
    process_receipts = []

    def process_probe(*arguments):
        child = subprocess.run(
            [sys.executable, "-B", "-m", "scripts.workflows_process_check", *arguments],
            check=True,
            capture_output=True,
            text=True,
            env=os.environ | {"DATABASE_URL": args.database_url, "ALIVE_META_API_KEY": ""},
        )
        receipt = json.loads(child.stdout)
        assert receipt["pid"] != os.getpid()
        process_receipts.append(receipt)

    server = ThreadingHTTPServer(("127.0.0.1", 0), Provider)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    provider_requests.clear()
    try:
        with tempfile.TemporaryDirectory(prefix="alive-pi02b-") as directory:
            settings = settings_for(Path(directory), server.server_address[1])
            if args.database_url:
                settings.database_url = args.database_url
                subprocess.run(
                    [sys.executable, "-B", "-m", "alembic", "upgrade", "head"],
                    check=True,
                    env=os.environ | {"DATABASE_URL": args.database_url, "ALIVE_API_TOKEN": TOKEN},
                )
            else:
                create_schema(settings)
            headers = {"Authorization": "Bearer " + TOKEN}
            results = []
            with TestClient(create_app(settings), headers=headers) as client:
                if args.process_probe:
                    process_probe("--expect-owned")
                response = client.post(
                    "/api/v1/cognition/control", json={"command": "start", "provider": "meta"}
                )
                response.raise_for_status()

                async def explicit_driver(_):
                    # This fixture drives existing admission explicitly, rather than letting the
                    # unrelated legacy autonomous loop consume the same synthetic observation.
                    task = client.app.state.cognition.task
                    task.cancel()
                    with contextlib.suppress(asyncio.CancelledError):
                        await task

                call(client, explicit_driver)
                baseline = call(client, durable_counts)
                for model, seed in ((True, 13), (False, 19)):
                    inject(client, seed)

                    async def execute(kernel):
                        cognition, runner = client.app.state.cognition, client.app.state.workflows
                        await cognition.perceive()
                        async with cognition.workflow_inquiry() as inquiry:
                            approval = await fixture_authorization(kernel, inquiry, model=model)
                            run = await runner.start(approval)
                            if model:
                                databases = [Database(settings.database_url) for _ in range(2)]
                                workers = [runner] + [
                                    WorkflowRunner(
                                        SimpleNamespace(
                                            db=db,
                                            instance_id=kernel.instance_id,
                                            ready=True,
                                            settings=settings,
                                            lock=asyncio.Lock(),
                                            add_event=kernel.add_event,
                                        ),
                                        cognition,
                                    )
                                    for db in databases
                                ]
                                try:
                                    await asyncio.gather(
                                        *(worker.execute(run["id"]) for worker in workers)
                                    )
                                finally:
                                    for db in databases:
                                        await db.engine.dispose()
                                async with kernel.db.sessions() as session:
                                    claimed = await session.scalar(
                                        select(func.count())
                                        .select_from(Event)
                                        .where(
                                            Event.event_type == "workflow.execution.claimed",
                                            Event.payload["run_id"].as_string() == run["id"],
                                        )
                                    )
                                    assert claimed == 1
                                run = await store.get_run(kernel, run["id"])
                            else:
                                run = await runner.execute(run["id"])
                            assert run["status"] == "COMPLETED", run
                            return {
                                "run": run,
                                "stages": await store.get_stage_runs(kernel, run["id"]),
                                "artifact": await artifact_view(kernel, run["id"], "record"),
                            }

                    result = call(client, execute)
                    assert len(result["stages"]) == (4 if model else 3)
                    assert all(stage["state"] == "COMPLETED" for stage in result["stages"])
                    assert result["artifact"]["independent_feedback"] is False
                    results.append(result)
                before = call(client, durable_counts)
                assert (
                    before[0] - baseline[0]
                    == before[1] - baseline[1]
                    == len(provider_requests)
                    == 1
                )
                assert before[3] == baseline[3]
                pi_stage = next(
                    stage for stage in results[0]["stages"] if stage["type"] == "pi_agent"
                )
                assert pi_stage["pi_run_id"] and pi_stage["model_invocation_id"]
                receipt = client.get("/api/v1/pi/runs/" + pi_stage["pi_run_id"]).json()
                assert (
                    receipt["state"] == "SETTLED"
                    and receipt["settlement"]["cleanup_confirmed"] is True
                )
                assert receipt["cost"]["usd"] is None
                assert receipt["pi"]["version"] == "1.4.0"
                from alive.intelligence.receipts import resolve

                async def existing_intelligence_receipt(kernel):
                    return await resolve(
                        kernel,
                        pi_stage["id"],
                        goal_id=results[0]["run"]["goal_id"],
                        approved_request_hash=receipt["approved_request_sha256"],
                    )

                intelligence_receipt = call(client, existing_intelligence_receipt)
                assert (
                    intelligence_receipt["model_invocation_id"] == pi_stage["model_invocation_id"]
                )
                assert provider_requests[0]["authorization"] == "Bearer " + FAKE_KEY
                assert provider_requests[0]["request_id"] == pi_stage["model_invocation_id"]
                assert not provider_requests[0]["tools"] and not provider_requests[0]["stream"]
            with TestClient(create_app(settings), headers=headers) as restarted:
                for _ in range(3):
                    for result in results:
                        identity = result["run"]["id"]
                        assert (
                            restarted.get(f"/api/v1/workflow-runs/{identity}").json()
                            == result["run"]
                        )
                        assert (
                            restarted.get(f"/api/v1/workflow-runs/{identity}/stages").json()[
                                "stages"
                            ]
                            == result["stages"]
                        )
                        assert (
                            restarted.get(
                                f"/api/v1/workflow-runs/{identity}/artifacts/record"
                            ).json()
                            == result["artifact"]
                        )
                assert call(restarted, durable_counts) == before
                assert len(provider_requests) == 1
            if args.process_probe:
                replay_path = Path(directory) / "replay.json"
                replay_path.write_text(json.dumps(results))
                process_probe("--replay", str(replay_path))
            output = {
                "status": "PASS",
                "qualification": "real pinned Pi; scripted local HTTP provider",
                "workflows": results,
                "pi_receipt": receipt,
                "provider_requests": 1,
                "restart": "PASS",
                "replay": "PASS: zero dispatch, artifacts or learning writes",
                "intelligence_learning_update_delta": 0,
                "independent_claim_workers": 3,
                "claim_worker_processes": 1,
                "process_lease_probes": process_receipts,
                "successful_execution_owners": 1,
                "intelligence_receipt_resolution": intelligence_receipt,
                "paid_inference": "NOT_RUN",
            }
            assert FAKE_KEY not in json.dumps(output) and TOKEN not in json.dumps(output)
            print(json.dumps(output, indent=2))
    finally:
        server.shutdown()
        thread.join(timeout=5)


if __name__ == "__main__":
    main()
