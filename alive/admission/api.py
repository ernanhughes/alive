from fastapi import APIRouter, Depends, HTTPException, Path
from sqlalchemy import select

from alive.admission import service
from alive.admission.contracts import Confirmation, ReviewRequest
from alive.admission.models import Admission
from alive.bespoke.recipes import recipe_hash
from alive.sources import custody
from alive.sources.models import SourceApproval, SourceCapture


def router(app, ready):
    api = APIRouter(prefix="/api/v1/admissions", dependencies=[Depends(ready)])

    async def safe(work):
        try:
            return await work
        except (ValueError, KeyError, TypeError):
            raise HTTPException(
                409, "Admission unavailable, unapproved, expired or changed"
            ) from None

    @api.get("/profile")
    async def profile():
        recipe = service.recipe_for(app.state.kernel)
        return {"recipe": recipe.model_dump(mode="json"), "recipe_sha256": recipe_hash(recipe)}

    @api.get("/sources")
    async def sources():
        kernel = app.state.kernel
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
                    if service.aware(a.expires_at) > service.now()
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

    @api.get("/{admission_id}")
    async def detail(admission_id: str = Path(max_length=36)):
        return await safe(service.get(app.state.kernel, admission_id))

    @api.post("/{admission_id}/start")
    async def start(request: Confirmation, admission_id: str = Path(max_length=36)):
        return await safe(service.start(app, admission_id, request.review_sha256))

    @api.post("/{admission_id}/cancel")
    async def cancel(admission_id: str = Path(max_length=36)):
        return await safe(service.cancel(app, admission_id))

    return api
