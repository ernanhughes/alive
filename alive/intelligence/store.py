"""Trusted explicit INT-02 persistence adapter. No dispatch, scheduler or HTTP write path.

Only independently controlled fixture custody is enabled. Real model/Pi records may
be inspected, but an Intelligence-compatible reserved invocation is not yet qualified.
"""

import asyncio
from datetime import UTC
from uuid import UUID

from sqlalchemy import select, update
from sqlalchemy.exc import IntegrityError, OperationalError

from alive.models import Event, Goal
from alive.workflows.models import WorkflowDefinition, WorkflowRun, WorkflowStageRun
from alive.workflows.spec import hash_of_stored, parse_definition

from .contracts import Context, Observation, OutcomeFeedback, RunResult, digest
from .decision import propose
from .engine import reconcile
from .models import (
    IntelligenceEpisode as Episode,
)
from .models import (
    IntelligenceFeedback as Feedback,
)
from .models import (
    IntelligenceLearningUpdate as LearningUpdate,
)
from .models import IntelligenceMeasurementUse
from .models import (
    IntelligenceState as LearningState,
)
from .policies.empirical import EmpiricalPolicy

CUSTODIAN = "intelligence-fixture-custodian"
OBSERVER = "intelligence-fixture-observer"


class Refused(ValueError):
    """A bounded identity, trust, integrity or compatibility failure."""


class ConcurrentChange(RuntimeError):
    pass


def require(condition, message):
    if not condition:
        raise Refused(message)


def aware(value):
    return value.replace(tzinfo=UTC) if value.tzinfo is None else value


async def owned(session, model, identity, instance):
    row = await session.get(model, identity)
    require(row is not None and row.instance_id == instance, "Record unavailable")
    return row


async def custody(session, instance, identity, *, source, kind):
    row = await session.scalar(select(Event).where(Event.id == identity))
    require(
        row is not None
        and row.instance_id == instance
        and row.source == source
        and row.event_type == kind,
        "Independent custody record required",
    )
    return row


async def evidence_status(session, instance, source_id):
    notices = await session.scalars(
        select(Event).where(
            Event.instance_id == instance,
            Event.source == CUSTODIAN,
            Event.event_type == "intelligence.custody.withdrawn",
        )
    )
    return (
        "withdrawn"
        if any(n.payload.get("source_event_id") == source_id for n in notices)
        else "active"
    )


def policies(state):
    active = EmpiricalPolicy.model_validate(state.active_json)
    candidate = EmpiricalPolicy.model_validate(state.candidate_json)
    require(
        active.hash == state.active_hash
        and candidate.hash == state.candidate_hash
        and candidate.revision == state.revision,
        "Policy integrity failure",
    )
    require(not state.quarantined, "Learning state quarantined pending reviewed rebuild")
    return active, candidate


async def workflow(session, instance, stage_id, goal_id):
    stage = await session.get(WorkflowStageRun, stage_id)
    require(stage is not None, "Workflow stage unavailable")
    run = await owned(session, WorkflowRun, stage.run_id, instance)
    definition = await session.get(WorkflowDefinition, run.definition_id)
    require(definition is not None, "Workflow definition unavailable")
    # A retained definition (hash-verified below): linkage must not depend on today's catalogue.
    spec = parse_definition(definition.definition_json, operations=None)
    matching = [s for s in spec.stages if s.id == stage.stage_id]
    require(
        run.goal_id == goal_id
        and run.workflow_name == definition.name
        and run.workflow_version == definition.version
        and run.schema_version == definition.schema_version
        and run.definition_sha256 == definition.definition_sha256
        and hash_of_stored(definition.definition_json) == definition.definition_sha256
        and len(matching) == 1
        and matching[0].operation == stage.operation
        and matching[0].type == stage.stage_type,
        "Workflow identity mismatch",
    )
    return stage, run


