"""Dispatch-time authority checks for a research task.

This does not create a new approval system. It re-validates the owner's existing standing consent,
source approval, model destination and role contract immediately before every model call.
"""

from __future__ import annotations

from dataclasses import dataclass

from alive.model_contracts import ApprovedModelDestination
from alive.sources import custody
from alive.workflows.context import require


@dataclass(frozen=True)
class ResearchClaim:
    consent_ref: str
    goal_ref: str
    principal: str
    paths: tuple[str, ...]


async def validate_dispatch(
    session,
    kernel,
    claim: ResearchClaim,
    *,
    role: str,
    spec,
    model: str,
    output_limit: int,
    context: dict,
) -> ApprovedModelDestination:
    """Return the exact approved destination or refuse before provider dispatch."""
    from alive.admission import live

    current = await live.consent(session, kernel, claim.consent_ref)
    terms = current["terms"]
    research = terms.get("research")
    require(bool(research), "research_session_required")
    require(
        terms["principal"] == claim.principal == current["terms"]["principal"],
        "research_principal_changed",
    )
    require(terms["goal_ref"] == claim.goal_ref, "research_goal_changed")
    require(tuple(terms["paths"]) == claim.paths, "research_paths_changed")
    require(research["role"] == role, "research_role_changed")
    require(research["role_contract_sha256"] == spec.contract, "research_contract_changed")
    require(research["model"] == model, "research_model_changed")
    require(
        output_limit <= research["max_output_tokens"] <= terms["max_tokens"],
        "research_output_ceiling",
    )
    require(
        research["max_model_calls"] <= terms["max_calls"],
        "research_call_ceiling",
    )
    destination = research["destination"]
    require(
        destination["endpoint"] and destination["model"] == model,
        "research_destination_changed",
    )

    source = await custody.resolve(kernel, terms["source"]["resources"], "context.reason")
    await custody.resolve(kernel, terms["source"]["resources"], "context.validate")
    require(
        sorted(item["path"] for item in source.content["files"]) == sorted(claim.paths),
        "research_source_scope_changed",
    )
    require(
        source.content_sha256 == terms["source"]["resources"]["content_sha256"],
        "research_source_digest_changed",
    )
    return ApprovedModelDestination(
        admission_id=claim.consent_ref,
        review_sha256=current["sha256"],
        endpoint=destination["endpoint"],
    )


async def source_for(claim: ResearchClaim, kernel) -> custody.ApprovedSource:
    """Resolve the approved source for deterministic tool execution."""
    from alive.admission import live

    async with kernel.db.sessions() as session:
        current = await live.consent(session, kernel, claim.consent_ref)
    return await custody.resolve(kernel, current["terms"]["source"]["resources"], "context.reason")


__all__ = ["ResearchClaim", "source_for", "validate_dispatch"]
