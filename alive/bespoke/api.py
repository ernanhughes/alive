"""Authenticated recommendations and history. Execution and approval have no routes."""

from fastapi import APIRouter, Depends, HTTPException, Path
from sqlalchemy import select

from alive.bespoke import store
from alive.bespoke.contracts import RecommendationView, RecommendRequest
from alive.bespoke.handoff import linked_runs
from alive.bespoke.recipes import recipe_hash
from alive.capabilities.bindings import binding_record, registry_for
from alive.capabilities.trusted import permission_bits
from alive.models import Event
from alive.workflows.context import OWNER, authorized
from alive.workflows.models import WorkflowDefinition
from alive.workflows.spec import definition_sha256, parse_definition


async def catalogue_view(kernel, catalogue):
    result = []
    registry = registry_for(kernel)
    async with kernel.db.sessions() as session:
        for recipe in catalogue:
            reasons = []
            if recipe.status != "active":
                reasons.append("recipe_unavailable")
            for pin in recipe.capabilities:
                try:
                    cap = registry.get(pin.id, pin.version)
                    if not cap.executable:
                        reasons.append("missing_capability")
                    elif cap.manifest_sha256 != pin.manifest_sha256:
                        reasons.append("capability_identity_changed")
                except KeyError:
                    reasons.append("missing_capability")
            definition = await session.scalar(
                select(WorkflowDefinition).where(
                    WorkflowDefinition.name == recipe.workflow.name,
                    WorkflowDefinition.version == recipe.workflow.version,
                )
            )
            if definition is None or definition.status != "active":
                reasons.append("workflow_unavailable")
            else:
                try:
                    spec = parse_definition(
                        definition.definition_json, operations=registry.operations
                    )
                    if not (
                        definition_sha256(spec)
                        == definition.definition_sha256
                        == recipe.workflow.definition_sha256
                    ):
                        reasons.append("workflow_identity_changed")
                    binding = await binding_record(session, kernel, definition)
                    if registry.bind(spec) != binding.snapshot["stages"]:
                        reasons.append("binding_changed")
                    pins = {p.stage_id: p for p in recipe.capabilities}
                    if set(pins) != set(binding.snapshot["stages"]):
                        reasons.append("capability_identity_changed")
                    for stage_id, bound in binding.snapshot["stages"].items():
                        cap = registry.recheck(bound["identity"])
                        pin = pins.get(stage_id)
                        if pin is None or any(
                            getattr(pin, k) != bound["identity"][k]
                            for k in ("id", "version", "manifest_sha256")
                        ):
                            reasons.append("capability_identity_changed")
                        if not permission_bits(cap.manifest["permissions"]) <= set(
                            recipe.limits.permissions
                        ):
                            reasons.append("permission_not_grantable")
                except (ValueError, TypeError, KeyError):
                    reasons.append("binding_changed")
            result.append(
                {
                    "recipe": recipe.model_dump(mode="json"),
                    "recipe_sha256": recipe_hash(recipe),
                    "status": "unavailable" if reasons else "installed",
                    "reasons": sorted(set(reasons)),
                    "authorization": "unavailable",
                }
            )
    return {"recipes": result, "execution_available": False}


def router(app, ready):
    api = APIRouter(prefix="/api/v1/bespoke", dependencies=[Depends(ready)])

    def kernel():
        return app.state.kernel

    async def safe(awaitable):
        try:
            return await awaitable
        except TimeoutError:
            raise HTTPException(503, "Selection deadline exceeded") from None
        except (ValueError, TypeError, KeyError):
            raise HTTPException(409, "Context, approval or record unavailable or changed") from None

    @api.get("/recipes")
    async def recipes():
        return await catalogue_view(kernel(), app.state.bespoke_recipes)

    @api.get("/contexts")
    async def contexts():
        # References only. Existing grants are read, never minted or widened.
        current = kernel()
        result = []
        async with current.db.sessions() as session:
            events = (
                await session.scalars(
                    select(Event)
                    .where(
                        Event.instance_id == current.instance_id,
                        Event.source == OWNER,
                        Event.event_type == "workflow.execution.authorized",
                    )
                    .order_by(Event.sequence_number.desc())
                    .limit(50)
                )
            ).all()
            for event in events:
                try:
                    grant, _, _, _, _, _ = await authorized(session, current, event.id)
                    result.append(
                        {
                            "approval_ref": event.id,
                            "goal_ref": grant.goal_id,
                            "investigation_ref": grant.investigation_id,
                            "source_ref": grant.context_event_id,
                            "source_sha256": grant.context_sha256,
                        }
                    )
                except (ValueError, KeyError, TypeError):
                    continue
        return {"contexts": result}

    @api.post("/recommend", response_model=RecommendationView)
    async def recommend(request: RecommendRequest):
        return await safe(store.recommend(kernel(), app.state.bespoke_recipes, request))

    @api.get("/recommendations")
    async def history():
        return {"recommendations": await store.history(kernel())}

    @api.get("/recommendations/{recommendation_id}", response_model=RecommendationView)
    async def recommendation(recommendation_id: str = Path(max_length=36)):
        return await safe(store.get(kernel(), recommendation_id))

    @api.get("/recommendations/{recommendation_id}/runs")
    async def runs(recommendation_id: str = Path(max_length=36)):
        return {"runs": await safe(linked_runs(kernel(), recommendation_id))}

    return api
