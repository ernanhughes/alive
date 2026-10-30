import asyncio

import pytest

from alive.intelligence.contracts import OutcomeFeedback, digest
from alive.intelligence.engine import IntelligenceEngine
from alive.intelligence.example import (
    FixtureEvidence,
    FixtureFeedback,
    FixtureInvocation,
    inputs,
    observed_feedback,
    run_example,
)
from alive.intelligence.policies.empirical import EmpiricalPolicy


def engine(*, evidence=None, verifier=None, **kwargs):
    return IntelligenceEngine(
        evidence=evidence or FixtureEvidence(),
        feedback=verifier or FixtureFeedback(),
        policy=EmpiricalPolicy(origin="fixture"),
        **kwargs,
    )


async def issued(e=None, **kwargs):
    e = e or engine()
    observation, context = inputs(**kwargs)
    capability = FixtureInvocation(observation, context)
    run = await e.analyze(observation, context, inference=capability)
    return e, run, capability


async def test_proposal_and_exact_request_trace():
    e, run, capability = await issued()
    assert run.status == "proposed"
    assert run.proposal.action.action == "monitor"
    assert run.proposal.executed is False
    assert run.proposal.required_authorization == "external_governor_required"
    assert run.reasoning.claims[0].kind == "model_opinion"
    assert run.reasoning.claims[0].citations == ("claim-episode-1",)
    assert [t.stage for t in run.trace] == ["input", "evidence", "invocation", "decision"]
    request = capability.requests[0]
    assert request.operation == "cognition.role"
    assert request.correlation == capability.binding.summary.reservation_id
    assert request.model == capability.binding.summary.model
    assert request.max_output == 1536
    assert request.schema["additionalProperties"] is False
    assert "UNTRUSTED DATA" in request.instructions
    assert digest(request.data) == capability.binding.payload_hash
    assert e.policy.revision == 0


@pytest.mark.parametrize("capability", [None, "approved", object()])
async def test_no_capability_no_dispatch(capability):
    observation, context = inputs()
    backend = FixtureInvocation(observation, context)
    result = await engine().analyze(observation, context, inference=capability)
    assert result.status == "abstained" and result.proposal is None
    assert backend.requests == []


async def test_wrong_capability_binding_no_dispatch():
    observation, context = inputs()
    capability = FixtureInvocation(*inputs("other-episode"))
    result = await engine().analyze(observation, context, inference=capability)
    assert result.status == "abstained" and capability.requests == []


async def test_completed_feedback_and_two_episode_revisit():
    result = await run_example()
    first = result["episode_1"]["proposal"]
    transition = result["feedback"]["transition"]
    later = result["episode_2"]
    assert first["action"]["action"] == "monitor" and first["executed"] is False
    assert transition["outcome"]["rewards"][0]["value"] == -0.5
    assert transition["before_version"] == 0 and transition["after_version"] == 1
    assert transition["before_samples"] == 0 and transition["after_samples"] == 1
    assert transition["before_policy_hash"] != transition["after_policy_hash"]
    assert transition["prediction_error"] is None
    assert later["current"]["proposal"]["action"]["action"] == "retrieve"
    assert later["frozen_action"] == "monitor"
    assert later["current"]["proposal"]["invocation"]["prompt_tokens"] == 0


async def test_revisit_preserves_dated_historical_context():
    from datetime import timedelta

    from alive.intelligence.contracts import Context, Evidence, History
    from alive.intelligence.example import NOW

    e, first, _ = await issued()
    observation, context = inputs("episode-2", at=NOW + timedelta(seconds=2))
    historical = Evidence.model_validate(
        inputs()[1].evidence[0].model_dump() | {"qualification": "historical"}
    )
    history = History(
        episode_id=first.proposal.episode_id,
        observed_at=NOW,
        origin="fixture",
        split="train",
        qualification="unqualified",
        evidence_refs=(historical.id,),
        summary="Historical claim, not verification of the current event.",
    )
    context = Context.model_validate(
        context.model_dump()
        | {
            "evidence": context.evidence + (historical,),
            "history": (history,),
        }
    )
    capability = FixtureInvocation(observation, context)
    result = await e.revisit(
        observation, context, earlier_proposal=first.proposal, inference=capability
    )
    assert result.current.status == "proposed"
    supplied = capability.requests[0].data["context"]
    assert supplied["history"][0]["qualification"] == "unqualified"
    assert supplied["evidence"][1]["qualification"] == "historical"
    assert supplied["history"][0]["observed_at"] == "2026-10-30T00:00:00Z"
    bad = Context.model_validate(
        context.model_dump()
        | {
            "history": (History.model_validate(history.model_dump() | {"split": "test"}),),
        }
    )
    rejected = await engine().analyze(
        observation, bad, inference=FixtureInvocation(observation, bad)
    )
    assert rejected.status == "failed"


