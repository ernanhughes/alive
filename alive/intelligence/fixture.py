"""Trusted synthetic INT-02 harness. Explicit calls only; never imported at startup.

This module writes controlled fixture custody through existing events. It is not
production evidence authority, a workflow executor or a public feedback endpoint.
"""

from datetime import timedelta

from sqlalchemy import select

from alive.models import Goal, now, uid
from alive.workflows.models import WorkflowStageRun
from alive.workflows.store import open_run, register_definition

from .contracts import Context, Observation, OutcomeFeedback, digest
from .engine import IntelligenceEngine
from .example import FixtureEvidence, FixtureFeedback, FixtureInvocation, inputs, observed_feedback
from .models import IntelligenceEpisode, IntelligenceState
from .policies.empirical import EmpiricalPolicy
from .store import CUSTODIAN, OBSERVER, create_state, inspect_chain, record_assessment

DEFINITION = {
    "schema_version": 1,
    "name": "intelligence-fixture",
    "version": 1,
    "title": "Intelligence fixture references",
    "stages": [
        {
            "id": "context",
            "title": "Context reference",
            "type": "deterministic",
            "operation": "context.prepare",
            "output_schema": {"properties": {"snapshot": {"type": "object"}}},
        }
    ],
}


async def start(kernel):
    async with kernel.lock, kernel.db.sessions.begin() as session:
        goal = Goal(
            id=uid(),
            instance_id=kernel.instance_id,
            title="INT-02 controlled Aster inquiry",
            origin="controlled-fixture",
            status="active",
        )
        session.add(goal)
        await session.flush()
        goal_id = goal.id
    await register_definition(kernel, DEFINITION, status="active", source="admin")
    return await create_state(kernel, goal_id)


async def assessment(kernel, state_id, *, previous_id=None, shadow=None):
    async with kernel.db.sessions() as session:
        state = await session.get(IntelligenceState, state_id)
        goal_id = state.goal_id
        candidate = EmpiricalPolicy.model_validate(state.candidate_json)
    at = now() - timedelta(seconds=1)
    observation, context = inputs(uid(), at=at)
    observation = Observation.model_validate(observation.model_dump() | {"goal_id": goal_id})
    context = Context.model_validate(context.model_dump() | {"goal_id": goal_id})
    run, _ = await open_run(
        kernel,
        "intelligence-fixture",
        1,
        goal_id=goal_id,
        input_sha256=digest(context),
        trigger="manual",
    )
    async with kernel.db.sessions() as session:
        stage = await session.scalar(
            select(WorkflowStageRun).where(WorkflowStageRun.run_id == run["id"])
        )
        stage_id = stage.id
    async with kernel.lock, kernel.db.sessions.begin() as session:
        event = kernel.add_event(
            session,
            "intelligence.fixture.context",
            {
                "contract": "intelligence-fixture-context/v1",
                "goal_id": goal_id,
                "observation": observation.model_dump(mode="json"),
                "context": context.model_dump(mode="json"),
            },
            source=CUSTODIAN,
            correlation=observation.episode_id,
        )
        source_id = str(event.event_id)
    engine = IntelligenceEngine(
        evidence=FixtureEvidence(), feedback=FixtureFeedback(), policy=candidate
    )
    result = await engine.analyze(
        observation, context, inference=FixtureInvocation(observation, context)
    )
    return await record_assessment(
        kernel,
        state_id=state_id,
        stage_id=stage_id,
        source_event_id=source_id,
        result=result,
        previous_id=previous_id,
        shadow=shadow,
    )


async def independent_outcome(kernel, episode_id, *, reward=-0.5, outcome_id=None):
    """Separately controlled fixture observer record; no Intelligence proposal certifies success."""
    async with kernel.db.sessions() as session:
        episode = await session.get(IntelligenceEpisode, episode_id)
        from .contracts import DecisionProposal, Evidence

        proposal = DecisionProposal.model_validate(episode.snapshot_json["assessment"]["proposal"])
        value = observed_feedback(proposal, reward=reward, outcome_id=outcome_id or uid())
        stamp = now()
        measurement = Evidence.model_validate(
            value.measurements[0].model_dump() | {"observed_at": stamp}
        )
        feedback = OutcomeFeedback.model_validate(
            value.model_dump()
            | {
                "observed_action": episode.active_choice,
                "event_at": stamp,
                "measurements": (measurement,),
            }
        )
        snapshot_hash = episode.snapshot_hash
    async with kernel.lock, kernel.db.sessions.begin() as session:
        event = kernel.add_event(
            session,
            "intelligence.fixture.outcome",
            {
                "contract": "intelligence-fixture-outcome/v1",
                "episode_id": episode_id,
                "snapshot_hash": snapshot_hash,
                "feedback": feedback.model_dump(mode="json"),
            },
            source=OBSERVER,
            correlation=episode_id,
        )
        return str(event.event_id), feedback


async def lifecycle(kernel):
    from .store import accept_feedback

    state_id = await start(kernel)
    first = await assessment(kernel, state_id)
    source, feedback = await independent_outcome(kernel, first)
    assert (
        await accept_feedback(kernel, episode_id=first, source_event_id=source, feedback=feedback)
        == "accepted"
    )
    await assessment(kernel, state_id, previous_id=first)
    return await inspect_chain(kernel, state_id)
