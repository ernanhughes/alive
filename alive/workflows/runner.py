"""Sequential, explicitly authorized execution of immutable PI-02A procedures."""

import asyncio
from datetime import timedelta

from sqlalchemy import select, update
from sqlalchemy.exc import IntegrityError

from alive.cognition import complete_despite_cancel
from alive.cognitive_models import CognitiveMessage, Investigation, ModelInvocation
from alive.models import Event, now, uid
from alive.pi.models import PiProviderRequest, PiRun
from alive.workflows import states, store
from alive.workflows.adapters import ADAPTERS, StageContext
from alive.workflows.context import Refused, authorized, aware, bounded, digest, require
from alive.workflows.models import WorkflowExecution, WorkflowRun, WorkflowStageRun
from alive.workflows.spec import check_activatable

TYPES = {
    "object": lambda x: type(x) is dict,
    "array": lambda x: type(x) is list,
    "string": lambda x: type(x) is str,
    "boolean": lambda x: type(x) is bool,
    "integer": lambda x: type(x) is int,
    "number": lambda x: type(x) in (int, float),
}


def output_valid(stage, data):
    bounded(data)
    require(
        type(data) is dict
        and set(data) <= stage.output_schema.properties.keys()
        and set(stage.output_schema.required) <= data.keys(),
        "output_schema",
    )
    require(
        all(TYPES[stage.output_schema.properties[key].type](value) for key, value in data.items()),
        "output_type",
    )


def order(spec):
    remaining, done = list(spec.stages), set()
    while remaining:
        ready = next(stage for stage in remaining if set(stage.depends_on) <= done)
        yield ready
        done.add(ready.id)
        remaining.remove(ready)


def inputs_for(stage, outputs, supplied):
    result = {}
    for name, value in stage.inputs.items():
        if isinstance(value, str) and value.startswith("$"):
            parts = value[1:].split(".")
            if parts[0] == "input":
                require(parts[1] in supplied, "missing_workflow_input")
                value = supplied[parts[1]]
            else:
                require(parts[1] in outputs and parts[2] in outputs[parts[1]], "missing_dependency")
                value = outputs[parts[1]][parts[2]]
        result[name] = value
    return bounded(result)


def executable(spec, grant):
    check_activatable(spec)
    require(
        all(
            stage.operation in ADAPTERS and stage.operation in grant.operations
            for stage in spec.stages
        ),
        "operation_not_authorized_or_executable",
    )
    require(
        all(stage.type != "approval_gate" and stage.on_failure == "stop" for stage in spec.stages),
        "approval_unavailable",
    )
    calls = [stage for stage in spec.stages if stage.type == "pi_agent"]
    require(
        len(calls) <= grant.max_model_calls <= spec.limits.max_model_calls
        and sum(stage.limits.max_output_tokens for stage in calls)
        <= grant.max_output_tokens
        <= spec.limits.max_total_output_tokens
        and grant.wall_seconds <= spec.limits.max_wall_seconds,
        "workflow_budget",
    )
    require(set(grant.inputs) <= spec.inputs.keys(), "undeclared_workflow_input")
    for name, declaration in spec.inputs.items():
        require(name in grant.inputs or not declaration.required, "missing_workflow_input")
        if name in grant.inputs:
            require(TYPES[declaration.type](grant.inputs[name]), "workflow_input_type")


async def result_event(session, stage):
    require(stage.output_ref and stage.output_ref.startswith("event:"), "result_unavailable")
    event = await session.scalar(select(Event).where(Event.id == stage.output_ref[6:]))
    run = await session.get(WorkflowRun, stage.run_id)
    require(
        event is not None
        and event.event_type == "workflow.stage.result"
        and event.source == "workflow"
        and event.instance_id == run.instance_id
        and event.payload.get("stage_id") == stage.id
        and event.payload.get("run_id") == stage.run_id
        and digest(event.payload["output"]) == stage.output_sha256,
        "result_integrity",
    )
    return event.payload["output"]


