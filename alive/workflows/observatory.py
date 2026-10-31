"""Owned, SELECT-only observatory projections. Never execution authority."""

from sqlalchemy import and_, or_, select

from alive.cognitive_models import ModelInvocation
from alive.models import Event
from alive.pi.api import receipt
from alive.pi.models import PiProviderRequest, PiRun
from alive.workflows import store
from alive.workflows.models import WorkflowDefinition, WorkflowRun, WorkflowStageRun
from alive.workflows.spec import graph_of, hash_of_stored, parse_definition

WORKFLOW_EVENTS = {
    "workflow.run.opened",
    "workflow.execution.claimed",
    "workflow.stage.claimed",
    "workflow.stage.result",
    "workflow.execution.completed",
    "workflow.execution.ended",
    *(f"workflow.run.{s}" for s in ("running", "completed", "failed", "cancelled", "unknown")),
}
PI_EVENTS = {
    *(
        f"pi.run.{s}"
        for s in (
            "prepared",
            "admitted",
            "starting",
            "started",
            "settled",
            "failed",
            "cancelled",
            "unknown",
            "repaired",
        )
    ),
    *(
        f"pi.provider_request.{s}"
        for s in (
            "admitted",
            "dispatched",
            "settled",
            "failed",
            "rejected",
            "ambiguous",
        )
    ),
}


def require(condition):
    if not condition:
        raise store.UnknownWorkflow("History unavailable or integrity check failed")


async def records(session, kernel, run_id):
    run = await session.get(WorkflowRun, run_id)
    require(run is not None and run.instance_id == kernel.instance_id)
    definition = await session.get(WorkflowDefinition, run.definition_id)
    require(
        definition is not None
        and (
            definition.name,
            definition.version,
            definition.definition_sha256,
            definition.schema_version,
        )
        == (run.workflow_name, run.workflow_version, run.definition_sha256, run.schema_version)
        and hash_of_stored(definition.definition_json) == run.definition_sha256
    )
    try:
        spec = parse_definition(definition.definition_json)
    except (ValueError, TypeError):
        raise store.UnknownWorkflow("Invalid retained definition") from None
    declared = {s.id: s for s in spec.stages}
    stages = (
        await session.scalars(
            select(WorkflowStageRun)
            .where(WorkflowStageRun.run_id == run_id)
            .order_by(WorkflowStageRun.created_at, WorkflowStageRun.id)
            .limit(257)
        )
    ).all()
    require(len(stages) <= 256)
    for stage in stages:
        require(stage.stage_id in declared)
        expected = declared[stage.stage_id]
        require((stage.operation, stage.stage_type) == (expected.operation, expected.type))
    return run, definition, stages


async def attached_pi(session, kernel, run, stage):
    if not stage.pi_run_id:
        return None
    require(stage.model_invocation_id is not None)
    call = await session.get(ModelInvocation, stage.model_invocation_id)
    pi = await session.get(PiRun, stage.pi_run_id)
    require(
        call is not None
        and pi is not None
        and isinstance(call.input_json, dict)
        and call.investigation_id == run.investigation_id
        and call.input_json.get("workflow_run_id") == run.id
        and call.input_json.get("workflow_stage_id") == stage.id
        and pi.instance_id == kernel.instance_id
        and pi.reservation_ref == call.id
        and pi.operation == stage.operation
    )
    return pi


async def timeline(kernel, run_id, *, after=0, limit=200):
    async with kernel.db.sessions() as session:
        run, definition, stages = await records(session, kernel, run_id)
        by_attempt = {s.id: s for s in stages}
        by_pi = {}
        for stage in stages:
            pi = await attached_pi(session, kernel, run, stage)
            if pi:
                require(pi.id not in by_pi)
                by_pi[pi.id] = stage
        rows = (
            await session.scalars(
                select(Event)
                .where(
                    Event.instance_id == kernel.instance_id,
                    Event.sequence_number > after,
                    or_(
                        and_(
                            Event.source == "workflow",
                            Event.correlation_id == run.id,
                            Event.event_type.in_(WORKFLOW_EVENTS),
                        ),
                        and_(
                            Event.source == "pi",
                            Event.correlation_id.in_(by_pi),
                            Event.event_type.in_(PI_EVENTS),
                        ),
                    ),
                )
                .order_by(Event.sequence_number)
                .limit(limit + 1)
            )
        ).all()
        events = []
        for event in rows[:limit]:
            stage = by_pi.get(event.correlation_id) if event.source == "pi" else None
            if event.source == "workflow":
                require(event.payload.get("run_id") == run.id)
                if event.event_type.startswith("workflow.stage."):
                    stage = by_attempt.get(event.payload.get("stage_id"))
                    require(stage is not None)
            # Never expose result/context/prompt/event payloads. Only safe identity facts.
            events.append(
                {
                    "sequence": event.sequence_number,
                    "event_type": event.event_type,
                    "occurred_at": event.occurred_at.isoformat(),
                    "run_id": run.id,
                    "stage_id": stage.stage_id if stage else None,
                    "attempt_id": stage.id if stage else None,
                    "pi_run_id": stage.pi_run_id if stage else None,
                    "output_ref": stage.output_ref
                    if stage and stage.output_ref == "event:" + event.id
                    else None,
                    "status": event.payload.get("status")
                    if event.payload.get("status")
                    in {"COMPLETED", "FAILED", "CANCELLED", "UNKNOWN"}
                    else None,
                }
            )
        return {
            "run_id": run.id,
            "definition_id": definition.id,
            "definition_sha256": definition.definition_sha256,
            "events": events,
            "next_after": events[-1]["sequence"] if events else after,
            "has_more": len(rows) > limit,
            "complete_transition_history": False,
            "history_note": "Recorded events only. Some reservation and interrupted-stage "
            "transitions were not retained; current stage snapshots are separate facts.",
        }


async def stage_receipt(kernel, run_id, attempt_id):
    async with kernel.db.sessions() as session:
        run, _, stages = await records(session, kernel, run_id)
        stage = next((s for s in stages if s.id == attempt_id), None)
        require(stage is not None)
        pi = await attached_pi(session, kernel, run, stage)
        require(pi is not None)
        requests = (
            await session.scalars(
                select(PiProviderRequest)
                .where(PiProviderRequest.run_id == pi.id)
                .order_by(PiProviderRequest.seq)
            )
        ).all()
        return {
            "run_id": run.id,
            "attempt_id": stage.id,
            "stage_id": stage.stage_id,
            "receipt": receipt(pi, requests),
        }


async def inspected_run(kernel, run_id):
    async with kernel.db.sessions() as session:
        run, definition, _ = await records(session, kernel, run_id)
        return {
            "run": store.run_view(run),
            "definition": store.definition_view(definition, full=True),
            "graph": {
                "name": definition.name,
                "version": definition.version,
                "definition_sha256": definition.definition_sha256,
                **graph_of(definition.definition_json),
            },
        }
