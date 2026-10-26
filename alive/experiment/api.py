from fastapi import APIRouter, Depends
from sqlalchemy import select

from alive.experiment.schema import FullAuthorization, RunRequest
from alive.experiment.service import ExperimentRun


def router(app, ready):
    routes = APIRouter(prefix="/api/v1/experiments", dependencies=[Depends(ready)])

    @routes.get("")
    async def list_runs():
        async with app.state.kernel.db.sessions() as session:
            rows = (
                await session.scalars(
                    select(ExperimentRun).order_by(ExperimentRun.created_at.desc()).limit(20)
                )
            ).all()
            return [
                {
                    "id": row.id,
                    "phase": row.phase,
                    "provider": row.provider,
                    "status": row.status,
                    "created_at": row.created_at,
                    "completed_tasks": row.data["completed_tasks"],
                    "tasks": len(row.data["task_ids"]),
                    "summary": row.data.get("summary"),
                    "error": row.data.get("error"),
                    "freeze_id": row.data["freeze_id"],
                }
                for row in rows
            ]

    @routes.get("/review-pack")
    async def review():
        return await app.state.experiments.review()

    @routes.post("/freeze-design")
    async def freeze_design():
        return await app.state.experiments.freeze()

    @routes.post("/runs")
    async def start(data: RunRequest):
        return await app.state.experiments.start(data)

    @routes.post("/authorize-full")
    async def authorize(data: FullAuthorization):
        return await app.state.experiments.authorize(data)

    @routes.get("/runs/{run_id}")
    async def detail(run_id: str):
        return await app.state.experiments.detail(run_id)

    @routes.post("/runs/{run_id}/freeze-policy")
    async def freeze_policy(run_id: str):
        return await app.state.experiments.finalize(run_id)

    @routes.post("/stop")
    async def stop():
        return await app.state.experiments.cancel()

    return routes
