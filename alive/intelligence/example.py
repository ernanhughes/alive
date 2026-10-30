"""Controlled integration example, not a live benchmark. No physical actions occur.

Run: python -B -m alive.intelligence.example
"""

import asyncio
import json
from datetime import UTC, datetime, timedelta

from .contracts import (
    CandidateAction,
    Context,
    EmpiricalState,
    Evidence,
    History,
    InvocationSummary,
    Observation,
    OutcomeFeedback,
    RewardComponent,
    digest,
)
from .engine import IntelligenceEngine
from .policies.empirical import EmpiricalPolicy
from .ports import InvocationBinding, InvocationResponse
from .reasoning import payload

NOW = datetime(2026, 10, 30, tzinfo=UTC)


def inputs(episode="episode-1", *, origin="fixture", split="train", candidates=None, at=NOW):
    evidence = Evidence(
        id="claim-" + episode,
        source_id="aster-claim",
        fingerprint=digest("claim-32"),
        observed_at=at,
        origin=origin,
        qualification="current",
        trust="admitted",
        excerpt="Aster endurance_hours claim 32; source replaced; current value unresolved.",
    )
    observation = Observation(
        goal_id="aster-inquiry",
        event_id="event-" + episode,
        episode_id=episode,
        observed_at=at,
        evidence=(evidence,),
        source_fingerprint=evidence.fingerprint,
        safe_text=evidence.excerpt,
        origin=origin,
        provenance="controlled-instrument-fixture",
        trust="admitted",
    )
    if candidates is None:
        candidates = tuple(
            CandidateAction(
                id=a,
                action=a,
                expected_evidence_benefit=0.5,
                expected_cost=0 if a == "monitor" else 0.15,
                expected_risk=0,
            )
            for a in ("monitor", "retrieve")
        )
    context = Context(
        goal_id=observation.goal_id,
        state=EmpiricalState(claim="32"),
        evidence=(evidence,),
        candidates=candidates,
        reported_resources=1,
        origin=origin,
        split=split,
    )
    return observation, context


class FixtureEvidence:
    async def admit(self, observation, context):
        # A real implementation must consult authorized source records and outbound consent.
        return context.evidence


class FixtureFeedback:
    def __init__(self):
        self.records = {}

    def verify(self, feedback):
        # Exact independently supplied record, not a provenance string from a model.
        return self.records.get(feedback.id) == feedback


class FixtureInvocation:
    """One-use deterministic role fixture; zero model calls, tokens and spend."""

    def __init__(self, observation, context, *, output=None):
        self.binding = InvocationBinding(
            summary=InvocationSummary(
                invocation_id="fixture-" + observation.episode_id,
                reservation_id="fixture-reservation-" + observation.episode_id,
                operation="cognition.role",
                provider="fixture",
                model="controlled-role-fixture-v1",
                provenance="fixture",
                prompt_tokens=0,
                completion_tokens=0,
            ),
            payload_hash=digest(payload(observation, context)),
            approved_context=context.scope,
        )
        self.requests = []
        self.output = (
            output
            if output is not None
            else {
                "summary": "Fixture interpretation: current measurement needs verification.",
                "claims": [
                    {
                        "subject": "Aster",
                        "predicate": "endurance_hours",
                        "value": "32",
                        "evidence_refs": [context.evidence[0].id],
                    }
                ],
                "actions": [],
                "criticisms": [],
                "uncertainties": ["Observed claim is not independent verification."],
                "recommendation": "investigate",
                "confidence": 0.5,
            }
        )

    async def invoke(self, request):
        if self.requests or digest(request.data) != self.binding.payload_hash:
            raise PermissionError("Fixture capability consumed or payload mismatch")
        self.requests.append(request)
        return InvocationResponse(text=json.dumps(self.output), summary=self.binding.summary)


def observed_feedback(proposal, *, reward=-0.5, outcome_id="outcome-1"):
    measurement = Evidence(
        id="measurement-" + outcome_id,
        source_id="independent-fixture-instrument",
        fingerprint=digest("instrument-20"),
        observed_at=NOW + timedelta(seconds=1),
        origin="fixture",
        qualification="current",
        trust="admitted",
        excerpt="Independent fixture feedback: current value 20; initial claim unresolved.",
    )
    return OutcomeFeedback(
        id=outcome_id,
        proposal_id=proposal.id,
        episode_id=proposal.episode_id,
        goal_id=proposal.goal_id,
        observed_action=proposal.action.action,
        executed=True,
        result="Fixture observer reports unresolved claim; no physical action executed by engine.",
        measurements=(measurement,),
        rewards=(RewardComponent(name="goal-utility", value=reward, source_ref=measurement.id),),
        completion="completed",
        event_at=measurement.observed_at,
        origin="fixture",
        split="train",
    )


async def run_example():
    verifier = FixtureFeedback()
    engine = IntelligenceEngine(
        evidence=FixtureEvidence(), feedback=verifier, policy=EmpiricalPolicy(origin="fixture")
    )
    first_observation, context = inputs()
    first = await engine.analyze(
        first_observation, context, inference=FixtureInvocation(first_observation, context)
    )
    feedback = observed_feedback(first.proposal)
    verifier.records[feedback.id] = feedback  # supplied independently, never model-generated
    learned = engine.evaluate_feedback(first.proposal, feedback)
    later, later_context = inputs("episode-2", at=NOW + timedelta(seconds=2))
    historical_measurement = Evidence.model_validate(
        feedback.measurements[0].model_dump() | {"qualification": "historical"}
    )
    history = History(
        episode_id=first.proposal.episode_id,
        observed_at=feedback.event_at,
        origin="fixture",
        split="train",
        qualification="observed",
        evidence_refs=(historical_measurement.id,),
        summary="Earlier monitor unresolved; observed fixture reward -0.5; historical only.",
    )
    later_context = Context.model_validate(
        later_context.model_dump()
        | {
            "evidence": later_context.evidence + (historical_measurement,),
            "history": (history,),
        }
    )
    revisit = await engine.revisit(
        later,
        later_context,
        earlier_proposal=first.proposal,
        inference=FixtureInvocation(later, later_context),
    )
    return {
        "mode": "controlled integration example; no live inference or physical execution",
        "episode_1": first.model_dump(mode="json"),
        "feedback": learned.model_dump(mode="json"),
        "episode_2": revisit.model_dump(mode="json"),
    }


if __name__ == "__main__":
    print(json.dumps(asyncio.run(run_example()), indent=2))
