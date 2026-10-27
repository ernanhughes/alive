"""Goal-scoped cross-page research memory over reviewed companion observations.

The WebExperience research row remains the authoritative record. The existing Memory and
MemoryVector tables are a rebuildable retrieval projection, not a second source of truth.
"""

import hashlib
import re
from datetime import UTC, datetime

from sqlalchemy import select

from alive.cognitive_models import MemoryVector
from alive.models import Memory, now, record

RESEARCH_KIND = "research_memory"
CONNECTION_KIND = "research_connection"
INDEX_VERSION = "alive12-research-v1"
STOPWORDS = {
    "about",
    "after",
    "again",
    "also",
    "and",
    "are",
    "because",
    "before",
    "between",
    "both",
    "but",
    "can",
    "could",
    "does",
    "for",
    "from",
    "has",
    "have",
    "into",
    "its",
    "more",
    "not",
    "the",
    "their",
    "them",
    "then",
    "there",
    "these",
    "they",
    "this",
    "that",
    "was",
    "were",
    "what",
    "when",
    "where",
    "which",
    "while",
    "with",
    "would",
}
TOKEN = re.compile(r"[a-z0-9][a-z0-9_-]{2,}")


def _tokens(text):
    return {term for term in TOKEN.findall((text or "").lower()) if term not in STOPWORDS}


def _projection_id(instance_id, note_id):
    return "rm-" + hashlib.sha256(f"{instance_id}|{note_id}".encode()).hexdigest()[:33]


def _age_days(value):
    try:
        then = datetime.fromisoformat(value.replace("Z", "+00:00"))
        if then.tzinfo is None:
            then = then.replace(tzinfo=UTC)
        return max(0.0, (now() - then).total_seconds() / 86400)
    except (AttributeError, TypeError, ValueError):
        return None


def _sentence(text, terms):
    for sentence in re.split(r"(?<=[.!?])\s+", text or ""):
        if any(term in _tokens(sentence) for term in terms):
            return sentence.strip()[:300]
    return None


