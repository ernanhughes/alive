from typing import Literal

from fastapi import APIRouter, Depends
from fastapi.responses import HTMLResponse
from pydantic import BaseModel, ConfigDict
from sqlalchemy import select

from alive.living_models import LivingJourney, LivingPolicy
from alive.living_policy import world_html


class CreateLiving(BaseModel):
    model_config = ConfigDict(extra="forbid")
    provider: Literal["meta", "mock"] = "meta"
    allow_controlled_read: Literal[True]


def router(app, ready):
    route = APIRouter(prefix="/api/v1/living", dependencies=[Depends(ready)])

    @route.get("")
    async def status():
        async with app.state.kernel.db.sessions() as session:
            rows = (
                await session.scalars(
                    select(LivingJourney).order_by(LivingJourney.created_at.desc()).limit(20)
                )
            ).all()
            policy = await session.get(LivingPolicy, app.state.kernel.instance_id)
            return {
                "policy": policy.data,
                "active": app.state.living.active,
                "journeys": [
                    {
                        "id": r.id,
                        "status": r.status,
                        "provider": r.provider,
                        "episodes": len(r.data["episodes"]),
                        "error": r.data.get("error"),
                    }
                    for r in rows
                ],
            }

    @route.post("/journeys")
    async def create(data: CreateLiving):
        return await app.state.living.create(data.provider, data.allow_controlled_read)

    @route.get("/journeys/{journey_id}")
    async def detail(journey_id: str):
        return await app.state.living.detail(journey_id)

    @route.post("/journeys/{journey_id}/advance")
    async def advance(journey_id: str):
        return await app.state.living.advance(journey_id)

    @route.post("/journeys/{journey_id}/stop")
    async def stop(journey_id: str):
        return await app.state.living.cancel(journey_id)

    return route


def public_router(app):
    route = APIRouter()

    @route.get("/living/world/{journey_id}/{episode}", response_class=HTMLResponse)
    async def world(journey_id: str, episode: int):
        if episode not in {1, 2}:
            raise ValueError("Two predetermined situations only")
        async with app.state.kernel.db.sessions() as session:
            if not await session.get(LivingJourney, journey_id):
                raise KeyError("Unknown controlled habitat")
        return world_html()

    return route
