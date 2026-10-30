import httpx
from sqlalchemy import func, select

from alive.cognitive_models import CognitiveMessage, ModelInvocation
from alive.workflows import store
from alive.workflows.examples import fixture_authorization
from tests.test_pi_gateway import REAL_KEY, Upstream
from tests.workflow_execution_helpers import call, lifecycle, observation, prepare, reserved


def test_artifact_and_stage_commit_or_rollback_together(client, monkeypatch):
    prepare(client)
    observation(client)
    original = client.app.state.kernel.add_event

    def fail(session, kind, payload=None, **kwargs):
        if kind == "workflow.stage.result" and "artifact_id" in payload["output"]:
            raise RuntimeError("injected after artifact add, before transaction commit")
        return original(session, kind, payload, **kwargs)

    monkeypatch.setattr(client.app.state.kernel, "add_event", fail)
    run, _ = call(
        client, lambda k: lifecycle(k, client.app.state.cognition, client.app.state.workflows)
    )
    assert run["status"] == "FAILED"
    stages = call(client, store.get_stage_runs, run["id"])
    assert stages[-1]["state"] == "FAILED" and stages[-1]["output_ref"] is None

    async def no_artifact(k):
        async with k.db.sessions() as session:
            assert await session.scalar(select(func.count()).select_from(CognitiveMessage)) == 0

    call(client, no_artifact)
    assert all(value == 0 for value in call(client, reserved).values())


def test_real_pi_effect_before_stage_commit_is_unknown_without_retry(client, settings, monkeypatch):
    settings.alive_model_transport = "pi"
    settings.alive_meta_api_key = REAL_KEY

    async def catalog(_):
        return {"status": "available", "models": [settings.alive_meta_model]}

    monkeypatch.setattr("alive.cognition.MetaProvider.discover", catalog)
    upstream = Upstream()
    client.app.state.pi.upstream_transport = httpx.MockTransport(upstream.handle)
    prepare(client, "meta")
    observation(client)
    original = client.app.state.kernel.add_event

    def fail(session, kind, payload=None, **kwargs):
        if kind == "workflow.stage.result" and "analysis" in payload["output"]:
            raise RuntimeError("injected after settled model effect, before result commit")
        return original(session, kind, payload, **kwargs)

    monkeypatch.setattr(client.app.state.kernel, "add_event", fail)

    async def probe(k):
        async with client.app.state.cognition.workflow_inquiry() as inquiry:
            authorization = await fixture_authorization(k, inquiry, model=True)
            run = await client.app.state.workflows.start(authorization)
            result = await client.app.state.workflows.execute(run["id"])
            assert result["status"] == "UNKNOWN"
            assert len(upstream.calls) == 1
            stages = await store.get_stage_runs(k, run["id"])
            model = next(stage for stage in stages if stage["type"] == "pi_agent")
            assert model["state"] == "UNKNOWN" and model["output_ref"] is None
            async with k.db.sessions() as session:
                invocation = await session.get(ModelInvocation, model["model_invocation_id"])
                assert invocation.status == "validated"
                assert invocation.usage["charged_tokens"] > 0
            await client.app.state.workflows.execute(run["id"])
            assert len(upstream.calls) == 1

    call(client, probe)
    assert all(value == 0 for value in call(client, reserved).values())