async def verify_episode(session, row):
    require(digest(row.snapshot_json) == row.snapshot_hash, "Historical snapshot changed")
    source = await custody(
        session,
        row.instance_id,
        row.source_event_id,
        source=CUSTODIAN,
        kind="intelligence.fixture.context",
    )
    require(digest(source.payload) == row.source_hash, "Historical evidence changed")
    require(digest(row.snapshot_json["context"]) == row.context_hash, "Historical context changed")
    snapshot = row.snapshot_json
    require(
        snapshot["previous_id"] == row.previous_id
        and snapshot["workflow_stage_id"] == row.workflow_stage_id
        and snapshot["source_event_id"] == row.source_event_id
        and snapshot["assessment"]["proposal"]["id"] == row.proposal_id
        and snapshot["decision"]
        == {
            "active_choice": row.active_choice,
            "proposed_action": row.proposed_action,
            "shadow_action": row.shadow_action,
            "authorized_action": row.authorized_action,
            "executed_action": row.executed_action,
        },
        "Historical decision/reference changed",
    )
    require(
        source.payload["context"] == snapshot["context"]
        and source.payload["observation"] == snapshot["observation"],
        "Source snapshot mismatch",
    )
    context = Context.model_validate(snapshot["context"])
    stage, run = await workflow(session, row.instance_id, row.workflow_stage_id, context.goal_id)
    require(
        run.id == snapshot["workflow_run_id"]
        and run.definition_sha256 == snapshot["definition_hash"]
        and run.workflow_version == snapshot["workflow_version"]
        and run.input_sha256 == row.context_hash
        and stage.state == run.status == "PENDING"
        and stage.validation_status == "not_run"
        and stage.uncertainty == "none"
        and stage.pi_run_id is None
        and stage.model_invocation_id is None
        and row.pi_run_id is None
        and row.model_invocation_id is None,
        "Historical fixture workflow changed",
    )


async def create_state(kernel, goal_id):
    """Trusted admin/test entry point. No policy selection/promotion parameter exists."""
    async with kernel.lock, kernel.db.sessions.begin() as session:
        await owned(session, Goal, goal_id, kernel.instance_id)
        cold = EmpiricalPolicy(origin="fixture")
        row = LearningState(
            instance_id=kernel.instance_id,
            goal_id=goal_id,
            active_json=cold.model_dump(mode="json"),
            active_hash=cold.hash,
            candidate_json=cold.model_dump(mode="json"),
            candidate_hash=cold.hash,
        )
        session.add(row)
        await session.flush()
        kernel.add_event(
            session,
            "intelligence.state.created",
            {"state_id": row.id},
            source="intelligence",
            correlation=row.id,
        )
        return row.id