async def pi_facts(session, kernel, stage):
    call = await session.get(ModelInvocation, stage.model_invocation_id)
    pi = await session.scalar(
        select(PiRun).where(PiRun.reservation_ref == stage.model_invocation_id)
    )
    require(
        call is not None
        and call.status == "validated"
        and pi is not None
        and pi.instance_id == kernel.instance_id
        and pi.operation == "cognition.role"
        and pi.state == "SETTLED"
        and all(
            pi.result_json.get(key) is True
            for key in ("cleanup_confirmed", "pi_settled", "matches_egress_record")
        ),
        "unsettled_pi",
    )
    requests = (
        await session.scalars(select(PiProviderRequest).where(PiProviderRequest.run_id == pi.id))
    ).all()
    require(
        len(requests) == 1
        and requests[0].state == "settled"
        and requests[0].response_sha256 == pi.result_json.get("text_sha256")
        and requests[0].approved_request_sha256 == pi.approved_request_sha256,
        "ambiguous_provider_receipt",
    )
    return pi


class WorkflowRunner:
    def __init__(self, kernel, cognition):
        self.k, self.cognition = kernel, cognition
        self.tasks = {}
        self.closing = False

    async def authorize_dispatch(self, session, call):
        """Host callback at PI-01B's actual dispatch fence, inside its existing transaction."""
        try:
            run_id = call.input_json["workflow_run_id"]
            execution = await session.get(WorkflowExecution, run_id)
            _, run, grant, _, approved = await self._authority(session, run_id, execution.owner)
            stage = await session.get(WorkflowStageRun, call.input_json["workflow_stage_id"])
            require(
                stage is not None
                and stage.run_id == run.id
                and stage.state == states.RUNNING
                and stage.model_invocation_id == call.id
                and call.status == "reserved"
                and call.investigation_id == run.investigation_id
                and grant.models.get(call.role) == call.model
                and call.input_json["context"] == approved,
                "dispatch_stage_binding",
            )
            return True
        except (asyncio.CancelledError, ValueError, KeyError, AttributeError):
            return False

    async def start(self, authorization_id):
        ledger = {}

        async def admission():
            ledger["view"] = await self._start(authorization_id, ledger)

        try:
            await complete_despite_cancel(admission())
            return ledger["view"]
        except asyncio.CancelledError:
            if ledger.get("created"):
                async with self.k.db.sessions() as session:
                    exists = await session.get(WorkflowExecution, ledger["created"])
                if exists is not None:
                    await complete_despite_cancel(self.cancel(ledger["created"]))
            raise

    async def _start(self, authorization_id, ledger):
        """Transfer an already admitted inquiry to one durable owner grant. No dispatch."""
        require(not self.closing, "runner_closed")
        try:
            async with self.k.lock, self.k.db.sessions.begin() as session:
                prior = await session.scalar(
                    select(WorkflowExecution).where(
                        WorkflowExecution.authorization_id == authorization_id
                    )
                )
                if prior:
                    require(prior.instance_id == self.k.instance_id, "record_unavailable")
                    event = await session.scalar(select(Event).where(Event.id == authorization_id))
                    require(
                        event is not None and digest(event.payload) == prior.authorization_sha256,
                        "conflicting_authorization_replay",
                    )
                    return store.run_view(await session.get(WorkflowRun, prior.run_id))
                grant, spec, definition, inquiry, approved, authorization_hash = await authorized(
                    session, self.k, authorization_id
                )
                executable(spec, grant)
                if any(stage.type == "pi_agent" for stage in spec.stages):
                    require(
                        grant.outbound_approved and self.k.settings.alive_model_transport == "pi",
                        "pi_and_outbound_approval_required",
                    )
                require(inquiry.state == "INVESTIGATING", "inquiry_ownership_required")
                require(
                    not inquiry.snapshot
                    and inquiry.usage.get("calls", 0) == 0
                    and (self.cognition.worker is None or self.cognition.worker.done()),
                    "unclaimed_governor_inquiry_required",
                )
                require(grant.max_model_calls <= inquiry.budget["calls"], "governor_budget")
                deadline = min(grant.expires_at, now() + timedelta(seconds=grant.wall_seconds))
                view, _ = await store.create_run(
                    session,
                    self.k,
                    definition,
                    input_ref="event:" + grant.context_event_id,
                    input_sha256=digest(grant.inputs),
                    goal_id=grant.goal_id,
                    investigation_id=inquiry.id,
                    trigger="authorized-execution",
                    authorization_ref=authorization_id,
                    budget={
                        "max_model_calls": grant.max_model_calls,
                        "max_output_tokens": grant.max_output_tokens,
                        "wall_seconds": grant.wall_seconds,
                    },
                    idempotency_key=grant.idempotency_key,
                )
                session.add(
                    WorkflowExecution(
                        run_id=view["id"],
                        authorization_id=authorization_id,
                        authorization_sha256=authorization_hash,
                        investigation_id=inquiry.id,
                        instance_id=self.k.instance_id,
                        slot=self.k.instance_id,
                        deadline=deadline,
                    )
                )
                ledger["created"] = view["id"]
                inquiry.snapshot = approved | {
                    "workflow_run_id": view["id"],
                    "retrieval_mode": "authorized_exact_context",
                    "model_versions": {"provider": "meta", "roles": grant.models}
                    if grant.max_model_calls
                    else {"provider": "not_invoked"},
                }
                return view
        except IntegrityError:
            # No dispatch occurred. A retry can read an identical winning grant; never infer it.
            async with self.k.db.sessions() as session:
                prior = await session.scalar(
                    select(WorkflowExecution).where(
                        WorkflowExecution.authorization_id == authorization_id,
                        WorkflowExecution.instance_id == self.k.instance_id,
                    )
                )
                require(prior is not None, "execution_identity_or_instance_slot_conflict")
                return store.run_view(await session.get(WorkflowRun, prior.run_id))

    async def _authority(self, session, run_id, owner):
        execution = await session.get(WorkflowExecution, run_id)
        run = await session.get(WorkflowRun, run_id)
        if execution is not None and execution.cancel_requested:
            raise asyncio.CancelledError()
        require(
            execution is not None
            and run is not None
            and execution.instance_id == run.instance_id == self.k.instance_id
            and execution.owner == owner
            and execution.slot == self.k.instance_id
            and not execution.cancel_requested
            and aware(execution.deadline) > now()
            and run.status == states.RUNNING,
            "execution_authority_lost",
        )
        grant, spec, definition, inquiry, context, _ = await authorized(
            session, self.k, execution.authorization_id, execution.authorization_sha256
        )
        executable(spec, grant)
        require(
            run.definition_id == definition.id
            and run.definition_sha256 == grant.definition_sha256
            and run.workflow_name == spec.name
            and run.workflow_version == spec.version
            and run.investigation_id == inquiry.id == execution.investigation_id
            and run.goal_id == grant.goal_id
            and run.authorization_ref == execution.authorization_id
            and run.budget_json
            == {
                "max_model_calls": grant.max_model_calls,
                "max_output_tokens": grant.max_output_tokens,
                "wall_seconds": grant.wall_seconds,
            }
            and run.input_sha256 == digest(grant.inputs),
            "run_identity_changed",
        )
        return execution, run, grant, spec, context

    async def execute(self, run_id):
        require(not self.closing, "runner_closed")
        owner = uid()
        ledger = {}

        async def claim():
            async with self.k.lock, self.k.db.sessions.begin() as session:
                claimed = await session.execute(
                    update(WorkflowRun)
                    .where(
                        WorkflowRun.id == run_id,
                        WorkflowRun.instance_id == self.k.instance_id,
                        WorkflowRun.status == states.PENDING,
                        WorkflowRun.id.in_(
                            select(WorkflowExecution.run_id).where(
                                WorkflowExecution.instance_id == self.k.instance_id
                            )
                        ),
                    )
                    .values(status=states.RUNNING, started_at=now())
                )
                execution = await session.get(WorkflowExecution, run_id)
                require(
                    execution is not None and execution.instance_id == self.k.instance_id,
                    "record_unavailable",
                )
                if claimed.rowcount == 1:
                    execution.owner = owner
                    ledger["claimed"] = True
                    self.k.add_event(
                        session,
                        "workflow.execution.claimed",
                        {"run_id": run_id},
                        source="workflow",
                        correlation=run_id,
                    )

        try:
            await complete_despite_cancel(claim())
            if not ledger.get("claimed"):
                return await store.get_run(self.k, run_id)
            self.tasks[run_id] = asyncio.current_task()
            require(not self.closing, "runner_closed")
            async with self.k.db.sessions() as session:
                execution, _, _, spec, _ = await self._authority(session, run_id, owner)
                seconds = (aware(execution.deadline) - now()).total_seconds()
            async with asyncio.timeout(seconds):
                for stage in order(spec):
                    await self._stage(run_id, owner, stage)
                await self._finish(run_id, owner)
        except asyncio.CancelledError:
            if ledger.get("claimed"):
                await complete_despite_cancel(
                    self._abandon(run_id, owner, "cancelled", states.CANCELLED)
                )
            else:
                raise
        except Exception as error:
            if not ledger.get("claimed"):
                raise
            reason = (
                "timeout"
                if isinstance(error, TimeoutError)
                else (str(error) if isinstance(error, Refused) else "result_persistence_failure")
            )
            await complete_despite_cancel(self._abandon(run_id, owner, reason, states.FAILED))
        finally:
            if self.tasks.get(run_id) is asyncio.current_task():
                self.tasks.pop(run_id, None)
        return await store.get_run(self.k, run_id)

    async def _stage(self, run_id, owner, stage):
        async with self.k.lock, self.k.db.sessions.begin() as session:
            _, run, grant, spec, approved = await self._authority(session, run_id, owner)
            rows = (
                await session.scalars(
                    select(WorkflowStageRun).where(WorkflowStageRun.run_id == run_id)
                )
            ).all()
            by_id = {row.stage_id: row for row in rows}
            row = by_id[stage.id]
            require(
                row.operation == stage.operation
                and row.stage_type == stage.type
                and row.attempt == 1,
                "stage_identity_changed",
            )
            require(
                all(by_id[name].state == states.COMPLETED for name in stage.depends_on),
                "dependencies_incomplete",
            )
            outputs, dependencies = {}, {}
            for previous in rows:
                if previous.state == states.COMPLETED:
                    data = await result_event(session, previous)
                    outputs[previous.stage_id] = data
                    if previous.stage_id in stage.depends_on:
                        dependencies[previous.stage_id] = {
                            "operation": previous.operation,
                            "output": data,
                            "validation_status": previous.validation_status,
                        }
            data = inputs_for(stage, outputs, grant.inputs)
            changed = await session.execute(
                update(WorkflowStageRun)
                .where(
                    WorkflowStageRun.id == row.id,
                    WorkflowStageRun.state == states.PENDING,
                )
                .values(
                    state=states.RUNNING,
                    started_at=now(),
                    input_sha256=digest(data),
                    input_ref="workflow:" + run_id,
                )
            )
            require(changed.rowcount == 1, "stage_claim_lost")
            self.k.add_event(
                session,
                "workflow.stage.claimed",
                {"run_id": run_id, "stage_id": row.id},
                source="workflow",
                correlation=run_id,
            )
            context = StageContext(
                self.k,
                self.cognition,
                run_id,
                row.id,
                stage,
                run.investigation_id,
                owner,
                data,
                approved,
                dependencies,
                run.definition_sha256,
                digest(data),
            )
        try:
            async with asyncio.timeout(stage.limits.timeout_seconds):
                result = await ADAPTERS[stage.operation](context)
        except Refused:
            raise
        except Exception:
            raise Refused("adapter_execution_failure") from None
        try:
            output_valid(stage, result.output)
        except (ValueError, TypeError):
            raise Refused("output_validation_failure") from None
        try:
            await self._persist_result(run_id, owner, stage, context, result)
        except Refused:
            raise
        except Exception:
            raise Refused("result_persistence_failure") from None

    async def _persist_result(self, run_id, owner, stage, context, result):
        async with self.k.lock, self.k.db.sessions.begin() as session:
            await self._authority(session, run_id, owner)
            row = await session.get(WorkflowStageRun, context.stage_id)
            require(row.state == states.RUNNING, "stage_settlement_ownership")
            if stage.type == "pi_agent":
                pi = await pi_facts(session, self.k, row)
                row.pi_run_id = pi.id
            if result.artifact is not None:
                session.add(
                    CognitiveMessage(
                        id=row.id,
                        investigation_id=context.inquiry_id,
                        sender="investigator",
                        recipient="governor",
                        message_type="result",
                        content=result.artifact,
                    )
                )
            event = self.k.add_event(
                session,
                "workflow.stage.result",
                {
                    "run_id": run_id,
                    "stage_id": row.id,
                    "output": result.output,
                },
                source="workflow",
                correlation=run_id,
            )
            row.output_ref = "event:" + str(event.event_id)
            row.output_sha256 = digest(result.output)
            row.validation_status = result.validation_status
            row.evidence_refs = list(result.evidence_refs)
            row.state = states.advance(row.state, states.COMPLETED, states.STAGE_TRANSITIONS)
            row.finished_at = now()

    async def _finish(self, run_id, owner):
        async with self.k.lock, self.k.db.sessions.begin() as session:
            _, run, _, _, _ = await self._authority(session, run_id, owner)
            rows = (
                await session.scalars(
                    select(WorkflowStageRun).where(WorkflowStageRun.run_id == run_id)
                )
            ).all()
            require(
                all(row.state == states.COMPLETED for row in rows), "required_stages_incomplete"
            )
            inquiry = await session.get(Investigation, run.investigation_id)
            self.cognition._transition(session, inquiry, "EVALUATING")
            self.cognition._transition(session, inquiry, "EXECUTING")
            await self.cognition.finish_in_session(
                session,
                inquiry.id,
                "COMPLETED",
                {
                    "effect": "none",
                    "reason": "workflow_result_retained",
                    "workflow_run_id": run_id,
                },
            )
            execution = await session.get(WorkflowExecution, run_id)
            run = await session.get(WorkflowRun, run_id)
            require(execution.owner == owner and not execution.cancel_requested, "finish_ownership")
            run.status = states.advance(run.status, states.COMPLETED, states.RUN_TRANSITIONS)
            run.finished_at, run.terminal_reason = now(), "required_stages_completed"
            execution.slot = None
            self.k.add_event(
                session,
                "workflow.execution.completed",
                {"run_id": run_id},
                source="workflow",
                correlation=run_id,
            )

    async def _abandon(self, run_id, owner, reason, terminal):
        async with self.k.lock, self.k.db.sessions.begin() as session:
            execution = await session.get(WorkflowExecution, run_id)
            run = await session.get(WorkflowRun, run_id)
            if execution.owner is None and run.status == states.PENDING:
                execution.owner = owner
                run.status = states.advance(run.status, states.RUNNING, states.RUN_TRANSITIONS)
            if execution.owner != owner or run.status in states.RUN_TERMINAL:
                return
            rows = (
                await session.scalars(
                    select(WorkflowStageRun).where(WorkflowStageRun.run_id == run_id)
                )
            ).all()
            for row in rows:
                if row.state in states.STAGE_TERMINAL:
                    continue
                target = states.CANCELLED if row.state == states.PENDING else terminal
                if row.model_invocation_id is not None:
                    pi = await session.scalar(
                        select(PiRun).where(PiRun.reservation_ref == row.model_invocation_id)
                    )
                    if pi is not None:
                        row.pi_run_id = pi.id
                        requests = (
                            await session.scalars(
                                select(PiProviderRequest).where(PiProviderRequest.run_id == pi.id)
                            )
                        ).all()
                        if any(
                            request.error_category == "workflow_authority_revoked"
                            for request in requests
                        ):
                            reason = "authority_refused"
                        possible = (
                            pi.state not in ("FAILED", "CANCELLED")
                            or any(
                                request.state in ("dispatched", "ambiguous", "settled")
                                for request in requests
                            )
                            or pi.terminal_reason == "pi_cleanup_unconfirmed"
                        )
                        if possible:
                            target = terminal = states.UNKNOWN
                            row.uncertainty = "unknown_outcome"
                row.state = states.advance(row.state, target, states.STAGE_TRANSITIONS)
                row.error_category, row.finished_at = reason[:64], now()
            run.status = states.advance(run.status, terminal, states.RUN_TRANSITIONS)
            run.finished_at, run.terminal_reason = now(), reason[:120]
            execution.slot = None
            inquiry_id = run.investigation_id
            self.k.add_event(
                session,
                "workflow.execution.ended",
                {
                    "run_id": run_id,
                    "status": terminal,
                    "reason": reason[:120],
                },
                source="workflow",
                correlation=run_id,
            )
            await self.cognition.finish_in_session(
                session,
                inquiry_id,
                "CANCELLED" if terminal == states.CANCELLED else "FAILED",
                {"effect": "none", "reason": "workflow_stopped"},
                truncated=True,
            )

    async def recover(self):
        """Startup after cognition and Pi recovery. Consult receipts; never resume or dispatch."""
        require(not self.tasks, "recovery_requires_quiescence")
        async with self.k.db.sessions() as session:
            ids = list(
                await session.scalars(
                    select(WorkflowExecution.run_id)
                    .join(WorkflowRun)
                    .where(
                        WorkflowExecution.instance_id == self.k.instance_id,
                        ~WorkflowRun.status.in_(states.RUN_TERMINAL),
                    )
                )
            )
        for run_id in ids:
            owner = uid()
            async with self.k.lock, self.k.db.sessions.begin() as session:
                execution = await session.get(WorkflowExecution, run_id)
                run = await session.get(WorkflowRun, run_id)
                execution.owner = owner
                if run.status == states.PENDING:
                    run.status = states.advance(run.status, states.RUNNING, states.RUN_TRANSITIONS)
            await self._abandon(run_id, owner, "interrupted_requires_review", states.CANCELLED)

    async def cancel(self, run_id):
        async with self.k.lock, self.k.db.sessions.begin() as session:
            execution = await session.get(WorkflowExecution, run_id)
            require(
                execution is not None and execution.instance_id == self.k.instance_id,
                "record_unavailable",
            )
            execution.cancel_requested = True
        task = self.tasks.get(run_id)
        if task is not None:
            task.cancel()
            await asyncio.gather(task, return_exceptions=True)
        else:
            async with self.k.db.sessions() as session:
                run = await session.get(WorkflowRun, run_id)
            if run.status == states.PENDING:
                await self.execute(run_id)

    async def close(self):
        self.closing = True
        tasks = list(self.tasks.values())
        for task in tasks:
            task.cancel()
        await asyncio.gather(*tasks, return_exceptions=True)
        if self.k.ready:
            await self.recover()


