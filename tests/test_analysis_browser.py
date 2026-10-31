"""Opt-in real-browser journey on the disposable analysis fixture; no production test routes."""

import asyncio
import os
import subprocess
from pathlib import Path

import pytest
import uvicorn

from alive.pi.egress import _QuietServer
from tests import test_repository_analysis as fixtures
from tests.conftest import TOKEN
from tests.test_owner_admission import approve_review, call
from tests.test_repository_analysis import prepared

case = fixtures.case
ready = fixtures.ready
settings = fixtures.settings
quick_settle = fixtures.quick_settle


@pytest.mark.skipif(
    os.environ.get("ALIVE_TEST_ANALYSIS_BROWSER") != "1", reason="opt-in Chrome journey"
)
def test_real_admission_to_report_browser_journey(ready):
    client, upstream, *_ = ready
    review = prepared(ready)
    # Local trusted owner confirmation, never an HTTP approval route.
    approve_review(client, review)

    async def serve(kernel):
        server = _QuietServer(
            uvicorn.Config(
                client.app,
                host="127.0.0.1",
                port=0,
                lifespan="off",
                log_level="warning",
            )
        )
        task = asyncio.create_task(server.serve())
        for _ in range(200):
            if server.started:
                return server, task, server.servers[0].sockets[0].getsockname()[1]
            if task.done():
                task.result()
            await asyncio.sleep(0.05)
        raise AssertionError("disposable browser server did not start")

    server, task, port = call(client, serve)
    # This disposable app admits only its own randomly allocated loopback browser origin.
    client.app.state.kernel.settings.alive_allowed_origins.append(f"http://127.0.0.1:{port}")
    dashboard = Path(__file__).resolve().parents[1] / "dashboard"
    try:
        result = subprocess.run(
            [
                "node",
                "node_modules/@playwright/test/cli.js",
                "test",
                "e2e/admission-analysis.spec.ts",
            ],
            cwd=dashboard,
            capture_output=True,
            text=True,
            env=os.environ
            | {
                "ALIVE_BASE_URL": f"http://127.0.0.1:{port}",
                "ALIVE_API_TOKEN": TOKEN,
                "ALIVE_ANALYSIS_REVIEW_ID": review["id"],
            },
        )
        assert result.returncode == 0, result.stdout + result.stderr
        assert len(upstream.calls) == 1
    finally:

        async def stop(kernel):
            server.should_exit = True
            await task

        call(client, stop)
