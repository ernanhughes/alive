from datetime import timedelta

import pytest
from sqlalchemy import select

from alive.cognitive_models import CognitiveControl, ModelInvocation
from alive.models import Event, now
from alive.pi.models import PiProviderRequest
from alive.workflows import context, store
from alive.workflows.models import WorkflowExecution, WorkflowStageRun
from tests.workflow_execution_helpers import call, reserved
from tests.workflow_r2_helpers import gated_run, pi_environment


@pytest.mark.parametrize(
    "change",
    [
        "configuration",
        "deadline",
        "expiry",
        "model",
        "context",
        "status",
        "stage_state",
        "stage_link",
        "missing_guard",
        "withdraw",
        "revoke",
    ],
)
def test_dispatch_fence_individual_invariants(client, settings, monkeypatch, change):
    upstream = pi_environment(client, settings, monkeypatch)

    async def before(k, grant_id):
        if change == "missing_guard":
            client.app.state.pi.egress.workflow_guard = None
            return
        async with k.lock, k.db.sessions.begin() as session:
            grant = await session.scalar(select(Event).where(Event.id == grant_id))
            invocation = (await session.scalars(select(ModelInvocation))).one()
            stage = await session.scalar(
                select(WorkflowStageRun).where(
                    WorkflowStageRun.model_invocation_id == invocation.id
                )
            )
            if change == "configuration":
                control = await session.get(CognitiveControl, k.instance_id)
                control.configuration = {**control.configuration, "topics": ["changed"]}
            elif change == "deadline":
                execution = (await session.scalars(select(WorkflowExecution))).one()
                execution.deadline = now() - timedelta(seconds=1)
            elif change == "expiry":
                from datetime import datetime

                expired = datetime.fromisoformat(grant.payload["expires_at"]) + timedelta(seconds=1)
                monkeypatch.setattr(context, "now", lambda: expired)
            elif change == "model":
                invocation.model = "unapproved-substitution"
            elif change == "context":
                invocation.input_json = {**invocation.input_json, "context": {"substituted": True}}
            elif change == "status":
                invocation.status = "validated"
            elif change == "stage_state":
                # A valid terminal state isolates the fence clause without making
                # mutated cleanup attempt an invalid PENDING -> UNKNOWN transition.
                stage.state = "FAILED"
            elif change == "stage_link":
                stage.model_invocation_id = None
        if change == "withdraw":
            await context.withdraw(k, grant.payload["context_event_id"])
        elif change == "revoke":
            await context.revoke(k, grant_id)

    async def probe(k):
        run_id = await gated_run(client, k, before)
        assert len(upstream.calls) == 0, f"{change} crossed actual dispatch fence"
        async with k.db.sessions() as session:
            requests = (await session.scalars(select(PiProviderRequest))).all()
            assert len(requests) == 1 and requests[0].state == "rejected"
        if change not in {"stage_state", "stage_link"}:
            result = await store.get_run(k, run_id)
            assert result["terminal_reason"] == "authority_refused"
        return run_id

    call(client, probe)
    assert all(value == 0 for value in call(client, reserved).values())
