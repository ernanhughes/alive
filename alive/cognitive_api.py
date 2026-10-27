import json

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import HTMLResponse, Response
from sqlalchemy import select

from alive.cognitive_models import (
    ActionProposal,
    CognitiveObservation,
    Experience,
    Investigation,
    Laboratory,
)
from alive.cognitive_schema import (
    Approval,
    AutonomyCommand,
    CognitiveConfiguration,
    ImportApproval,
    ImportPreview,
    LabCreate,
)
from alive.laboratory import create_lab, inject_lab, lab_view, world_html
from alive.models import record
from alive.providers import MetaProvider


def router(app, ready):
    route = APIRouter(prefix="/api/v1", dependencies=[Depends(ready)])

    @route.get("/cognition")
    async def status():
        return await app.state.cognition.status()

    @route.post("/cognition/control")
    async def control(data: AutonomyCommand):
        result = await app.state.cognition.command(data)
        if data.command == "stop":
            for session_id in list(app.state.browsers.watchers):
                await app.state.browsers.watch(session_id, False)
        return result

    @route.post("/cognition/configuration")
    async def configuration(data: CognitiveConfiguration):
        return await app.state.cognition.configure(data)

    @route.get("/cognition/observations")
    async def observations():
        async with app.state.kernel.db.sessions() as session:
            return [
                record(r)
                for r in (
                    await session.scalars(
                        select(CognitiveObservation)
                        .order_by(CognitiveObservation.created_at.desc())
                        .limit(100)
                    )
                ).all()
            ]

    @route.get("/cognition/investigations")
    async def investigations():
        async with app.state.kernel.db.sessions() as session:
            return [
                record(r)
                for r in (
                    await session.scalars(
                        select(Investigation).order_by(Investigation.created_at.desc()).limit(100)
                    )
                ).all()
            ]

    @route.get("/cognition/investigations/{run_id}")
    async def detail(run_id: str):
        return await app.state.cognition.detail(run_id)

    @route.post("/cognition/investigations/{run_id}/cancel")
    async def cancel(run_id: str):
        cog = app.state.cognition
        if cog.worker and not cog.worker.done():
            async with cog.k.db.sessions() as session:
                active = await session.scalar(
                    select(Investigation).where(
                        ~Investigation.state.in_(["COMPLETED", "ABSTAINED", "FAILED", "CANCELLED"])
                    )
                )
            if active and active.id == run_id:
                cog.worker.cancel()
                await cog.worker
                return {"status": "cancelled"}
        await cog.finish(
            run_id, "CANCELLED", {"effect": "none", "reason": "human cancellation"}, truncated=True
        )
        return {"status": "cancelled"}

    @route.get("/cognition/actions")
    async def actions():
        async with app.state.kernel.db.sessions() as session:
            return [
                record(r)
                for r in (
                    await session.scalars(
                        select(ActionProposal).order_by(ActionProposal.created_at.desc()).limit(100)
                    )
                ).all()
            ]

    @route.post("/cognition/actions/{action_id}/decision")
    async def approve(action_id: str, data: Approval):
        return await app.state.cognition.approve(action_id, data.decision)

    @route.get("/experiences")
    async def experiences():
        async with app.state.kernel.db.sessions() as session:
            return [
                record(r)
                for r in (
                    await session.scalars(
                        select(Experience).order_by(Experience.created_at.desc()).limit(100)
                    )
                ).all()
            ]

    @route.get("/experiences/export")
    async def export(after: str = "", limit: int = Query(100, ge=1, le=1000)):
        async with app.state.kernel.db.sessions() as session:
            rows = (
                await session.scalars(
                    select(Experience)
                    .where(Experience.id > after)
                    .order_by(Experience.id)
                    .limit(limit)
                )
            ).all()
            return Response(
                "\n".join(json.dumps(r.data, default=str) for r in rows) + "\n",
                media_type="application/x-ndjson",
                headers={"X-Next-Cursor": rows[-1].id if rows else after},
            )

    @route.post("/experiences/{experience_id}/replay")
    async def replay(experience_id: str):
        from alive.society import evaluate

        async with app.state.kernel.db.sessions() as session:
            row = await session.get(Experience, experience_id)
            if not row:
                raise HTTPException(404, "Experience not found")
            state = row.data["state_snapshot"]
            return {
                "mode": "deterministic_recorded_evidence_replay",
                "model_reexecuted": False,
                "environment": state.get("environment_id"),
                "state_hash": state.get("state_hash"),
                "observation_evaluation": evaluate(
                    state.get("claims", []), [], state.get("sources", [])
                ),
                "original_evaluation": row.data["evaluation"],
            }

    @route.post("/providers/meta/probe")
    async def probe():
        return await MetaProvider(app.state.kernel.settings).discover()

    @route.post("/memories/index")
    async def index():
        return await app.state.memory.index()

    @route.post("/history/preview")
    async def preview(data: ImportPreview):
        return await app.state.memory.preview_import(data)

    @route.post("/history/{import_id}/decision")
    async def import_decision(import_id: str, data: ImportApproval):
        return await app.state.memory.approve_import(import_id, data.approved)

    @route.delete("/history/{import_id}")
    async def revoke(import_id: str):
        return await app.state.memory.revoke_import(import_id)

    @route.post("/lab")
    async def lab(data: LabCreate):
        return await create_lab(app.state.kernel, data)

    @route.post("/lab/{environment_id}/inject")
    async def inject(environment_id: str):
        return await inject_lab(app.state.kernel, environment_id)

    @route.post("/browser/sessions/{session_id}/observation")
    async def watch(session_id: str, data: ImportApproval):
        return await app.state.browsers.watch(session_id, data.approved)

    return route


def public_router(app):
    route = APIRouter()

    @route.get("/world/{environment_id}", response_class=HTMLResponse)
    async def world(environment_id: str):
        from uuid import UUID

        try:
            UUID(environment_id)
        except ValueError as exc:
            raise HTTPException(404, "Unknown habitat") from exc
        return world_html(environment_id)

    @route.get("/api/v1/lab/world/{environment_id}")
    async def world_state(environment_id: str):
        async with app.state.kernel.db.sessions() as session:
            lab = await session.get(Laboratory, environment_id)
            if not lab:
                raise HTTPException(404, "Unknown habitat")
            # Only explicitly synthetic laboratory state is public to its local browser page.
            return lab_view(lab)

    return route
