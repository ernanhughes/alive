import asyncio
from pathlib import Path

import httpx
import pytest
from sqlalchemy import select

from alive.cognitive_models import ModelInvocation
from alive.pi.models import PiProviderRequest, PiRun
from alive.workflows import store
from alive.workflows.examples import fixture_authorization
from tests.test_pi_gateway import REAL_KEY, Upstream
from tests.workflow_execution_helpers import (
    call,
    counts,
    observation,
    prepare,
    replace_adapters,
    reserved,
)


def test_explicit_cancel_of_pending_run_closes_its_reservation(client):
    prepare(client)
    observation(client)

    async def probe(k):
        async with client.app.state.cognition.workflow_inquiry() as inquiry:
            approval = await fixture_authorization(k, inquiry, model=False)
            runner = client.app.state.workflows
            run = await runner.start(approval)
            await runner.cancel(run["id"])
            assert (await store.get_run(k, run["id"]))["status"] == "CANCELLED"
            assert (await counts(k))[:3] == (0, 0, 0)

    call(client, probe)
    assert all(value == 0 for value in call(client, reserved).values())


@pytest.mark.parametrize("phase", ["creation", "run_claim", "stage_claim", "model_start"])
def test_cancel_at_lifecycle_boundaries_is_settled(client, settings, monkeypatch, phase):
    prepare(client)
    observation(client)
    original = client.app.state.kernel.add_event

    def injected(session, kind, *args, **kwargs):
        targets = {
            "run_claim": "workflow.execution.claimed",
            "stage_claim": "workflow.stage.claimed",
        }
        if kind == targets.get(phase):
            asyncio.current_task().cancel()
        return original(session, kind, *args, **kwargs)

    monkeypatch.setattr(client.app.state.kernel, "add_event", injected)

    async def probe(k):
        async with client.app.state.cognition.workflow_inquiry() as inquiry:
            approval = await fixture_authorization(k, inquiry, model=False)
            runner = client.app.state.workflows
            if phase == "creation":
                task = asyncio.create_task(runner.start(approval))
                task.cancel()
                try:
                    await task
                except asyncio.CancelledError:
                    pass
            else:
                run = await runner.start(approval)
                if phase == "model_start":
                    # A claimed operation stalls before calling any inference/service.
                    entered = asyncio.Event()

                    async def stalled(_):
                        entered.set()
                        await asyncio.Event().wait()

                    replace_adapters(monkeypatch, {"context.prepare": stalled})
                    task = asyncio.create_task(runner.execute(run["id"]))
                    await asyncio.wait_for(entered.wait(), 5)
                    task.cancel()
                    result = await task
                else:
                    result = await runner.execute(run["id"])
                assert result["status"] == "CANCELLED"
            assert (await counts(k))[:3] == (0, 0, 0)

    call(client, probe)
    assert all(value == 0 for value in call(client, reserved).values())


def test_real_pi_cancel_pending_upstream_is_unknown_and_never_retried(
    client, settings, monkeypatch
):
    cli = (
        Path(__file__).resolve().parents[1]
        / "pi-runtime/node_modules/@earendil-works/pi-coding-agent/dist/bundle/cli.js"
    )
    if not cli.is_file():
        pytest.skip("Pinned real Pi not installed; CI installs it")
    settings.alive_model_transport = "pi"
    settings.alive_meta_api_key = REAL_KEY

    async def catalog(_):
        return {"status": "available", "models": [settings.alive_meta_model]}

    monkeypatch.setattr("alive.cognition.MetaProvider.discover", catalog)
    monkeypatch.setattr("alive.pi.gateway.SETTLE_WAIT_SECONDS", 0.1)
    upstream = Upstream()
    client.app.state.pi.upstream_transport = httpx.MockTransport(upstream.handle)
    prepare(client, "meta")
    observation(client)

    async def probe(k):
        upstream.block = asyncio.Event()
        async with client.app.state.cognition.workflow_inquiry() as inquiry:
            approval = await fixture_authorization(k, inquiry, model=True)
            runner = client.app.state.workflows
            run = await runner.start(approval)
            task = asyncio.create_task(runner.execute(run["id"]))
            for _ in range(400):
                if upstream.calls:
                    break
                await asyncio.sleep(0.02)
            assert upstream.calls, "the actual pinned Pi never reached its approved upstream"
            # No global kernel lock or transaction is retained across the model wait.
            await asyncio.wait_for(k.lock.acquire(), 1)
            k.lock.release()
            task.cancel()
            result = await task
            assert result["status"] == "UNKNOWN"
            assert len(upstream.calls) == 1
            async with k.db.sessions() as session:
                pi = await session.scalar(select(PiRun))
                request = await session.scalar(select(PiProviderRequest))
                invocation = await session.scalar(select(ModelInvocation))
                assert pi.state == "UNKNOWN" and request.state == "ambiguous"
                assert pi.result_json["cleanup_confirmed"] is True
                assert invocation.status != "reserved"
            await runner.execute(run["id"])
            assert len(upstream.calls) == 1
            assert (await store.get_run(k, run["id"]))["status"] == "UNKNOWN"
            upstream.block.set()

    call(client, probe)
    assert all(value == 0 for value in call(client, reserved).values())


def test_revocation_after_reservation_is_fenced_before_real_pi_upstream(
    client, settings, monkeypatch
):
    settings.alive_model_transport = "pi"
    settings.alive_meta_api_key = REAL_KEY

    async def catalog(_):
        return {"status": "available", "models": [settings.alive_meta_model]}

    monkeypatch.setattr("alive.cognition.MetaProvider.discover", catalog)
    upstream = Upstream()
    client.app.state.pi.upstream_transport = httpx.MockTransport(upstream.handle)
    prepare(client, "meta")
    observation(client)

    async def probe(k):
        from alive.workflows.context import revoke

        async with client.app.state.cognition.workflow_inquiry() as inquiry:
            approval = await fixture_authorization(k, inquiry, model=True)
            runner = client.app.state.workflows
            run = await runner.start(approval)
            original = client.app.state.pi.egress._dispatch

            async def revoked_before_dispatch(request_id):
                await revoke(k, approval)
                return await original(request_id)

            monkeypatch.setattr(client.app.state.pi.egress, "_dispatch", revoked_before_dispatch)
            result = await runner.execute(run["id"])
            assert upstream.calls == [], "a revoked workflow reached its provider"
            assert result["status"] != "COMPLETED"
            async with k.db.sessions() as session:
                request = await session.scalar(select(PiProviderRequest))
                assert request.state == "rejected"
                assert request.error_category == "workflow_authority_revoked"
                invocation = await session.scalar(select(ModelInvocation))
                assert invocation.status != "reserved"

    call(client, probe)
    assert all(value == 0 for value in call(client, reserved).values())
