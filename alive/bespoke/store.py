"""Transactional idempotent recommendations. Historical reads never resolve today's recipes."""

import asyncio

from sqlalchemy import select

from alive.bespoke.context import resolve_context
from alive.bespoke.contracts import RecommendationView, Selection
from alive.bespoke.models import Recommendation
from alive.bespoke.selector import POLICY, select_recipe
from alive.capabilities.bindings import digest
from alive.capabilities.contracts import json_bytes
from alive.workflows.context import aware, require


def view(row):
    require(digest(row.selection) == row.selection_sha256, "recommendation_integrity")
    return RecommendationView(
        id=row.id,
        created_at=aware(row.created_at).isoformat(),
        principal=row.principal,
        selection_sha256=row.selection_sha256,
        selection=Selection.model_validate(row.selection),
    )


async def recommend(kernel, catalogue, request):
    # Includes database waits; no unbounded model, network, or background work.
    async with asyncio.timeout(POLICY["deadline_seconds"]):
        async with kernel.lock, kernel.db.sessions.begin() as session:
            grant, context = await resolve_context(session, kernel, request)
            existing = await session.scalar(
                select(Recommendation).where(
                    Recommendation.instance_id == kernel.instance_id,
                    Recommendation.principal == grant.principal,
                    Recommendation.idempotency_key == request.idempotency_key,
                )
            )
            request_hash = digest(request.model_dump(mode="json"))
            if existing:
                require(existing.request_sha256 == request_hash, "idempotency_conflict")
                return view(existing)
            result = await select_recipe(session, kernel, catalogue, request, grant, context)
            payload = result.model_dump(mode="json")
            require(len(json_bytes(payload)) <= POLICY["max_record_bytes"], "record_size_limit")
            row = Recommendation(
                instance_id=kernel.instance_id,
                principal=grant.principal,
                goal_id=grant.goal_id,
                investigation_id=grant.investigation_id,
                source_ref=grant.context_event_id,
                idempotency_key=request.idempotency_key,
                request_sha256=request_hash,
                selection_sha256=digest(payload),
                selection=payload,
            )
            session.add(row)
            await session.flush()
            kernel.add_event(
                session,
                "bespoke.selection.recorded",
                {
                    "recommendation_id": row.id,
                    "selection_sha256": row.selection_sha256,
                    "state": result.state,
                },
                source="bespoke",
                correlation=grant.investigation_id,
            )
            return view(row)


async def get(kernel, recommendation_id):
    async with kernel.db.sessions() as session:
        row = await session.scalar(
            select(Recommendation).where(
                Recommendation.id == recommendation_id,
                Recommendation.instance_id == kernel.instance_id,
            )
        )
        require(row is not None, "recommendation_unavailable")
        return view(row)


async def history(kernel):
    async with kernel.db.sessions() as session:
        rows = (
            await session.scalars(
                select(Recommendation)
                .where(
                    Recommendation.instance_id == kernel.instance_id,
                )
                .order_by(Recommendation.created_at.desc(), Recommendation.id)
                .limit(50)
            )
        ).all()
        return [
            {
                "id": r.id,
                "created_at": aware(r.created_at).isoformat(),
                "state": r.selection["state"],
            }
            for r in rows
        ]
