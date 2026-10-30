"""Deterministic masked empirical proposal construction, with no execution port."""

from .contracts import DecisionProposal, digest


def propose(observation, context, policy, reasoning):
    candidates = tuple(
        c for c in context.candidates if c.expected_cost <= context.reported_resources
    )
    chosen, ranking = policy.rank(candidates)
    if reasoning.recommendation == "abstain":
        chosen = None
    prediction = ranking["predictions"].get(chosen.action) if chosen else None
    identity = digest(
        {"observation": digest(observation), "context": digest(context), "policy": policy.hash}
    )
    return DecisionProposal(
        id="proposal-" + identity[:48],
        episode_id=observation.episode_id,
        goal_id=observation.goal_id,
        action=chosen,
        candidate_ids=tuple(c.id for c in context.candidates),
        policy_name=context.policy_id,
        policy_version=policy.revision,
        policy_hash=policy.hash,
        state_hash=digest(context.state),
        reason=ranking["reason"]
        if chosen
        else "No permitted affordable action or reasoner abstained.",
        estimated_value=prediction["mean"] if prediction else None,
        samples=prediction["n"] if prediction else 0,
        invocation=reasoning.invocation,
    )