class ResearchMemory:
    def __init__(self, web, memory):
        self.web, self.memory = web, memory
        self.k = web.k

    async def _research_row(self, session, research_id):
        row = await self.web.get(session, research_id, RESEARCH_KIND)
        if row.instance_id != self.k.instance_id:
            raise KeyError("Unknown research memory")
        return row

    async def _latest_feedback(self, session, note_id):
        rows = [row for row in await self.web.rows(session, "feedback") if row.parent_id == note_id]
        return rows[-1].data.get("useful") if rows else None

    async def save(self, note_id):
        async with self.k.lock, self.k.db.sessions.begin() as session:
            note = await self.web.get(session, note_id, "note")
            if note.status != "validated" or not note.data.get("output"):
                raise ValueError("Only a validated note can be saved for research")
            existing = next(
                (
                    row
                    for row in await self.web.rows(session, RESEARCH_KIND)
                    if row.parent_id == note.id
                ),
                None,
            )
            if existing:
                if existing.status != "active":
                    raise ValueError("This research memory was withdrawn and cannot be resurrected")
                result = record(existing)
                result["idempotent"] = True
                result["index"] = {"available": self.memory.embedding.available}
                return result
            snapshot = await self.web.get(session, note.parent_id, "snapshot")
            goal = await self.web.get(session, note.data["goal_id"], "goal")
            excerpt = snapshot.data["text"][:2000]
            usefulness = await self._latest_feedback(session, note.id)
            row = self.web.add(
                session,
                RESEARCH_KIND,
                {
                    "goal_id": goal.id,
                    "url": snapshot.data["url"],
                    "title": snapshot.data.get("title", ""),
                    "note_id": note.id,
                    "snapshot_id": snapshot.id,
                    "sha256": snapshot.data["sha256"],
                    "language_requested": snapshot.data.get("language_requested", "auto"),
                    "source_kind": "reviewed_browser_excerpt",
                    "excerpt": excerpt,
                    "evidence_quote": note.data["output"].get("evidence_quote"),
                    "note_summary": note.data["output"].get("summary"),
                    "note_limitations": note.data["output"].get("limitations"),
                    "owner_useful": usefulness,
                    "model": note.data.get("model"),
                    "model_policy_version": note.data.get("policy_version"),
                    "saved_at": now().isoformat(),
                    "reviewed_at": snapshot.created_at.isoformat(),
                    "status": "active",
                    "index_version": INDEX_VERSION,
                    "withdrawn_at": None,
                },
                note.id,
                "active",
            )
            await session.flush()
            projection_id = _projection_id(self.k.instance_id, note.id)
            projection = await session.get(Memory, projection_id)
            if not projection:
                projection = Memory(
                    id=projection_id,
                    instance_id=self.k.instance_id,
                    content=excerpt,
                    memory_type="research_memory",
                    source_event_id=None,
                    importance=0.5,
                    confidence=1.0,
                    metadata_json={
                        "research_memory_id": row.id,
                        "goal_id": goal.id,
                        "url": snapshot.data["url"],
                        "note_id": note.id,
                        "snapshot_id": snapshot.id,
                        "sha256": snapshot.data["sha256"],
                        "source_kind": "reviewed_browser_excerpt",
                        "index_version": INDEX_VERSION,
                        "saved_at": row.data["saved_at"],
                    },
                )
                session.add(projection)
            row.data = row.data | {
                "memory_projection_id": projection_id,
                "index_model": self.memory.embedding.model_id,
                "index_revision": self.memory.embedding.revision,
            }
            await session.flush()
            result = record(row)
        index = await self.memory.index(limit=32)
        result["index"] = index | {"available": self.memory.embedding.available}
        return result

    async def sync_feedback(self, session, note_id):
        row = next(
            (
                item
                for item in await self.web.rows(session, RESEARCH_KIND)
                if item.parent_id == note_id and item.status == "active"
            ),
            None,
        )
        if not row:
            return
        usefulness = await self._latest_feedback(session, note_id)
        row.data = row.data | {"owner_useful": usefulness}
        projection = await session.get(Memory, row.data.get("memory_projection_id"))
        if projection:
            projection.metadata_json = projection.metadata_json | {"owner_useful": usefulness}

    async def withdraw(self, research_id):
        async with self.k.lock, self.k.db.sessions.begin() as session:
            row = await self._research_row(session, research_id)
            if row.status == "withdrawn":
                return record(row) | {"idempotent": True}
            row.status = "withdrawn"
            row.data = row.data | {
                "status": "withdrawn",
                "withdrawn_at": now().isoformat(),
            }
            projection_id = row.data.get("memory_projection_id")
            if projection_id:
                vector_rows = (
                    await session.scalars(
                        select(MemoryVector).where(MemoryVector.memory_id == projection_id)
                    )
                ).all()
                for vector in vector_rows:
                    await session.delete(vector)
                projection = await session.get(Memory, projection_id)
                if projection:
                    await session.delete(projection)
            self.k.add_event(
                session,
                "research.memory_withdrawn",
                {"research_memory_id": row.id, "note_id": row.parent_id},
            )
            return record(row)

    async def list(self, goal_id=None):
        async with self.k.db.sessions() as session:
            rows = [
                row
                for row in await self.web.rows(session, RESEARCH_KIND)
                if row.status == "active" and (not goal_id or row.data["goal_id"] == goal_id)
            ]
            return {"memories": [record(row) for row in rows]}

    async def retrieve(self, snapshot_id, top_k=3, mode="hybrid"):
        if not 1 <= top_k <= 5:
            raise ValueError("top_k must be 1-5")
        async with self.k.db.sessions() as session:
            snapshot = await self.web.get(session, snapshot_id, "snapshot")
            goal = await self.web.get(session, snapshot.data["goal_id"], "goal")
            goal_id = goal.id
            current_url = snapshot.data["url"]
            current_sha = snapshot.data["sha256"]
            query = goal.data["instruction"] + " " + snapshot.data["text"][:1200]
            active = {
                row.id: row
                for row in await self.web.rows(session, RESEARCH_KIND)
                if row.status == "active" and row.data["goal_id"] == goal_id
            }
        try:
            retrieved = await self.memory.retrieve(query, mode=mode, top_k=top_k * 5)
        except ValueError:
            retrieved = await self.memory.retrieve(query, mode="text", top_k=top_k * 5)
        results, seen = [], set()
        for item in retrieved.get("results", []):
            metadata = item.get("metadata") or {}
            research_id = metadata.get("research_memory_id")
            if (
                item.get("memory_type") != "research_memory"
                or item.get("instance_id") != self.k.instance_id
                or metadata.get("goal_id") != goal_id
                or metadata.get("url") == current_url
                or metadata.get("sha256") == current_sha
                or research_id not in active
                or metadata.get("sha256") in seen
            ):
                continue
            row = active[research_id]
            seen.add(metadata.get("sha256"))
            latest = await self._latest_feedback_for(row.parent_id)
            results.append(
                {
                    "memory_id": row.id,
                    "source_url": row.data["url"],
                    "source_title": row.data.get("title"),
                    "goal_id": row.data["goal_id"],
                    "reviewed_at": row.data.get("reviewed_at"),
                    "age_days": _age_days(row.data.get("reviewed_at")),
                    "excerpt": row.data["excerpt"],
                    "evidence_quote": row.data.get("evidence_quote"),
                    "note_summary": row.data.get("note_summary"),
                    "owner_useful": latest,
                    "retrieval_score": item.get("retrieval_score"),
                    "retrieval_method": retrieved.get("mode"),
                    "same_source": False,
                    "sha256": row.data["sha256"],
                    "source_kind": row.data.get("source_kind"),
                    "status": row.status,
                }
            )
            if len(results) >= top_k:
                break
        return {
            "current_snapshot_id": snapshot_id,
            "current_url": current_url,
            "goal_id": goal_id,
            "mode": retrieved.get("mode"),
            "embedding": retrieved.get("embedding"),
            "results": results,
            "abstained": not results,
            "count": len(results),
            "message": "No related authorised research memory found."
            if not results
            else "Related historical evidence is distinct from current-page evidence.",
        }

    async def _latest_feedback_for(self, note_id):
        async with self.k.db.sessions() as session:
            return await self._latest_feedback(session, note_id)

    async def connect(self, snapshot_id, research_id):
        async with self.k.lock, self.k.db.sessions.begin() as session:
            snapshot = await self.web.get(session, snapshot_id, "snapshot")
            memory = await self._research_row(session, research_id)
            if memory.status != "active":
                raise ValueError("Research memory is withdrawn")
            if memory.data["goal_id"] != snapshot.data["goal_id"]:
                raise ValueError("Research memory belongs to a different goal")
            if memory.data["url"] == snapshot.data["url"]:
                raise ValueError("A connection requires a different source page")
            goal = await self.web.get(session, snapshot.data["goal_id"], "goal")
            current_text = snapshot.data["text"]
            historical_text = memory.data["excerpt"]
            shared = sorted(_tokens(current_text) & _tokens(historical_text))
            historical_quote = memory.data.get("evidence_quote")
            if historical_quote and historical_quote not in historical_text:
                historical_quote = None
            current_quote = _sentence(current_text, shared) if shared else None
            if historical_quote and not _sentence(historical_text, shared):
                historical_quote = historical_quote if historical_quote in historical_text else None
            if len(shared) >= 2 and current_quote and historical_quote:
                relation = "same_concept"
                status = "candidate"
                explanation = (
                    "Both reviewed excerpts contain the shared terms "
                    + ", ".join(shared[:6])
                    + ". This is a retrieval candidate, not independent factual corroboration."
                )
            elif len(shared) == 1 and current_quote and historical_quote:
                relation = "complementary"
                status = "candidate"
                explanation = (
                    f"The excerpts share the term '{shared[0]}'. The relationship is weak and "
                    "requires owner review."
                )
            else:
                relation = "no_supported_connection"
                status = "insufficient_evidence"
                explanation = (
                    "No inspectable shared evidence supports a research connection between these "
                    "two reviewed sources."
                )
            row = self.web.add(
                session,
                CONNECTION_KIND,
                {
                    "goal_id": goal.id,
                    "current_snapshot_id": snapshot.id,
                    "current_url": snapshot.data["url"],
                    "current_sha256": snapshot.data["sha256"],
                    "current_quote": current_quote,
                    "historical_memory_id": memory.id,
                    "historical_url": memory.data["url"],
                    "historical_sha256": memory.data["sha256"],
                    "historical_quote": historical_quote,
                    "shared_terms": shared[:12],
                    "relation_type": relation,
                    "explanation": explanation,
                    "status": status,
                    "model": "deterministic-lexical-connection-v1",
                    "inference_calls": 0,
                    "owner_useful": None,
                    "quote_validation": {
                        "current_exact": bool(current_quote and current_quote in current_text),
                        "historical_exact": bool(
                            historical_quote and historical_quote in historical_text
                        ),
                    },
                    "created_at": now().isoformat(),
                },
                snapshot.id,
                status,
            )
            await session.flush()
            return record(row) | {
                "current_source": {
                    "url": snapshot.data["url"],
                    "sha256": snapshot.data["sha256"],
                },
                "historical_source": {
                    "url": memory.data["url"],
                    "sha256": memory.data["sha256"],
                    "reviewed_at": memory.data.get("reviewed_at"),
                },
                "abstained": status == "insufficient_evidence",
            }

    async def connection_feedback(self, connection_id, useful):
        async with self.k.lock, self.k.db.sessions.begin() as session:
            row = await self.web.get(session, connection_id, CONNECTION_KIND)
            row.data = row.data | {
                "owner_useful": bool(useful),
                "feedback_at": now().isoformat(),
            }
            self.k.add_event(
                session,
                "research.connection_feedback",
                {"connection_id": row.id, "useful": bool(useful)},
            )
            return record(row)
