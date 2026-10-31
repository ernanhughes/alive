import asyncio
import contextlib

from sqlalchemy import func, select

from alive.cognitive_models import CognitiveControl, CognitiveMessage, ModelInvocation
from alive.intelligence.models import IntelligenceLearningUpdate
from alive.models import Event
from alive.pi.models import PiRun
from alive.workflows.examples import fixture_authorization
from tests.test_cognition import observe


def call(client, function, *args, **kwargs):
    return client.portal.call(lambda: function(client.app.state.kernel, *args, **kwargs))


def prepare(client, provider="mock"):
    response = client.post(
        "/api/v1/cognition/control", json={"command": "start", "provider": provider}
    )
    assert response.status_code == 200, response.text

    async def explicit_driver(_):
        cognition = client.app.state.cognition
        cognition.task.cancel()
        with contextlib.suppress(asyncio.CancelledError):
            await cognition.task

    call(client, explicit_driver)


def observation(client):
    observe(client)

    async def perceive(_):
        await client.app.state.cognition.perceive()

    call(client, perceive)


async def lifecycle(kernel, cognition, runner, *, model=False, changes=None):
    async with cognition.workflow_inquiry() as inquiry:
        grant = await fixture_authorization(kernel, inquiry, model=model, changes=changes)
        run = await runner.start(grant)
        final = await runner.execute(run["id"])
        return final, grant


async def counts(kernel):
    async with kernel.db.sessions() as session:
        result = [
            await session.scalar(select(func.count()).select_from(model))
            for model in (ModelInvocation, PiRun, IntelligenceLearningUpdate)
        ]
        result.append(
            await session.scalar(
                select(func.count())
                .select_from(Event)
                .where(Event.source.in_(("workflow", "workflow-owner", "controlled-laboratory")))
            )
        )
        result.append(await session.scalar(select(func.count()).select_from(CognitiveMessage)))
        return tuple(result)


async def reserved(kernel):
    async with kernel.db.sessions() as session:
        control = await session.get(CognitiveControl, kernel.instance_id)
        return control.reserved


def replace_adapters(monkeypatch, replacements):
    """Fault injection for tests only: swap what the registry resolves for given operation ids.

    Production has no override parameter; this patches the registry class for one test.
    """
    from alive.capabilities.registry import CapabilityRegistry

    original = CapabilityRegistry.adapter

    def adapter(self, capability_id, version=None):
        if capability_id in replacements:
            return replacements[capability_id]
        return original(self, capability_id, version)

    monkeypatch.setattr(CapabilityRegistry, "adapter", adapter)
