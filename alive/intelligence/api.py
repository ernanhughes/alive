"""Authenticated, typed, allow-listed read-only Intelligence inspection."""

from fastapi import APIRouter, Depends, HTTPException, Path, Query
from pydantic import BaseModel, ConfigDict
from sqlalchemy import select

from .models import IntelligenceEpisode, IntelligenceState
from .store import inspect_chain, owned


class EpisodeView(BaseModel):
    model_config = ConfigDict(extra="forbid")
    id: str
    proposal_id: str
    previous_id: str | None
    workflow_run_id: str
    workflow_stage_id: str
    definition_sha256: str
    workflow_state: str
    source_event_id: str
    source_hash: str
    context_hash: str
    snapshot_hash: str
    evidence_status: str
    active_policy_choice: str | None
    intelligence_proposal: str | None
    shadow_suggestion: str | None
    authorized_action: str | None
    executed_action: str | None
    authorization_status: str
    execution_basis: str
    model_invocation_id: str | None
    pi_run_id: str | None
    feedback_id: str | None
    feedback_status: str
    observed_fixture_action: str | None
    observed_reward: float | None
    feedback_source_event_id: str | None
    authority_class: str | None
    learning_update_id: str | None
    before_hash: str | None
    after_hash: str | None


class ChainView(BaseModel):
    model_config = ConfigDict(extra="forbid")
    id: str
    goal_id: str
    active_hash: str
    candidate_hash: str
    candidate_revision: int
    monitor_samples: int
    retrieve_samples: int
    quarantined: bool
    episodes: list[EpisodeView]


def router(app, ready):
    api = APIRouter(prefix="/api/v1/intelligence", dependencies=[Depends(ready)])

    @api.get("/states", response_model=list[str])
    async def states(limit: int = Query(50, ge=1, le=200)):
        kernel = app.state.kernel
        async with kernel.db.sessions() as session:
            return list(
                await session.scalars(
                    select(IntelligenceState.id)
                    .where(IntelligenceState.instance_id == kernel.instance_id)
                    .order_by(IntelligenceState.created_at.desc())
                    .limit(limit)
                )
            )

    @api.get("/states/{state_id}", response_model=ChainView)
    async def state(state_id: str = Path(max_length=36)):
        try:
            return await inspect_chain(app.state.kernel, state_id)
        except (ValueError, KeyError, TypeError):
            raise HTTPException(
                404, "Intelligence record unavailable or integrity check failed"
            ) from None

    @api.get("/episodes/{episode_id}", response_model=EpisodeView)
    async def episode(episode_id: str = Path(max_length=100)):
        kernel = app.state.kernel
        try:
            async with kernel.db.sessions() as session:
                row = await owned(session, IntelligenceEpisode, episode_id, kernel.instance_id)
                state_id = row.state_id
            chain = await inspect_chain(kernel, state_id)
            return next(e for e in chain["episodes"] if e["id"] == episode_id)
        except (ValueError, KeyError, TypeError):
            raise HTTPException(
                404, "Intelligence record unavailable or integrity check failed"
            ) from None

    return api
