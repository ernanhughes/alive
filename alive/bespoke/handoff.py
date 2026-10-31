"""Trusted host-only handoff. No HTTP route and no grant creation or execution here."""

from sqlalchemy import select

from alive.bespoke.context import resolve_context
from alive.bespoke.contracts import RecommendRequest
from alive.bespoke.models import Recommendation
from alive.bespoke.recipes import recipe_hash
from alive.bespoke.selector import POLICY, evaluate
from alive.bespoke.store import view
from alive.capabilities.bindings import digest
from alive.models import Event
from alive.workflows.context import require
from alive.workflows.models import WorkflowRun
from alive.workflows.store import run_view


async def trusted_handoff(kernel, catalogue, recommendation_id, authorization_id):
    async with kernel.lock, kernel.db.sessions.begin() as session:
        row = await session.get(Recommendation, recommendation_id)
        require(
            row is not None and row.instance_id == kernel.instance_id, "recommendation_unavailable"
        )
        selected = view(row).selection
        require(selected.state == "recommended", "recommendation_abstained")
        require(selected.policy_sha256 == digest(POLICY), "selection_policy_changed")
        retained = next(
            c for c in selected.candidates if c.recipe_sha256 == selected.selected_recipe_sha256
        )
        current_recipe = next(
            (r for r in catalogue if recipe_hash(r) == retained.recipe_sha256), None
        )
        require(current_recipe is not None, "recipe_identity_changed")
        context = selected.context.model_dump(mode="json")
        request = RecommendRequest(
            approval_ref=authorization_id,
            goal_ref=row.goal_id,
            investigation_ref=row.investigation_id,
            source_ref=row.source_ref,
            source_sha256=context["source_sha256"],
            objective=selected.objective,
            constraints=selected.constraints,
            idempotency_key=row.idempotency_key,
        )
        grant, observed = await resolve_context(session, kernel, request)
        require(
            grant.principal == row.principal and digest(observed) == selected.context_sha256,
            "recommendation_context_changed",
        )
        current = await evaluate(session, kernel, current_recipe, request, grant, observed)
        require(current.eligible and current == retained, "recommendation_no_longer_eligible")
        require(
            grant.definition_id == retained.definition_id
            and grant.definition_sha256 == retained.recipe.workflow.definition_sha256
            and grant.capability_binding_sha256 == retained.binding_sha256,
            "recommendation_authority_mismatch",
        )
        limits = selected.constraints
        require(
            grant.max_model_calls <= limits.max_model_calls
            and grant.max_output_tokens <= limits.max_output_tokens
            and grant.wall_seconds <= limits.max_wall_seconds
            and (not grant.outbound_approved or limits.outbound_allowed),
            "recommendation_budget_mismatch",
        )
        kernel.add_event(
            session,
            "bespoke.authorization.handoff",
            {
                "recommendation_id": row.id,
                "selection_sha256": row.selection_sha256,
                "authorization_id": authorization_id,
            },
            source="bespoke",
            correlation=row.investigation_id,
        )
        return authorization_id  # caller still must use the existing WorkflowRunner


async def linked_runs(kernel, recommendation_id):
    async with kernel.db.sessions() as session:
        row = await session.get(Recommendation, recommendation_id)
        require(
            row is not None and row.instance_id == kernel.instance_id, "recommendation_unavailable"
        )
        selected = view(row).selection
        if selected.state != "recommended":
            return []
        candidate = next(
            c for c in selected.candidates if c.recipe_sha256 == selected.selected_recipe_sha256
        )
        results = await session.scalars(
            select(WorkflowRun)
            .join(
                Event,
                Event.payload["authorization_id"].as_string() == WorkflowRun.authorization_ref,
            )
            .where(
                Event.instance_id == kernel.instance_id,
                Event.source == "bespoke",
                Event.event_type == "bespoke.authorization.handoff",
                Event.payload["recommendation_id"].as_string() == row.id,
                Event.payload["selection_sha256"].as_string() == row.selection_sha256,
                WorkflowRun.instance_id == kernel.instance_id,
                WorkflowRun.goal_id == row.goal_id,
                WorkflowRun.investigation_id == row.investigation_id,
                WorkflowRun.definition_id == candidate.definition_id,
                WorkflowRun.definition_sha256 == candidate.recipe.workflow.definition_sha256,
                WorkflowRun.input_ref == "event:" + row.source_ref,
            )
            .distinct()
            .limit(50)
        )
        return [run_view(run) for run in results]
