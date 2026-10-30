"""Bounded orchestration with caller-owned evidence, invocation and feedback authority."""

import asyncio

from .contracts import (
    Context,
    DecisionProposal,
    FeedbackResult,
    Observation,
    OutcomeFeedback,
    RevisitResult,
    RunResult,
    TraceEvent,
    digest,
)
from .decision import propose
from .experience import prepare
from .policies.empirical import EmpiricalPolicy, NotSupported
from .ports import AuthorizedInvocation, EvidencePort, FeedbackVerifier
from .reasoning import ModelReasoner, Unavailable


def reconcile(observation, context, admitted):
    if (
        observation.goal_id != context.goal_id
        or observation.origin != context.origin
        or observation.trust != "admitted"
    ):
        raise ValueError("Observation scope or trust mismatch")
    if not isinstance(admitted, tuple) or admitted != context.evidence:
        raise ValueError("Context must exactly match authorized evidence")
    ids, sources = {}, {}
    for evidence in context.evidence:
        if evidence.id in ids:
            raise ValueError("Duplicate evidence identity")
        ids[evidence.id] = evidence
        previous = sources.setdefault(evidence.source_id, evidence.fingerprint)
        if previous != evidence.fingerprint:
            raise ValueError("Conflicting source identity")
        if (
            evidence.origin != context.origin
            or evidence.trust != "admitted"
            or evidence.qualification == "unqualified"
            or evidence.observed_at > observation.observed_at
        ):
            raise ValueError("Unsupported evidence provenance or timestamp")
    for evidence in observation.evidence:
        if ids.get(evidence.id) != evidence:
            raise ValueError("Observation evidence not admitted")
    if not any(
        e.fingerprint == observation.source_fingerprint and e.qualification == "current"
        for e in observation.evidence
    ):
        raise ValueError("Observation fingerprint lacks current source")
    for history in context.history:
        if (
            history.origin != context.origin
            or history.split != context.split
            or history.observed_at > observation.observed_at
            or not set(history.evidence_refs) <= ids.keys()
        ):
            raise ValueError("History scope mismatch")