async def record_assessment(
    kernel, *, state_id, stage_id, source_event_id, result, previous_id=None, shadow=None
):
    """Consume an isolated validated fixture result and exact independently custodied context.

    PI-02A stages stay unchanged. No inference capability or executor is accepted here.
    """
    result = RunResult.model_validate(result)
    require(
        result.status in ("proposed", "abstained")
        and result.proposal is not None
        and result.reasoning is not None,
        "Validated assessment required",
    )
    require(
        result.reasoning.invocation.provenance == "fixture"
        and result.reasoning.invocation.provider == "fixture"
        and result.reasoning.invocation.prompt_tokens == 0
        and result.reasoning.invocation.completion_tokens == 0
        and result.reasoning.invocation.receipt_id is None,
        "Live Intelligence admission unavailable; fixture result required",
    )
    async with kernel.lock, kernel.db.sessions.begin() as session:
        state = await owned(session, LearningState, state_id, kernel.instance_id)
        active, candidate = policies(state)
        source = await custody(
            session,
            kernel.instance_id,
            source_event_id,
            source=CUSTODIAN,
            kind="intelligence.fixture.context",
        )
        require(
            await evidence_status(session, kernel.instance_id, source_event_id) == "active",
            "Evidence withdrawn",
        )
        require(
            source.payload.get("contract") == "intelligence-fixture-context/v1",
            "Unsupported context custody contract",
        )
        observation = Observation.model_validate(source.payload["observation"])
        context = Context.model_validate(source.payload["context"])
        require(
            observation.goal_id == state.goal_id == context.goal_id
            and source.payload.get("goal_id") == state.goal_id
            and observation.origin == context.origin == "fixture",
            "Evidence goal/origin mismatch",
        )
        reconcile(observation, context, context.evidence)
        require(
            aware(source.occurred_at) >= observation.observed_at,
            "Context custody precedes observation",
        )
        refs = {e.id for e in context.evidence}
        require(all(set(c.citations) <= refs for c in result.reasoning.claims), "Unknown citation")
        expected = propose(observation, context, candidate, result.reasoning)
        require(expected == result.proposal, "Proposal/context/policy substitution")
        require(
            result.status == ("proposed" if expected.action else "abstained"),
            "Assessment status inconsistent with proposal",
        )
        stage, run = await workflow(session, kernel.instance_id, stage_id, state.goal_id)
        require(run.input_sha256 == digest(context), "Workflow context hash mismatch")
        require(
            stage.state == "PENDING"
            and run.status == "PENDING"
            and stage.validation_status == "not_run"
            and stage.uncertainty == "none",
            "Fixture attachment requires unexecuted pending workflow records",
        )
        require(
            stage.pi_run_id is None and stage.model_invocation_id is None,
            "Fixture attachment cannot relabel model/Pi execution",
        )
        if previous_id:
            earlier = await owned(session, Episode, previous_id, kernel.instance_id)
            require(earlier.state_id == state.id, "Revisit belongs to different learning chain")
            await verify_episode(session, earlier)
            require(
                observation.observed_at
                >= Observation.model_validate(earlier.snapshot_json["observation"]).observed_at,
                "Revisit precedes original",
            )
        allowed = tuple(
            c for c in context.candidates if c.expected_cost <= context.reported_resources
        )
        chosen, _ = active.rank(allowed)
        if shadow:
            from .contracts import ShadowResult

            shadow = ShadowResult.model_validate(shadow)
        snapshot = {
            "observation": observation.model_dump(mode="json"),
            "context": context.model_dump(mode="json"),
            "assessment": result.model_dump(mode="json"),
            "active_policy": active.model_dump(mode="json"),
            "candidate_policy": candidate.model_dump(mode="json"),
            "definition_hash": run.definition_sha256,
            "workflow_run_id": run.id,
            "workflow_version": run.workflow_version,
            "previous_id": previous_id,
            "workflow_stage_id": stage.id,
            "source_event_id": source.id,
            "decision": {
                "active_choice": chosen.action if chosen else None,
                "proposed_action": expected.action.action if expected.action else None,
                "shadow_action": shadow.action if shadow else None,
                "authorized_action": None,
                "executed_action": None,
            },
            "shadow": shadow.model_dump(mode="json") if shadow else None,
            "trigger": "manual" if previous_id else "explicit-fixture-harness",
            "execution_basis": "fixture-backed; PI-02B unavailable; stage not executed",
        }
        row = Episode(
            id=observation.episode_id,
            instance_id=kernel.instance_id,
            state_id=state.id,
            workflow_stage_id=stage.id,
            source_event_id=source.id,
            source_hash=digest(source.payload),
            context_hash=digest(context),
            snapshot_json=snapshot,
            snapshot_hash=digest(snapshot),
            proposal_id=expected.id,
            proposed_action=expected.action.action if expected.action else None,
            active_choice=chosen.action if chosen else None,
            shadow_action=shadow.action if shadow else None,
            authorized_action=None,
            executed_action=None,
            previous_id=previous_id,
        )
        session.add(row)
        await session.flush()
        for name in (
            "episode.created",
            "proposal.recorded",
            "proposal.validated",
            "decision.recorded",
        ):
            kernel.add_event(
                session,
                "intelligence." + name,
                {
                    "episode_id": row.id,
                    "proposal_id": row.proposal_id,
                    "snapshot_hash": row.snapshot_hash,
                },
                source="intelligence",
                correlation=row.id,
            )
        if previous_id:
            kernel.add_event(
                session,
                "intelligence.revisit.proposed",
                {"episode_id": row.id, "previous_id": previous_id},
                source="intelligence",
                correlation=row.id,
            )
        return row.id


async def accept_feedback(kernel, *, episode_id, source_event_id, feedback):
    """Trusted interface; rejected submissions get a separate bounded audit event."""
    try:
        return await _accept_feedback(
            kernel, episode_id=episode_id, source_event_id=source_event_id, feedback=feedback
        )
    except ValueError:
        try:
            correlation = str(UUID(str(episode_id)))
        except ValueError:
            correlation = None
        async with kernel.lock, kernel.db.sessions.begin() as session:
            kernel.add_event(
                session,
                "intelligence.feedback.rejected",
                {
                    "episode_ref": str(episode_id)[:100],
                    "reason": "identity_provenance_or_contract_rejected",
                },
                source="intelligence",
                correlation=correlation,
            )
        raise


