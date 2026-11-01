from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Path, Query
from sqlalchemy import select

from alive.admission import live, service
from alive.admission.contracts import (
    Confirmation,
    ConversationRequest,
    LiveGoal,
    LiveSetup,
    ReviewRequest,
)
from alive.admission.models import Admission
from alive.admission.profiles import PROFILES
from alive.bespoke.recipes import recipe_hash
from alive.intent import service as intent_service
from alive.sources import custody
from alive.sources.models import SourceApproval, SourceCapture
from alive.workflows.context import Refused


def router(app, ready):
    api = APIRouter(prefix="/api/v1/admissions", dependencies=[Depends(ready)])

    async def safe(work):
        try:
            return await work
        except Refused as error:
            category = str(error)
            if category.isidentifier() and category.startswith(
                ("context", "conversation", "essential_context")
            ):
                raise HTTPException(409, category) from None
            raise HTTPException(
                409, "Admission unavailable, unapproved, expired or changed"
            ) from None
        except (ValueError, KeyError, TypeError):
            raise HTTPException(
                409, "Admission unavailable, unapproved, expired or changed"
            ) from None

    ProfileName = Literal[
        "approved-repository-inspection",
        "approved-repository-analysis",
        "intent-interpretation",
        "contextual-reasoning",
    ]

    @api.get("/profile")
    async def profile(profile: ProfileName = Query("approved-repository-inspection")):
        recipe = service.recipe_for(app.state.kernel, profile)
        return {
            "profile": profile,
            "model_call": PROFILES[profile].model,
            "recipe": recipe.model_dump(mode="json"),
            "recipe_sha256": recipe_hash(recipe),
        }

    @api.get("/sources")
    async def sources(profile: ProfileName = Query("approved-repository-inspection")):
        kernel = app.state.kernel
        needed = set(PROFILES[profile].source_operations)
        async with kernel.db.sessions() as session:
            rows = await session.execute(
                select(SourceApproval, SourceCapture)
                .join(SourceCapture, SourceCapture.id == SourceApproval.capture_id)
                .where(
                    SourceApproval.instance_id == kernel.instance_id,
                    SourceCapture.instance_id == kernel.instance_id,
                    SourceCapture.source_type == "repository",
                    SourceApproval.withdrawn_at.is_(None),
                )
                .order_by(SourceApproval.approved_at.desc())
                .limit(50)
            )
            return {
                "sources": [
                    {
                        "approval_ref": a.id,
                        "capture_ref": c.id,
                        "label": c.label,
                        "content_sha256": c.content_sha256,
                        "scope": a.scope,
                        "inventory": custody.inventory(
                            c.source_type, custody.apply_scope(c.source_type, c.content, a.scope)
                        ),
                        "expires_at": a.expires_at.isoformat(),
                    }
                    for a, c in rows
                    if service.aware(a.expires_at) > service.now() and needed <= set(a.operations)
                ]
            }

    @api.get("")
    async def listing():
        kernel = app.state.kernel
        async with kernel.db.sessions() as session:
            rows = (
                await session.scalars(
                    select(Admission)
                    .where(Admission.instance_id == kernel.instance_id)
                    .order_by(Admission.created_at.desc())
                    .limit(20)
                )
            ).all()
            return {"admissions": [await service.view(session, kernel, row) for row in rows]}

    @api.post("")
    async def prepare(request: ReviewRequest):
        return await safe(service.prepare(app.state.kernel, request))

    @api.get("/live")
    async def live_history():
        return await safe(live.listing(app.state.kernel))

    @api.post("/live/setup")
    async def live_setup(request: LiveSetup):
        return await safe(live.prepare(app.state.kernel, request))

    @api.post("/live/ask")
    async def live_ask(request: LiveGoal):
        return await safe(live.ask(app, request))

    @api.post("/live/conversations")
    async def new_conversation(request: ConversationRequest):
        from alive.continuity.service import create

        return await safe(create(app.state.kernel, request.consent_ref, request.title))

    @api.get("/live/{admission_id}")
    async def live_exchange(admission_id: str = Path(max_length=36)):
        return await safe(live.exchange(app.state.kernel, admission_id))

    @api.get("/{admission_id}")
    async def detail(admission_id: str = Path(max_length=36)):
        return await safe(service.get(app.state.kernel, admission_id))

    @api.get("/{admission_id}/report")
    async def report(admission_id: str = Path(max_length=36)):
        return await safe(service.report(app.state.kernel, admission_id))

    @api.post("/{admission_id}/recommendation")
    async def compose_recommendation(admission_id: str = Path(max_length=36)):
        # Deterministic: reads the retained interpretation and re-runs eligibility. No model call.
        return await safe(intent_service.compose(app.state.kernel, admission_id))

    @api.get("/{admission_id}/recommendation")
    async def recommendation(admission_id: str = Path(max_length=36)):
        return await safe(intent_service.get(app.state.kernel, admission_id))

    @api.post("/{admission_id}/start")
    async def start(request: Confirmation, admission_id: str = Path(max_length=36)):
        return await safe(service.start(app, admission_id, request.review_sha256))

    @api.post("/{admission_id}/cancel")
    async def cancel(admission_id: str = Path(max_length=36)):
        return await safe(service.cancel(app, admission_id))

    return api
