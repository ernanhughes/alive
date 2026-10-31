"""Feasibility before ranking. No capability invocation, workflow start or model client."""

from time import monotonic

from sqlalchemy import select

from alive.bespoke.contracts import Candidate, Selection
from alive.bespoke.recipes import MAX_RECIPES, recipe_hash
from alive.capabilities.bindings import binding_record, digest, registry_for
from alive.capabilities.trusted import permission_bits
from alive.workflows.context import require
from alive.workflows.models import WorkflowDefinition
from alive.workflows.spec import canonical_dict, definition_sha256, graph_of, parse_definition

POLICY = {
    "selector": "bespoke-selector/v1",
    "scoring": "bespoke-suitability/v1",
    "factors": {
        "explicit_goal_alignment": 40,
        "captured_context_match": 25,
        "required_evidence_present": 15,
        "validation_contract": 10,
        "resource_headroom": 5,
        "operational_simplicity": 5,
    },
    "max_recipes": MAX_RECIPES,
    "max_context_bytes": 65536,
    "max_record_bytes": 262144,
    "deadline_seconds": 5,
}


async def evaluate(session, kernel, recipe, request, grant, context):
    registry = registry_for(kernel)
    reasons = []
    if recipe.status != "active":
        reasons.append("recipe_unavailable")
    if context["surface"] not in recipe.context_types:
        reasons.append("unsupported_context")
    if request.objective.kind is None:
        reasons.append("intent_unclear")
    elif request.objective.kind not in recipe.intents:
        reasons.append("objective_incompatible")
    if recipe.required_evidence == "claims_and_sources" and (
        not context["claims_count"] or not context["sources_count"]
    ):
        reasons.append("context_insufficient")
    limits = recipe.limits
    ceiling = request.constraints
    if (
        limits.max_model_calls > ceiling.max_model_calls
        or limits.max_wall_seconds > ceiling.max_wall_seconds
        or limits.max_output_tokens > ceiling.max_output_tokens
        or limits.outbound_allowed
        and not ceiling.outbound_allowed
    ):
        reasons.append("resource_limit_exceeded")
    if not set(limits.permissions) <= set(ceiling.permissions):
        reasons.append("permission_not_grantable")
    if limits.max_model_calls:
        if (
            kernel.settings.alive_model_transport != "pi"
            or not hasattr(kernel, "model_provider_ready")
            or not await kernel.model_provider_ready()
        ):
            reasons.append("deployment_policy_conflict")
    for pin in recipe.capabilities:
        try:
            cap = registry.get(pin.id, pin.version)
            if not cap.executable:
                reasons.append("missing_capability")
            elif cap.manifest_sha256 != pin.manifest_sha256:
                reasons.append("capability_identity_changed")
        except KeyError:
            reasons.append("missing_capability")
    row = await session.scalar(
        select(WorkflowDefinition).where(
            WorkflowDefinition.name == recipe.workflow.name,
            WorkflowDefinition.version == recipe.workflow.version,
        )
    )
    detail = {}
    if row is None or row.status != "active":
        reasons.append("workflow_unavailable")
    else:
        try:
            spec = parse_definition(row.definition_json, operations=registry.operations)
            if not (
                definition_sha256(spec)
                == row.definition_sha256
                == recipe.workflow.definition_sha256
            ):
                reasons.append("workflow_identity_changed")
            binding = await binding_record(session, kernel, row)
            # Rebinding checks input/output contracts; retained fingerprints remain authoritative.
            current = registry.bind(spec)
            if current != binding.snapshot["stages"]:
                reasons.append("binding_changed")
            pins = {p.stage_id: p for p in recipe.capabilities}
            if set(pins) != set(binding.snapshot["stages"]):
                reasons.append("capability_identity_changed")
            permissions, identities, policies = set(), [], []
            calls, tokens = 0, 0
            for stage_id, bound in sorted(binding.snapshot["stages"].items()):
                identity = bound["identity"]
                cap = registry.recheck(identity)
                pin = pins.get(stage_id)
                if pin is None or any(
                    getattr(pin, k) != identity[k] for k in ("id", "version", "manifest_sha256")
                ):
                    reasons.append("capability_identity_changed")
                effective = registry.limits_for(cap)
                if (
                    bound["stage_limits"]["timeout_seconds"] > effective["timeout_seconds"]
                    or bound["stage_limits"]["max_output_tokens"] > effective["max_output_tokens"]
                ):
                    reasons.append("deployment_policy_conflict")
                calls += effective["max_model_calls"]
                tokens += bound["stage_limits"]["max_output_tokens"]
                permissions |= permission_bits(cap.manifest["permissions"])
                identities.append(identity)
                policies.append(registry.policy_sha256(cap))
            if not permissions <= set(limits.permissions):
                reasons.append("permission_not_grantable")
            if (
                spec.limits.max_model_calls > limits.max_model_calls
                or calls > limits.max_model_calls
                or tokens > limits.max_output_tokens
                or spec.limits.max_total_output_tokens > limits.max_output_tokens
                or spec.limits.max_wall_seconds > limits.max_wall_seconds
                or "model.infer" in permissions
                and not limits.outbound_allowed
            ):
                reasons.append("resource_limit_exceeded")
            types = {
                "string": str,
                "array": list,
                "object": dict,
                "integer": int,
                "boolean": bool,
                "number": (int, float),
            }
            for key, field in spec.inputs.items():
                if field.required and key not in grant.inputs:
                    reasons.append("missing_inputs")
                elif key in grant.inputs and type(grant.inputs[key]) not in (
                    types[field.type]
                    if isinstance(types[field.type], tuple)
                    else (types[field.type],)
                ):
                    reasons.append("missing_inputs")
            detail = {
                "definition_id": row.id,
                "binding_sha256": binding.snapshot_sha256,
                "capability_identities": identities,
                "capability_policies": policies,
                # Canonical execution contract, excluding recipe presentation and suitability.
                "procedure_sha256": digest(
                    {
                        "workflow": canonical_dict(spec),
                        "binding": binding.snapshot_sha256,
                        "inputs": context["inputs_sha256"],
                    }
                ),
                "graph": {
                    "name": spec.name,
                    "version": spec.version,
                    "definition_sha256": row.definition_sha256,
                    **graph_of(canonical_dict(spec), operations=registry.operations),
                },
            }
        except (ValueError, KeyError, TypeError):
            reasons.append("binding_changed")
    reasons = sorted(set(reasons))
    factors = {}
    if not reasons:
        factors = dict(POLICY["factors"])
        factors["validation_contract"] = 0 if recipe.validation == "none" else 10
        factors["resource_headroom"] = 5 if limits.max_model_calls == 0 else 0
        factors["operational_simplicity"] = max(0, 6 - len(recipe.capabilities))
    return Candidate(
        recipe=recipe,
        recipe_sha256=recipe_hash(recipe),
        eligible=not reasons,
        reasons=reasons,
        factors=factors,
        suitability=sum(factors.values()),
        **detail,
    )


