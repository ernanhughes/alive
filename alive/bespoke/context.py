"""Resolve captured and approved evidence; never infer user intent from source prose."""

from alive.bespoke.contracts import ObservedContext
from alive.capabilities.bindings import digest, registry_for
from alive.capabilities.repository import reader_for
from alive.workflows.context import authorized, require


async def resolve_context(session, kernel, request):
    grant, _, _, _, context, _ = await authorized(session, kernel, request.approval_ref)
    require(
        grant.goal_id == request.goal_ref
        and grant.investigation_id == request.investigation_ref
        and grant.context_event_id == request.source_ref
        and grant.context_sha256 == request.source_sha256,
        "context_scope_or_integrity",
    )
    surface = (
        "controlled_evidence"
        if grant.context_provenance.custody == "controlled_fixture"
        else "browser_document"
    )
    repositories = []
    for cap_grant in grant.capabilities.values():
        resource = cap_grant.get("resources", {})
        if "repository_ref" in resource:
            # Existing registry checks exact capture digest and path subset without reading files.
            registry_for(kernel).check_grant(
                {
                    "identity": cap_grant["identity"],
                    "stage_limits": {
                        "timeout_seconds": cap_grant["limits"]["timeout_seconds"],
                        "max_output_tokens": cap_grant["limits"]["max_output_tokens"],
                    },
                },
                cap_grant,
            )
            reader_for(registry_for(kernel), cap_grant, grant.inputs)
            repositories.append(resource)
            surface = "repository"
    observed = {
        "context_schema": "bespoke-context/v1",
        "goal_ref": grant.goal_id,
        "investigation_ref": grant.investigation_id,
        "source_ref": grant.context_event_id,
        "source_sha256": grant.context_sha256,
        "surface": surface,
        "provenance": grant.context_provenance.model_dump(mode="json"),
        "claims_count": len(context["claims"]),
        "sources_count": len(context["sources"]),
        "repositories": repositories,
        "inputs_sha256": digest(grant.inputs),
        "intent_origin": "explicit_user" if request.objective.kind else "unspecified",
        "inferred_intent": None,
    }
    return grant, ObservedContext.model_validate(observed).model_dump(mode="json")