class IntelligenceEngine:
    """Session-local proposals and exactly-once updates, bounded to 256 episodes.

    A new engine is a new idempotency domain. This is not a durable transaction service.
    Injected ports must be trusted, bounded and cancellation-cooperative.
    """

    def __init__(
        self,
        *,
        evidence: EvidencePort,
        feedback: FeedbackVerifier,
        policy: EmpiricalPolicy,
        timeout_seconds: float = 10,
    ):
        if not 0 < timeout_seconds <= 60:
            raise ValueError("Timeout must be in (0, 60]")
        self.evidence = evidence
        self.feedback = feedback
        self._policy = EmpiricalPolicy.model_validate(policy)
        self.timeout_seconds = timeout_seconds
        self._issued = {}
        self._consumed = set()
        self._outcomes = {}

    @property
    def policy(self) -> EmpiricalPolicy:
        return self._policy

    async def analyze(
        self,
        observation: Observation,
        context: Context,
        *,
        inference: AuthorizedInvocation | None = None,
    ) -> RunResult:
        trace = []

        def event(stage, summary, reference=None):
            trace.append(
                TraceEvent(sequence=len(trace), stage=stage, summary=summary, reference=reference)
            )

        try:
            observation = Observation.model_validate(observation)
            context = Context.model_validate(context)
            event("input", "Observation received; no execution authority.", observation.event_id)
            if len(self._issued) >= 256:
                raise ValueError("Session episode capacity reached")
            if any(o.episode_id == observation.episode_id for _, o, _, _ in self._issued.values()):
                raise ValueError("Episode already issued; supply a new episode identity")
            policy = self._policy  # freeze across asynchronous invocation
            if policy.origin != context.origin:
                raise ValueError("Policy origin mismatch")
            # Check compatibility even when inference is unavailable.
            policy.rank(context.candidates)
            async with asyncio.timeout(self.timeout_seconds):
                admitted = await self.evidence.admit(observation, context)
                reconcile(observation, context, admitted)
                event(
                    "evidence", "Exact authorized evidence admitted; citations are identity checks."
                )
                reasoning = await ModelReasoner().reason(observation, context, inference)
            event(
                "invocation",
                "Structured response validated: " + reasoning.invocation.provenance,
                reasoning.invocation.invocation_id,
            )
            if self._policy != policy:
                raise ValueError("Policy changed during reasoning; retry with a new reservation")
            proposal = propose(observation, context, policy, reasoning)
            if any(o.episode_id == observation.episode_id for _, o, _, _ in self._issued.values()):
                raise ValueError("Concurrent episode already issued")
            if len(self._issued) >= 256:
                raise ValueError("Session capacity reached during reasoning")
            self._issued[proposal.id] = (proposal, observation, context, policy)
            event(
                "decision",
                "Unexecuted policy proposal; external Governor authorization required.",
                proposal.id,
            )
            return RunResult(
                status="proposed" if proposal.action else "abstained",
                explanation=proposal.reason,
                proposal=proposal,
                reasoning=reasoning,
                trace=tuple(trace),
            )
        except Unavailable:
            event("error", "Authorized reasoning unavailable; no inference dispatched.")
            return RunResult(
                status="abstained",
                error_code="reasoning_unavailable",
                explanation=trace[-1].summary,
                trace=tuple(trace),
            )
        except asyncio.CancelledError:
            event("error", "Analysis cancelled; no proposal issued.")
            return RunResult(
                status="cancelled",
                error_code="cancelled",
                explanation=trace[-1].summary,
                trace=tuple(trace),
            )
        except Exception as error:
            # Adapter exceptions may contain secrets. Only retain a bounded category, not text.
            if isinstance(error, TimeoutError):
                category = "timeout"
            elif isinstance(error, NotSupported):
                category = "not_supported"
            else:
                category = "invalid_input_or_adapter"
            event("error", "Analysis failed: " + category)
            return RunResult(
                status="failed",
                error_code=category,
                explanation=trace[-1].summary,
                trace=tuple(trace),
            )

    def evaluate_feedback(
        self,
        proposal: DecisionProposal,
        feedback: OutcomeFeedback,
    ) -> FeedbackResult:
        try:
            feedback = OutcomeFeedback.model_validate(feedback)
            issued = self._issued.get(feedback.proposal_id)
            if issued is None or proposal != issued[0]:
                raise ValueError("Previously issued proposal required")
            if feedback.id in self._outcomes or proposal.id in self._consumed:
                if self._outcomes.get(feedback.id) != digest(feedback):
                    return FeedbackResult(
                        status="rejected", explanation="Conflicting feedback replay."
                    )
                return FeedbackResult(status="duplicate", explanation="Outcome already consumed.")
            _, observation, context, _ = issued
            updated, transition = prepare(
                proposal, feedback, observation, context, self._policy, self.feedback
            )
            result = FeedbackResult(
                status="accepted",
                explanation="Observed training outcome applied once in memory.",
                transition=transition,
                trace=(
                    TraceEvent(
                        sequence=0,
                        stage="feedback",
                        summary="Independent outcome accepted.",
                        reference=feedback.id,
                    ),
                ),
            )
            # No await or external write: prepared state and deduplication commit together locally.
            self._policy = updated
            self._outcomes[feedback.id] = digest(feedback)
            self._consumed.add(proposal.id)
            return result
        except ValueError:
            return FeedbackResult(status="rejected", explanation="Outcome validation rejected.")
        except Exception:
            return FeedbackResult(
                status="failed", explanation="Feedback adapter failed; no update."
            )

    async def revisit(
        self,
        observation: Observation,
        context: Context,
        *,
        earlier_proposal: DecisionProposal,
        inference: AuthorizedInvocation | None = None,
    ) -> RevisitResult:
        issued = self._issued.get(earlier_proposal.id)
        if issued is None or issued[0] != earlier_proposal:
            raise ValueError("Previously issued proposal required")
        context = Context.model_validate(context)
        if context.goal_id != issued[2].goal_id or context.origin != issued[2].origin:
            raise ValueError("Related goal and origin required")
        old_action, _ = issued[3].rank(
            tuple(c for c in context.candidates if c.expected_cost <= context.reported_resources)
        )
        current = await self.analyze(observation, context, inference=inference)
        return RevisitResult(
            current=current,
            frozen_action=old_action.action if old_action else None,
            frozen_policy_hash=issued[3].hash,
        )

    @staticmethod
    def shadow_compare(adapter, state):
        """Separate read-only query: shadow predictions cannot enter analyze or feedback."""
        return adapter.compare(state)
