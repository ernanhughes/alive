"""Synthetic receipt graphs test resolution, not qualification of real Pi execution."""

import pytest
from sqlalchemy import select

from alive.cognitive_models import CognitiveObservation, Investigation, ModelInvocation
from alive.cognitive_schema import RoleOutput
from alive.intelligence import fixture, receipts, store
from alive.intelligence.models import IntelligenceState
from alive.model_gateway import StructuredRequest
from alive.models import uid
from alive.pi.egress import approved_request_sha256, render_prompt
from alive.pi.models import PiProviderRequest, PiRun
from alive.pi.runner import sha256_text
from alive.workflows.models import WorkflowStageRun
from alive.workflows.store import open_run, register_definition
from tests.test_intelligence_durable import call


async def graph(kernel, mode):
    state_id = await fixture.start(kernel)
    async with kernel.db.sessions.begin() as session:
        state = await session.get(IntelligenceState, state_id)
        goal_id = state.goal_id
        event = kernel.add_event(session, "fixture.receipt", {}, source="synthetic-receipt-test")
        await session.flush()
        observation = CognitiveObservation(
            id=uid(),
            instance_id=kernel.instance_id,
            source_event_id=str(event.event_id),
            fingerprint=uid(),
            content="Synthetic receipt test",
            provenance={},
            attention={},
        )
        session.add(observation)
        await session.flush()
        inquiry = Investigation(
            id=uid(),
            instance_id=kernel.instance_id,
            observation_id=observation.id,
            goal_id=goal_id,
            snapshot={},
            budget={},
        )
        session.add(inquiry)
        await session.flush()
        call_row = ModelInvocation(
            id=uid(),
            investigation_id=inquiry.id,
            role="observer",
            provider="fixture",
            model="synthetic",
            status="validated",
            input_json={"instructions": "Synthetic receipt test", "context": {}},
            output_json={
                "summary": "Synthetic fixture",
                "claims": [],
                "actions": [],
                "criticisms": [],
                "uncertainties": [],
                "recommendation": "abstain",
                "confidence": 0,
            },
            reserved_tokens=0,
            usage={
                "prompt_tokens": 0,
                "completion_tokens": 0,
                "total_tokens": 0,
                "charged_tokens": 1 if mode == "charge" else 0,
            },
        )
        session.add(call_row)
        await session.flush()
        request = StructuredRequest(
            operation="cognition.role",
            instructions="Synthetic receipt test",
            data={},
            schema=RoleOutput.model_json_schema(),
            model="synthetic",
            max_output=1536,
            correlation=call_row.id,
        )
        request_hash = approved_request_sha256(request)
        pi = PiRun(
            id=uid(),
            instance_id=kernel.instance_id,
            operation="cognition.role",
            idempotency_key="synthetic:" + call_row.id,
            reservation_ref=call_row.id,
            state="UNKNOWN" if mode == "unknown" else "SETTLED",
            approved_request_json={
                "operation": request.operation,
                "model": request.model,
                "max_output": request.max_output,
                "schema_sha256": sha256_text(repr(sorted(request.schema.items()))),
                "payload_sha256": "0" * 64
                if mode == "summary"
                else sha256_text(render_prompt(request)),
            },
            approved_request_sha256=request_hash,
            requested_json={},
            token_sha256="0" * 64,
            result_json={
                "cleanup_confirmed": mode != "lifecycle",
                "pi_settled": True,
                "matches_egress_record": True,
                "text_sha256": "b" * 64,
            },
        )
        session.add(pi)
        await session.flush()
        session.add(
            PiProviderRequest(
                run_id=pi.id,
                seq=1,
                state="settled",
                approved_request_sha256=request_hash,
                usage_json=None
                if mode == "usage"
                else (
                    {}
                    if mode == "empty_usage"
                    else {
                        "prompt_tokens": 0,
                        "completion_tokens": 0,
                        "total_tokens": -1 if mode == "negative_usage" else 0,
                    }
                ),
                response_sha256="c" * 64 if mode == "output" else "b" * 64,
            )
        )
        inquiry_id, call_id, pi_id = inquiry.id, call_row.id, pi.id
    definition = {
        "schema_version": 1,
        "name": "synthetic-receipt",
        "version": 1,
        "title": "Synthetic receipt graph",
        "stages": [
            {
                "id": "reason",
                "title": "Reason",
                "type": "pi_agent",
                "operation": "cognition.role",
                "limits": {"max_output_tokens": 1536},
                "output_schema": {"properties": {"summary": {"type": "string"}}},
            }
        ],
    }
    await register_definition(kernel, definition, status="active")
    run, _ = await open_run(
        kernel, "synthetic-receipt", 1, goal_id=goal_id, investigation_id=inquiry_id
    )
    async with kernel.db.sessions.begin() as session:
        stage = await session.scalar(
            select(WorkflowStageRun).where(WorkflowStageRun.run_id == run["id"])
        )
        # Explicitly synthetic test graph, never done by the INT02 lifecycle demonstration.
        stage.state, stage.validation_status = "COMPLETED", "passed"
        stage.pi_run_id, stage.model_invocation_id = pi_id, call_id
        stage_id = stage.id
    return stage_id, goal_id, request_hash


@pytest.mark.parametrize(
    "mode",
    [
        "settled",
        "unknown",
        "usage",
        "lifecycle",
        "output",
        "hash",
        "summary",
        "empty_usage",
        "negative_usage",
        "charge",
    ],
)
def test_receipt_resolution_requires_complete_trustworthy_graph(client, mode):
    stage, goal, identity = call(client, graph, mode)
    if mode == "settled":
        receipt = call(
            client, receipts.resolve, stage, goal_id=goal, approved_request_hash=identity
        )
        assert receipt["settlement"] == "SETTLED" and receipt["usage"]["total_tokens"] == 0
    else:
        with pytest.raises(store.Refused):
            call(
                client,
                receipts.resolve,
                stage,
                goal_id=goal,
                approved_request_hash="d" * 64 if mode == "hash" else identity,
            )
