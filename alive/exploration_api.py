"""ALIVE-SF-01 P1: read-only, authority-backed exploration projection.

Project directly from ALIVE-12 research memories on every request. This deliberately
avoids another store that could retain withdrawn browser content.
"""
from __future__ import annotations

import hashlib
from collections import Counter

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select

from alive.research_memory import RESEARCH_KIND, _tokens
from alive.web_models import WebExperience

MAX_SOURCES = 200
MAX_CONCEPTS = 12


def _node_id(prefix: str, value: str) -> str:
    return prefix + "-" + hashlib.sha256(value.encode("utf-8")).hexdigest()[:20]


def project_inquiry(goal_id: str, goal_instruction: str, memories: list) -> dict:
    """No generated assertions: concept terms are explicitly labeled lexical candidates."""
    if len(memories) > MAX_SOURCES:
        raise ValueError("projection input exceeds limit")
    inquiry_id = _node_id("inquiry", goal_id)
    nodes = [{
        "id": inquiry_id, "kind": "inquiry", "label": goal_instruction[:300],
        "source_ref": goal_id, "status": "owner_declared",
    }]
    edges = []
    common = Counter()
    source_terms: dict[str, set[str]] = {}
    goal_terms = _tokens(goal_instruction)
    for memory in memories:
        data = memory.data
        terms = _tokens(data.get("excerpt", "")) - goal_terms
        source_terms[memory.id] = terms
        for term in terms:
            common[term] += 1
        nodes.append({
            "id": _node_id("source", memory.id),
            "kind": "source",
            "label": (data.get("title") or data.get("url") or "Reviewed source")[:300],
            "source_ref": memory.id,
            "url": data.get("url"),
            "sha256": data.get("sha256"),
            "status": "owner_saved",
        })
        edges.append({
            "source_id": inquiry_id, "target_id": _node_id("source", memory.id),
            "relation": "explores", "evidence_ref": memory.id,
            "status": "owner_saved",
        })
    # Require distinct sources to share a term before claiming a candidate concept.
    candidates = [
        term for term, frequency in sorted(common.items(), key=lambda p: (-p[1], p[0]))
        if frequency >= 2
    ][:MAX_CONCEPTS]
    for term in candidates:
        concept_id = _node_id("concept", goal_id + ":" + term)
        nodes.append({
            "id": concept_id, "kind": "concept", "label": term,
            "source_ref": None, "status": "lexical_candidate",
        })
        for memory in memories:
            if term in source_terms[memory.id]:
                edges.append({
                    "source_id": _node_id("source", memory.id), "target_id": concept_id,
                    "relation": "related_to", "evidence_ref": memory.id,
                    "status": "candidate",
                })
    return {
        "inquiry_id": inquiry_id, "goal_id": goal_id, "nodes": nodes, "edges": edges,
        "source_count": len(memories), "truncated": False,
        "interpretation": "Lexical candidate projection, not verified semantic relationships",
    }


async def projection_from_authoritative_store(web, goal_id: str) -> dict:
    """Every request rechecks ALIVE's instance-scoped active authoritative rows."""
    async with web.k.db.sessions() as session:
        goal = await web.get(session, goal_id, "goal")
        stmt = (
            select(WebExperience)
            .where(
                WebExperience.instance_id == web.k.instance_id,
                WebExperience.kind == RESEARCH_KIND,
                WebExperience.status == "active",
                WebExperience.data["goal_id"].as_string() == goal_id,
            )
            .order_by(WebExperience.created_at.desc(), WebExperience.id.desc())
            .limit(MAX_SOURCES + 1)
        )
        rows = (await session.scalars(stmt)).all()
        truncated = len(rows) > MAX_SOURCES
        rows = rows[:MAX_SOURCES]
        # Re-check the authoritative status, not the memory vector projection.
        result = project_inquiry(goal_id, goal.data["instruction"], rows)
        result["truncated"] = truncated
        return result


def router(app, ready):
    api = APIRouter(prefix="/api/v1/exploration", dependencies=[Depends(ready)])

    @api.get("/inquiries/{goal_id}")
    async def inquiry(goal_id: str):
        if not 1 <= len(goal_id) <= 128:
            raise HTTPException(422, "Invalid goal identifier")
        return await projection_from_authoritative_store(app.state.web, goal_id)

    @api.get("/inquiries")
    async def inquiries(limit: int = Query(30, ge=1, le=100)):
        # Only owner-declared companion goals, not arbitrary browser observations.
        web = app.state.web
        async with web.k.db.sessions() as session:
            rows = (await web.rows(session, "goal"))[-limit:]
            return {
                "inquiries": [{
                    "goal_id": row.id,
                    "label": row.data.get("instruction", "")[:300],
                    "source": "owner_instruction",
                } for row in rows]
            }

    return api