async def _accept_feedback(kernel, *, episode_id, source_event_id, feedback):
    """One atomic local-DB update. Unique keys + optimistic CAS protect independent workers."""
    feedback = OutcomeFeedback.model_validate(feedback)
    for attempt in range(3):
        try:
            async with kernel.lock, kernel.db.sessions.begin() as session:
                episode = await owned(session, Episode, episode_id, kernel.instance_id)
                await verify_episode(session, episode)
                state = await owned(session, LearningState, episode.state_id, kernel.instance_id)
                _, candidate = policies(state)
                source = await custody(
                    session,
                    kernel.instance_id,
                    source_event_id,
                    source=OBSERVER,
                    kind="intelligence.fixture.outcome",
                )
                require(
                    source.payload
                    == {
                        "contract": "intelligence-fixture-outcome/v1",
                        "episode_id": episode.id,
                        "snapshot_hash": episode.snapshot_hash,
                        "feedback": feedback.model_dump(mode="json"),
                    },
                    "Feedback source/decision/payload substitution",
                )
                prior = await session.scalar(
                    select(Feedback).where(
                        (Feedback.id == feedback.id)
                        | (Feedback.episode_id == episode.id)
                        | (Feedback.source_event_id == source.id)
                    )
                )
                if prior:
                    require(
                        prior.id == feedback.id
                        and prior.instance_id == kernel.instance_id
                        and prior.episode_id == episode.id
                        and prior.source_event_id == source.id
                        and prior.outcome_hash == digest(feedback),
                        "Conflicting feedback identity",
                    )
                    return "duplicate"
                context = Context.model_validate(episode.snapshot_json["context"])
                observation = Observation.model_validate(episode.snapshot_json["observation"])
                require(
                    feedback.episode_id == episode.id
                    and feedback.goal_id == state.goal_id
                    and feedback.proposal_id == episode.proposal_id
                    and feedback.observed_action == episode.active_choice,
                    "Outcome must bind separate frozen decision, not candidate proposal",
                )
                require(
                    feedback.origin == "fixture"
                    and feedback.split == context.split == "train"
                    and feedback.executed
                    and feedback.completion == "completed"
                    and observation.observed_at <= feedback.event_at <= aware(source.occurred_at),
                    "Completed independently observed training fixture required",
                )
                require(
                    await evidence_status(session, kernel.instance_id, episode.source_event_id)
                    == "active",
                    "Decision evidence withdrawn",
                )
                known = {e.id for e in context.evidence}
                source_ids = {e.source_id for e in context.evidence}
                measurements = feedback.measurements
                require(
                    len({e.id for e in measurements}) == len(measurements), "Duplicate measurement"
                )
                fingerprints = {}
                for measurement in measurements:
                    previous = fingerprints.setdefault(
                        measurement.source_id, measurement.fingerprint
                    )
                    require(previous == measurement.fingerprint, "Conflicting measurement source")
                require(
                    all(
                        e.id not in known
                        and e.source_id not in source_ids
                        and e.origin == "fixture"
                        and e.trust == "admitted"
                        and e.qualification == "current"
                        and observation.observed_at <= e.observed_at <= feedback.event_at
                        for e in measurements
                    ),
                    "Invalid independent measurement",
                )
                # Existing algorithm, updated from actual frozen decision feedback only.
                after = candidate.updated(feedback.observed_action, feedback.reward)
                changed = await session.execute(
                    update(LearningState)
                    .where(
                        LearningState.id == state.id,
                        LearningState.candidate_hash == candidate.hash,
                        LearningState.revision == candidate.revision,
                        LearningState.quarantined.is_(False),
                    )
                    .values(
                        candidate_json=after.model_dump(mode="json"),
                        candidate_hash=after.hash,
                        revision=after.revision,
                    )
                )
                if changed.rowcount != 1:
                    raise ConcurrentChange("Concurrent learning change")
                session.add(
                    Feedback(
                        id=feedback.id,
                        instance_id=kernel.instance_id,
                        episode_id=episode.id,
                        source_event_id=source.id,
                        outcome_hash=digest(feedback),
                        payload_json=feedback.model_dump(mode="json"),
                        authority_class="controlled-fixture/v1",
                    )
                )
                await session.flush()
                for measurement in measurements:
                    session.add(
                        IntelligenceMeasurementUse(
                            instance_id=kernel.instance_id,
                            evidence_id=measurement.id,
                            observation_hash=digest(
                                {
                                    "source_id": measurement.source_id,
                                    "fingerprint": measurement.fingerprint,
                                    "observed_at": measurement.observed_at.isoformat(),
                                }
                            ),
                            feedback_id=feedback.id,
                        )
                    )
                learning = LearningUpdate(
                    state_id=state.id,
                    feedback_id=feedback.id,
                    algorithm=context.policy_id,
                    before_json=candidate.model_dump(mode="json"),
                    before_hash=candidate.hash,
                    after_json=after.model_dump(mode="json"),
                    after_hash=after.hash,
                )
                session.add(learning)
                await session.flush()
                for kind in ("feedback.submitted", "feedback.accepted", "learning.updated"):
                    kernel.add_event(
                        session,
                        "intelligence." + kind,
                        {
                            "episode_id": episode.id,
                            "feedback_id": feedback.id,
                            "update_id": learning.id,
                            "before_hash": candidate.hash,
                            "after_hash": after.hash,
                        },
                        source="intelligence",
                        correlation=episode.id,
                    )
                return "accepted"
        except (IntegrityError, ConcurrentChange, OperationalError) as error:
            # A concurrent transaction may have won the same unique outcome/decision key.
            if attempt == 2:
                raise Refused("Concurrent feedback conflict") from None
            if isinstance(error, OperationalError) and "locked" not in str(error).lower():
                raise
            await asyncio.sleep(0.01)
    raise AssertionError("unreachable")


