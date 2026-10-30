"""Pure validation/update preparation. Engine commits only a fully prepared transition."""

from .contracts import ExperienceTransition, digest


def prepare(proposal, feedback, observation, context, policy, verifier):
    if proposal.action is None:
        raise ValueError("Abstention has no executed action")
    if (
        feedback.proposal_id != proposal.id
        or feedback.episode_id != proposal.episode_id
        or feedback.goal_id != proposal.goal_id
        or feedback.observed_action != proposal.action.action
        or not feedback.executed
        or feedback.completion != "completed"
        or feedback.event_at < observation.observed_at
    ):
        raise ValueError("Incomplete or incompatible observed outcome")
    if feedback.origin != context.origin or feedback.origin != policy.origin:
        raise ValueError("Origin mismatch")
    if feedback.split != "train" or context.split != "train":
        raise ValueError("Training split required")
    if policy.hash != proposal.policy_hash:
        raise ValueError("Stale policy; reanalyze before updating")
    known = {e.id for e in context.evidence}
    measurement_ids = [e.id for e in feedback.measurements]
    if len(set(measurement_ids)) != len(measurement_ids):
        raise ValueError("Conflicting measurement identity")
    sources = {}
    for evidence in feedback.measurements:
        if (
            evidence.id in known
            or evidence.trust != "admitted"
            or evidence.qualification != "current"
            or evidence.origin != context.origin
            or evidence.observed_at < observation.observed_at
            or evidence.observed_at > feedback.event_at
        ):
            raise ValueError("Independent current measurement required")
        previous = sources.setdefault(evidence.source_id, evidence.fingerprint)
        if previous != evidence.fingerprint:
            raise ValueError("Conflicting measurement source")
    if verifier.verify(feedback) is not True:
        raise ValueError("Outcome provenance not verified")
    updated = policy.updated(feedback.observed_action, feedback.reward)
    action = feedback.observed_action
    transition = ExperienceTransition(
        proposal=proposal,
        before_state=context.state,
        proposed_action=proposal.action.action,
        executed_action=action,
        outcome=feedback,
        before_policy_hash=policy.hash,
        after_policy_hash=updated.hash,
        before_version=policy.revision,
        after_version=updated.revision,
        before_samples=getattr(policy, action).n,
        after_samples=getattr(updated, action).n,
        origin=feedback.origin,
        split=feedback.split,
        usage=proposal.invocation,
        # A zero prior is not a prediction supported by observations.
        prediction_error=(feedback.reward - proposal.estimated_value)
        if proposal.samples and proposal.estimated_value is not None
        else None,
    )
    if proposal.state_hash != digest(context.state):
        raise ValueError("State identity changed")
    return updated, transition