async def select_recipe(session, kernel, catalogue, request, grant, context):
    start = monotonic()
    require(len(catalogue) <= MAX_RECIPES, "catalogue_limit")
    require(len(registry_for(kernel).list()) <= 128, "capability_catalogue_limit")
    candidates = []
    for recipe in catalogue:
        require(monotonic() - start < POLICY["deadline_seconds"], "selection_deadline")
        candidates.append(await evaluate(session, kernel, recipe, request, grant, context))
    candidates.sort(
        key=lambda c: (
            -int(c.eligible),
            -c.suitability,
            c.recipe.id,
            c.recipe.version,
            c.recipe_sha256,
        )
    )
    eligible = [c for c in candidates if c.eligible]
    uncertainty = [
        "Suitability is a rule-based score, not measured outcome quality.",
        "Source identity and reference checks do not establish semantic truth.",
        "Production owner authorization is unavailable; selection cannot execute.",
    ]
    if request.objective.kind is None:
        uncertainty.append("Intent is unspecified. Choose an explicit objective and select again.")
    return Selection(
        policy_sha256=digest(POLICY),
        context_sha256=digest(context),
        context=context,
        catalogue_sha256=digest(
            {
                "recipes": [
                    c.recipe_sha256 for c in sorted(candidates, key=lambda c: c.recipe_sha256)
                ],
                "capabilities": [
                    {
                        "identity": cap.identity,
                        "status": cap.status,
                        "policy_sha256": registry_for(kernel).policy_sha256(cap),
                    }
                    for cap in registry_for(kernel).list()
                ],
                "bindings": [
                    {
                        "definition_id": c.definition_id,
                        "binding_sha256": c.binding_sha256,
                        "reasons": c.reasons,
                    }
                    for c in candidates
                ],
            }
        ),
        objective=request.objective,
        constraints=request.constraints,
        candidates=candidates,
        selected_recipe_sha256=eligible[0].recipe_sha256 if eligible else None,
        state="recommended" if eligible else "abstained",
        uncertainty=uncertainty,
        distinct_procedures=len({c.procedure_sha256 for c in eligible}),
    )