async def quarantine_feedback(kernel, *, feedback_id, notice_event_id):
    """Append correction/revocation notice; quarantine estimates, never rewrite old reward."""
    async with kernel.lock, kernel.db.sessions.begin() as session:
        feedback = await owned(session, Feedback, feedback_id, kernel.instance_id)
        notice = await custody(
            session,
            kernel.instance_id,
            notice_event_id,
            source=OBSERVER,
            kind="intelligence.fixture.correction",
        )
        require(
            notice.payload.get("feedback_id") == feedback.id
            and notice.payload.get("status") in ("revoked", "corrected"),
            "Correction binding invalid",
        )
        episode = await owned(session, Episode, feedback.episode_id, kernel.instance_id)
        state = await owned(session, LearningState, episode.state_id, kernel.instance_id)
        if not state.quarantined:
            state.quarantined = True
            kernel.add_event(
                session,
                "intelligence.feedback.quarantined",
                {
                    "feedback_id": feedback.id,
                    "notice_event_id": notice.id,
                    "status": notice.payload["status"],
                },
                source="intelligence",
                correlation=episode.id,
            )


async def inspect_chain(kernel, state_id):
    """Read/replay only. Explicit allow-list view; no providers, updates or events."""
    async with kernel.db.sessions() as session:
        state = await owned(session, LearningState, state_id, kernel.instance_id)
        active = EmpiricalPolicy.model_validate(state.active_json)
        candidate = EmpiricalPolicy.model_validate(state.candidate_json)
        require(
            active.hash == state.active_hash and candidate.hash == state.candidate_hash,
            "Policy integrity failure",
        )
        episodes = (
            await session.scalars(
                select(Episode)
                .where(Episode.state_id == state.id)
                .order_by(Episode.created_at, Episode.id)
            )
        ).all()
        views = []
        updates = []
        for row in episodes:
            await verify_episode(session, row)
            stage, run = await workflow(
                session, kernel.instance_id, row.workflow_stage_id, state.goal_id
            )
            require(
                run.id == row.snapshot_json["workflow_run_id"]
                and run.definition_sha256 == row.snapshot_json["definition_hash"]
                and run.workflow_version == row.snapshot_json["workflow_version"],
                "Historical workflow identity changed",
            )
            feedback = await session.scalar(select(Feedback).where(Feedback.episode_id == row.id))
            learning = (
                await session.scalar(
                    select(LearningUpdate).where(LearningUpdate.feedback_id == feedback.id)
                )
                if feedback
                else None
            )
            if feedback:
                observed = OutcomeFeedback.model_validate(feedback.payload_json)
                require(feedback.outcome_hash == digest(observed), "Feedback history changed")
                independent = await custody(
                    session,
                    kernel.instance_id,
                    feedback.source_event_id,
                    source=OBSERVER,
                    kind="intelligence.fixture.outcome",
                )
                require(
                    independent.payload
                    == {
                        "contract": "intelligence-fixture-outcome/v1",
                        "episode_id": row.id,
                        "snapshot_hash": row.snapshot_hash,
                        "feedback": observed.model_dump(mode="json"),
                    },
                    "Independent feedback history changed",
                )
                require(learning is not None, "Accepted feedback missing learning update")
            if learning:
                require(
                    digest(learning.before_json) == learning.before_hash
                    and digest(learning.after_json) == learning.after_hash,
                    "Learning history changed",
                )
                before_policy = EmpiricalPolicy.model_validate(learning.before_json)
                after_policy = EmpiricalPolicy.model_validate(learning.after_json)
                require(
                    learning.algorithm == "empirical-outcome-mean-v1"
                    and before_policy.updated(observed.observed_action, observed.reward)
                    == after_policy,
                    "Learning result inconsistent with observed feedback",
                )
                updates.append((after_policy.revision, learning.before_hash, learning.after_hash))
            views.append(
                {
                    "id": row.id,
                    "proposal_id": row.proposal_id,
                    "previous_id": row.previous_id,
                    "workflow_run_id": run.id,
                    "workflow_stage_id": stage.id,
                    "definition_sha256": row.snapshot_json["definition_hash"],
                    "workflow_state": stage.state,
                    "source_event_id": row.source_event_id,
                    "source_hash": row.source_hash,
                    "context_hash": row.context_hash,
                    "snapshot_hash": row.snapshot_hash,
                    "evidence_status": await evidence_status(
                        session, kernel.instance_id, row.source_event_id
                    ),
                    "active_policy_choice": row.active_choice,
                    "intelligence_proposal": row.proposed_action,
                    "shadow_suggestion": row.shadow_action,
                    "authorized_action": row.authorized_action,
                    "executed_action": row.executed_action,
                    "authorization_status": "not_requested",
                    "execution_basis": row.snapshot_json["execution_basis"],
                    "model_invocation_id": row.model_invocation_id,
                    "pi_run_id": row.pi_run_id,
                    "feedback_id": feedback.id if feedback else None,
                    "feedback_status": (
                        "accepted_historical_quarantined" if state.quarantined else "accepted"
                    )
                    if feedback
                    else "unknown",
                    "observed_fixture_action": feedback.payload_json["observed_action"]
                    if feedback
                    else None,
                    "observed_reward": sum(c["value"] for c in feedback.payload_json["rewards"])
                    if feedback
                    else None,
                    "feedback_source_event_id": feedback.source_event_id if feedback else None,
                    "authority_class": feedback.authority_class if feedback else None,
                    "learning_update_id": learning.id if learning else None,
                    "before_hash": learning.before_hash if learning else None,
                    "after_hash": learning.after_hash if learning else None,
                }
            )
        previous_hash = state.active_hash
        for expected_revision, (revision, before_hash, after_hash) in enumerate(sorted(updates), 1):
            require(
                revision == expected_revision and before_hash == previous_hash,
                "Learning sequence changed",
            )
            previous_hash = after_hash
        require(
            previous_hash == state.candidate_hash and len(updates) == state.revision,
            "Learning state/history mismatch",
        )
        return {
            "id": state.id,
            "goal_id": state.goal_id,
            "active_hash": state.active_hash,
            "candidate_hash": state.candidate_hash,
            "candidate_revision": state.revision,
            "monitor_samples": candidate.monitor.n,
            "retrieve_samples": candidate.retrieve.n,
            "quarantined": state.quarantined,
            "episodes": views,
        }
