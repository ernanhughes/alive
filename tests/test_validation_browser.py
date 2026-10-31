"""Opt-in Chrome inspection of an actual deterministic captured-evidence artifact."""

import asyncio
import os
import subprocess
from pathlib import Path

import pytest
import uvicorn

from alive.pi.egress import _QuietServer
from alive.validation.workflows import definition
from tests.conftest import TOKEN
from tests.test_validation_workflows import approved, execute
from tests.workflow_execution_helpers import call, observation, prepare


@pytest.mark.skipif(
    os.environ.get("ALIVE_TEST_VALIDATION_BROWSER") != "1", reason="opt-in Chrome inspection"
)
def test_validation_report_in_the_existing_observatory(client):
    prepare(client)
    observation(client)

    async def seed(kernel):
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
        result, _ = await execute(kernel, client, definition("repository"), parameters, resources)
        assert result["status"] == "COMPLETED"
        server = _QuietServer(
            uvicorn.Config(
                client.app, host="127.0.0.1", port=0, lifespan="off", log_level="warning"
            )
        )
        task = asyncio.create_task(server.serve())
        for _ in range(200):
            if server.started:
                return result, server, task, server.servers[0].sockets[0].getsockname()[1]
            if task.done():
                task.result()
            await asyncio.sleep(0.05)
        raise AssertionError("disposable observatory failed to start")

    result, server, task, port = call(client, seed)
    client.app.state.kernel.settings.alive_allowed_origins.append(f"http://127.0.0.1:{port}")
    try:
        done = subprocess.run(
            [
                "node",
                "node_modules/@playwright/test/cli.js",
                "test",
                "e2e/validation.spec.ts",
            ],
            cwd=Path(__file__).resolve().parents[1] / "dashboard",
            capture_output=True,
            text=True,
            env=os.environ
            | {
                "ALIVE_BASE_URL": f"http://127.0.0.1:{port}",
                "ALIVE_API_TOKEN": TOKEN,
                "ALIVE_VALIDATION_RUN": result["id"],
            },
        )
        assert done.returncode == 0, done.stdout + done.stderr
    finally:

        async def stop(kernel):
            server.should_exit = True
            await task

        call(client, stop)