async def test_duplicate_outcomes_and_proposals_cannot_train_twice():
    e, run, _ = await issued()
    feedback = observed_feedback(run.proposal)
    e.feedback.records[feedback.id] = feedback
    assert e.evaluate_feedback(run.proposal, feedback).status == "accepted"
    before = e.policy
    assert e.evaluate_feedback(run.proposal, feedback).status == "duplicate"
    other = OutcomeFeedback.model_validate(feedback.model_dump() | {"id": "other-outcome"})
    assert e.evaluate_feedback(run.proposal, other).status == "duplicate"
    assert e.policy == before


async def test_prediction_error_uses_frozen_pre_event_observed_mean():
    e = engine()
    expected_actions = ("monitor", "retrieve", "retrieve")
    for index, reward in enumerate((-0.5, 0.85, 0.5)):
        _, run, _ = await issued(e, episode=f"episode-{index}")
        assert run.proposal.action.action == expected_actions[index]
        feedback = observed_feedback(run.proposal, reward=reward, outcome_id=f"outcome-{index}")
        e.feedback.records[feedback.id] = feedback
        result = e.evaluate_feedback(run.proposal, feedback)
        assert result.status == "accepted"
        if index < 2:
            assert result.transition.prediction_error is None
        else:
            assert run.proposal.estimated_value == 0.85 and run.proposal.samples == 1
            assert result.transition.prediction_error == pytest.approx(-0.35)
            assert result.transition.before_samples == 1 and result.transition.after_samples == 2


@pytest.mark.parametrize(
    "update",
    [
        {"episode_id": "wrong"},
        {"goal_id": "wrong"},
        {"proposal_id": "wrong"},
        {"observed_action": "retrieve"},
        {"executed": False},
        {"completion": "interrupted"},
        {"completion": "failed"},
        {"origin": "live"},
        {"split": "test"},
        {"split": "development"},
        {"measurements": []},
    ],
)
async def test_invalid_feedback_no_update(update):
    e, run, _ = await issued()
    feedback = observed_feedback(run.proposal).model_dump() | update
    before = e.policy
    assert e.evaluate_feedback(run.proposal, feedback).status == "rejected"
    assert e.policy == before


async def test_missing_independent_verification_rejected():
    e, run, _ = await issued()
    before = e.policy
    assert e.evaluate_feedback(run.proposal, observed_feedback(run.proposal)).status == "rejected"
    assert e.policy == before


async def test_verifier_failure_is_atomic_and_sanitized():
    class Broken:
        def verify(self, feedback):
            raise RuntimeError("secret must not escape")

    e, run, _ = await issued(engine(verifier=Broken()))
    before = e.policy
    result = e.evaluate_feedback(run.proposal, observed_feedback(run.proposal))
    assert result.status == "failed" and e.policy == before
    assert "secret" not in result.model_dump_json()


@pytest.mark.parametrize("split", ["test", "development"])
async def test_eval_observation_never_trains(split):
    e, run, _ = await issued(split=split)
    feedback = observed_feedback(run.proposal)
    e.feedback.records[feedback.id] = feedback
    assert e.evaluate_feedback(run.proposal, feedback).status == "rejected"
    assert e.policy.revision == 0


async def test_timeout_cancel_failure_no_pending_tasks():
    observation, context = inputs()

    class Slow(FixtureInvocation):
        stopped = False

        async def invoke(self, request):
            try:
                await asyncio.Event().wait()
            finally:
                self.stopped = True

    slow = Slow(observation, context)
    e = engine(timeout_seconds=0.01)
    result = await e.analyze(observation, context, inference=slow)
    assert result.status == "failed" and result.proposal is None and slow.stopped
    slow = Slow(observation, context)
    task = asyncio.create_task(engine().analyze(observation, context, inference=slow))
    await asyncio.sleep(0.01)
    task.cancel()
    result = await task
    assert result.status == "cancelled" and result.proposal is None and slow.stopped
    assert not [t for t in asyncio.all_tasks() if t is not asyncio.current_task()]

    class Broken(FixtureInvocation):
        async def invoke(self, request):
            raise RuntimeError("private adapter error")

    result = await engine().analyze(observation, context, inference=Broken(observation, context))
    assert result.status == "failed" and "private" not in result.model_dump_json()
