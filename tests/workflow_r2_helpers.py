import asyncio
import contextlib

import httpx

from alive.workflows.examples import fixture_authorization
from tests.test_pi_gateway import REAL_KEY, Upstream
from tests.workflow_execution_helpers import observation, prepare


def pi_environment(client, settings, monkeypatch):
    settings.alive_model_transport = "pi"
    settings.alive_meta_api_key = REAL_KEY

    async def catalog(_):
        return {"status": "available", "models": [settings.alive_meta_model]}

    monkeypatch.setattr("alive.cognition.MetaProvider.discover", catalog)
    upstream = Upstream()
    client.app.state.pi.upstream_transport = httpx.MockTransport(upstream.handle)
    prepare(client, "meta")
    observation(client)
    return upstream


async def gated_run(client, kernel, before):
    """Real pinned Pi, paused immediately before the existing dispatch transaction."""
    egress = client.app.state.pi.egress
    original = egress._dispatch
    reached, release = asyncio.Event(), asyncio.Event()

    async def gated(request_id):
        reached.set()
        await release.wait()
        return await original(request_id)

    egress._dispatch = gated
    task = None
    try:
        async with client.app.state.cognition.workflow_inquiry() as inquiry:
            grant = await fixture_authorization(kernel, inquiry, model=True)
            runner = client.app.state.workflows
            run = await runner.start(grant)
            task = asyncio.create_task(runner.execute(run["id"]))
            await asyncio.wait_for(reached.wait(), 45)
            await before(kernel, grant)
            release.set()
            # Database substitution can itself make reconciliation refuse. Assertions
            # on observed dispatch still run, rather than counting teardown as a kill.
            with contextlib.suppress(ValueError):
                await asyncio.wait_for(task, 45)
            return run["id"]
    finally:
        release.set()
        if task and not task.done():
            task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await task
        egress._dispatch = original