async def artifact_view(kernel, run_id, stage_id):
    """Owner-scoped retained result only; no prompts, raw context or execution on read."""
    async with kernel.db.sessions() as session:
        run = await session.get(WorkflowRun, run_id)
        execution = await session.get(WorkflowExecution, run_id)
        require(
            run is not None
            and execution is not None
            and run.instance_id == execution.instance_id == kernel.instance_id,
            "record_unavailable",
        )
        stage = await session.scalar(
            select(WorkflowStageRun).where(
                WorkflowStageRun.run_id == run_id,
                WorkflowStageRun.stage_id == stage_id,
                WorkflowStageRun.operation == "result.record",
            )
        )
        require(stage is not None and stage.state == states.COMPLETED, "artifact_unavailable")
        output = await result_event(session, stage)
        artifact = await session.get(CognitiveMessage, output["artifact_id"])
        require(
            artifact is not None
            and artifact.id == stage.id
            and artifact.investigation_id == run.investigation_id
            and digest(artifact.content) == output["sha256"]
            and artifact.content["run_id"] == run.id
            and artifact.content["stage_id"] == stage.stage_id
            and artifact.content["definition_sha256"] == run.definition_sha256
            and artifact.content["input_sha256"] == stage.input_sha256,
            "artifact_integrity",
        )
        from alive.workflows.context import OWNER, Grant

        authorization = await session.scalar(
            select(Event).where(Event.id == execution.authorization_id)
        )
        require(
            authorization is not None
            and digest(authorization.payload) == execution.authorization_sha256,
            "authorization_integrity",
        )
        grant = Grant.model_validate(authorization.payload)
        source = await session.scalar(select(Event).where(Event.id == grant.context_event_id))
        require(
            source is not None and digest(source.payload) == grant.context_sha256,
            "historical_source_integrity",
        )
        withdrawn = await session.scalar(
            select(Event.id)
            .where(
                Event.instance_id == kernel.instance_id,
                Event.source == OWNER,
                Event.event_type == "workflow.context.withdrawn",
                Event.payload["source_event_id"].as_string() == source.id,
            )
            .limit(1)
        )
        content = artifact.content
        return {
            key: content[key]
            for key in (
                "kind",
                "schema",
                "run_id",
                "stage_id",
                "definition_sha256",
                "input_sha256",
                "classification",
                "created_at",
                "result",
                "assessment",
                "evidence_refs",
                "intelligence_episode_id",
                "independent_feedback",
            )
        } | {
            "artifact_id": artifact.id,
            "sha256": output["sha256"],
            "source_status": "withdrawn" if withdrawn else "unchanged",
            "run_status": run.status,
            "terminal_reason": run.terminal_reason,
            "stage_state": stage.state,
            "stage_validation": store.validation_view(stage),
            "stage_uncertainty": stage.uncertainty,
            "workflow_completed": run.status == states.COMPLETED,
            "context_provenance": {
                "context_event_id": grant.context_event_id,
                "context_sha256": grant.context_sha256,
                "approved": grant.context_provenance.model_dump()
                if grant.context_provenance
                else None,
                "original_source": source.source,
                "original_event_type": source.event_type,
                "semantic_status": "unverified",
                "authorization_is_source_authentication": False,
            },
        }
