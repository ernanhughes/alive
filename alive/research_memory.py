"""Goal-scoped cross-page research memory over reviewed companion observations.

The WebExperience research row remains the authoritative record. The existing Memory and
MemoryVector tables are a rebuildable retrieval projection, not a second source of truth.
"""

import hashlib
import math
import re
from collections import Counter
from datetime import UTC, datetime

from sqlalchemy import select

from alive.cognitive_models import MemoryVector
from alive.models import Memory, now, record, uid
from alive.web_models import WebExperience

RESEARCH_KIND = "research_memory"
CONNECTION_KIND = "research_connection"
INDEX_VERSION = "alive12-research-v1"
ALIVE13_RANKING = "alive13-scoped-lexical-v1"
ALIVE14_RANKING = "alive14-bm25-v1"
BM25_K1 = 1.2
BM25_B = 0.75
MIN_RETRIEVAL_SCORE = 0.12
MIN_DISCRIMINATING_IDF = 0.3
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


def _token_counts(text):
    return Counter(term for term in TOKEN.findall((text or "").lower()) if term not in STOPWORDS)


def _tokens(text):
    return set(_token_counts(text))


def _bm25_scores(query_terms, documents):
    """Return bounded BM25-style scores for (row, term-counts) documents.

    Goal vocabulary is removed from the query before this function is called. The
    corpus is the eligible same-goal research set, so inverse document frequency is
    local and deterministic. A conservative floor keeps generic-only overlap from
    becoming a retrieval result.
    """
    if not documents or not query_terms:
        return {}
    total = len(documents)
    document_frequency = Counter()
    lengths = {}
    for row, counts in documents:
        lengths[row.id] = sum(counts.values())
        for term in counts:
            document_frequency[term] += 1
    average_length = sum(lengths.values()) / total or 1.0
    scores = {}
    for row, counts in documents:
        overlap = query_terms & set(counts)
        if not overlap:
            continue
        length = lengths[row.id]
        score = 0.0
        maximum_idf = 0.0
        for term in overlap:
            frequency = counts[term]
            inverse_frequency = math.log(
                1 + (total - document_frequency[term] + 0.5) / (document_frequency[term] + 0.5)
            )
            maximum_idf = max(maximum_idf, inverse_frequency)
            denominator = frequency + BM25_K1 * (1 - BM25_B + BM25_B * length / average_length)
            score += inverse_frequency * (frequency * (BM25_K1 + 1) / denominator)
        if score < MIN_RETRIEVAL_SCORE:
            continue
        # In a tiny corpus, IDF cannot distinguish generic vocabulary. Once there
        # are enough candidates, require at least one genuinely discriminating term.
        if total >= 3 and maximum_idf < MIN_DISCRIMINATING_IDF:
            continue
        scores[row.id] = score
    return scores


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


def _bounded_span(text, terms, limit=300):
    if not text:
        return None
    if len(text) <= limit:
        return text
    lowered = text.lower()
    positions = [lowered.find(term) for term in terms if lowered.find(term) >= 0]
    start = max(0, (min(positions) if positions else 0) - 50)
    return text[start : start + limit].strip()


def _overlap_spans(current_text, historical_text, terms):
    """Return the best pair of exact source sentences sharing displayed terms."""
    current_sentences = re.split(r"(?<=[.!?])\s+", current_text or "")
    historical_sentences = re.split(r"(?<=[.!?])\s+", historical_text or "")
    best = None
    for current_index, current_sentence in enumerate(current_sentences):
        current_terms = _tokens(current_sentence)
        for historical_index, historical_sentence in enumerate(historical_sentences):
            common = sorted(current_terms & _tokens(historical_sentence) & set(terms))
            if not common:
                continue
            candidate = (
                len(common),
                -abs(current_index - historical_index),
                -current_index,
                -historical_index,
                current_sentence,
                historical_sentence,
                common,
            )
            if best is None or candidate[:4] > best[:4]:
                best = candidate
    if best is None:
        return None, None, []
    current_span = _bounded_span(best[4], best[6])
    historical_span = _bounded_span(best[5], best[6])
    shown = sorted(_tokens(current_span) & _tokens(historical_span) & set(terms))
    return current_span, historical_span, shown


class ResearchMemory:
    MAX_RESEARCH_CANDIDATES = 5000

    def __init__(self, web, memory):
        self.web, self.memory = web, memory
        self.k = web.k
        self.outbound_inflight = set()

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
        try:
            index = await self.memory.index(limit=32)
        except Exception as exc:
            index = {
                "indexed": 0,
                "available": self.memory.embedding.available,
                "error": type(exc).__name__,
            }
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
            if research_id in self.outbound_inflight:
                raise ValueError(
                    "Cannot withdraw a research memory while outbound analysis is in progress"
                )
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
            # Invalidate derived content in the SAME transaction as withdrawal.
            # API consumers must never observe a retired source with an active
            # dependent finding. This is not a second copy of the source.
            from alive.research_relationships import (
                ATTEMPT_KIND, CONSENT_KIND, CURRENT_ANALYSIS_KIND,
                PAIRED_ANALYSIS_KIND, ResearchRelationships,
            )

            affected_consents = {
                item.id for item in await self.web.rows(session, CONSENT_KIND)
                if item.data.get("historical_memory_id") == research_id
            }
            dependent_kinds = (
                CONSENT_KIND, ATTEMPT_KIND, CONNECTION_KIND,
                CURRENT_ANALYSIS_KIND, PAIRED_ANALYSIS_KIND,
            )
            for kind in dependent_kinds:
                for dependent in await self.web.rows(session, kind):
                    if (dependent.data.get("historical_memory_id") != research_id
                            and dependent.data.get("consent_id") not in affected_consents):
                        continue
                    if kind == ATTEMPT_KIND and dependent.status == "reserved":
                        dependent.data = dependent.data | {
                            "source_revoked_during_dispatch": True
                        }
                        continue
                    if dependent.status != "invalidated":
                        dependent.data = ResearchRelationships._scrub_withdrawn_data(
                            dependent.data
                        )
                        dependent.status = "invalidated"
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

    async def repair_index(self):
        active = created = refreshed = skipped = 0
        async with self.k.lock, self.k.db.sessions.begin() as session:

            def projection_metadata(row):
                return {
                    "research_memory_id": row.id,
                    "goal_id": row.data["goal_id"],
                    "url": row.data["url"],
                    "note_id": row.parent_id,
                    "snapshot_id": row.data.get("snapshot_id"),
                    "sha256": row.data["sha256"],
                    "source_kind": row.data.get("source_kind"),
                    "index_version": INDEX_VERSION,
                    "saved_at": row.data.get("saved_at"),
                    "owner_useful": row.data.get("owner_useful"),
                }

            for row in await self.web.rows(session, RESEARCH_KIND):
                if row.status != "active":
                    skipped += 1
                    projection_id = row.data.get("memory_projection_id")
                    if projection_id:
                        projection = await session.get(Memory, projection_id)
                        if projection:
                            for vector in (
                                await session.scalars(
                                    select(MemoryVector).where(
                                        MemoryVector.memory_id == projection_id
                                    )
                                )
                            ).all():
                                await session.delete(vector)
                            await session.delete(projection)
                    continue
                active += 1
                projection_id = row.data.get("memory_projection_id") or _projection_id(
                    self.k.instance_id, row.parent_id
                )
                projection = await session.get(Memory, projection_id)
                metadata = projection_metadata(row)
                if not projection:
                    projection = Memory(
                        id=projection_id,
                        instance_id=self.k.instance_id,
                        content=row.data["excerpt"],
                        memory_type="research_memory",
                        source_event_id=None,
                        importance=0.5,
                        confidence=1.0,
                        metadata_json=metadata,
                    )
                    session.add(projection)
                    created += 1
                elif (
                    projection.content != row.data["excerpt"]
                    or (projection.metadata_json or {}).get("index_version") != INDEX_VERSION
                    or (projection.metadata_json or {}).get("research_memory_id") != row.id
                ):
                    projection.content = row.data["excerpt"]
                    projection.metadata_json = metadata
                    projection.updated_at = now()
                    for vector in (
                        await session.scalars(
                            select(MemoryVector).where(MemoryVector.memory_id == projection_id)
                        )
                    ).all():
                        await session.delete(vector)
                    refreshed += 1
                row.data = row.data | {"memory_projection_id": projection_id}
            await session.flush()
        try:
            index = await self.memory.index(limit=64)
        except Exception as exc:
            index = {
                "indexed": 0,
                "available": self.memory.embedding.available,
                "error": type(exc).__name__,
            }
        return {
            "active": active,
            "projection_created": created,
            "projection_refreshed": refreshed,
            "withdrawn_skipped": skipped,
            "index": index | {"available": self.memory.embedding.available},
            "index_version": INDEX_VERSION,
        }

    async def _eligible_research_rows(self, session, goal_id):
        """Load a bounded set already scoped by instance, kind, status and goal.

        The bound is applied after eligibility filtering. A single goal with more than
        MAX_RESEARCH_CANDIDATES active rows is outside the personal-memory envelope; the
        newest rows are retained and the cap is reported to callers.
        """
        statement = (
            select(WebExperience)
            .where(
                WebExperience.instance_id == self.k.instance_id,
                WebExperience.kind == RESEARCH_KIND,
                WebExperience.status == "active",
                WebExperience.data["goal_id"].as_string() == goal_id,
            )
            .order_by(WebExperience.created_at.desc())
            .limit(self.MAX_RESEARCH_CANDIDATES)
        )
        return (await session.scalars(statement)).all()

    async def retrieve(self, snapshot_id, top_k=3, mode="hybrid", ranker=ALIVE14_RANKING):
        if not 1 <= top_k <= 5:
            raise ValueError("top_k must be 1-5")
        if ranker not in (ALIVE13_RANKING, ALIVE14_RANKING):
            raise ValueError("Unknown research ranker")
        async with self.k.db.sessions() as session:
            snapshot = await self.web.get(session, snapshot_id, "snapshot")
            goal = await self.web.get(session, snapshot.data["goal_id"], "goal")
            goal_id = goal.id
            current_url = snapshot.data["url"]
            current_sha = snapshot.data["sha256"]
            current_terms = _tokens(snapshot.data["text"])
            goal_terms = _tokens(goal.data["instruction"])
            scoped_rows = await self._eligible_research_rows(session, goal_id)
            scoped = [
                row
                for row in scoped_rows
                if row.data.get("url") != current_url and row.data.get("sha256") != current_sha
            ]
            if ranker == ALIVE13_RANKING:
                candidates = []
                for row in scoped:
                    historical_terms = _tokens(row.data.get("excerpt"))
                    overlap = current_terms & historical_terms
                    if not overlap:
                        continue
                    goal_overlap = goal_terms & historical_terms
                    score = 2 * len(overlap) + len(goal_overlap - overlap)
                    candidates.append((score, row, sorted(overlap)[:12], sorted(goal_overlap)[:12]))
                candidate_count = len(candidates)
            else:
                query_terms = current_terms - goal_terms
                documents = [(row, _token_counts(row.data.get("excerpt"))) for row in scoped]
                scores = _bm25_scores(query_terms, documents)
                candidates = []
                candidate_count = 0
                for row, counts in documents:
                    overlap = query_terms & set(counts)
                    if not overlap:
                        continue
                    candidate_count += 1
                    if row.id not in scores:
                        continue
                    candidates.append(
                        (
                            scores[row.id],
                            row,
                            sorted(overlap)[:12],
                            sorted(goal_terms & set(counts))[:12],
                        )
                    )
            qualified_count = len(candidates)
            candidates.sort(
                key=lambda item: (
                    -item[0],
                    _age_days(item[1].data.get("reviewed_at") or "")
                    if _age_days(item[1].data.get("reviewed_at") or "") is not None
                    else 10**9,
                    item[1].id,
                )
            )
            # The cap is applied after goal/active/source eligibility filtering. It is a
            # safety bound for local personal memory, not an unscoped SQL LIMIT.
            candidates = candidates[: self.MAX_RESEARCH_CANDIDATES]
            results, seen = [], set()
            for score, row, overlap, goal_overlap in candidates:
                if row.data.get("sha256") in seen:
                    continue
                seen.add(row.data.get("sha256"))
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
                        "owner_useful": await self._latest_feedback(session, row.parent_id),
                        "retrieval_score": round(score, 6),
                        "retrieval_method": (
                            "scoped_bm25_v1" if ranker == ALIVE14_RANKING else "scoped_lexical_v1"
                        ),
                        "ranking_version": ranker,
                        "matched_terms": overlap,
                        "goal_terms": goal_overlap,
                        "same_source": False,
                        "sha256": row.data["sha256"],
                        "source_kind": row.data.get("source_kind"),
                        "status": row.status,
                        "rank": len(results) + 1,
                    }
                )
                if len(results) >= top_k:
                    break
        return {
            "current_snapshot_id": snapshot_id,
            "current_url": current_url,
            "goal_id": goal_id,
            "mode": "scoped_bm25_v1" if ranker == ALIVE14_RANKING else "scoped_lexical_v1",
            "requested_mode": mode,
            "embedding": None,
            "ranking_version": ranker,
            "scoped_count": len(scoped),
            "candidate_count": candidate_count,
            "qualified_count": qualified_count,
            "minimum_score": MIN_RETRIEVAL_SCORE if ranker == ALIVE14_RANKING else None,
            "candidate_limit": self.MAX_RESEARCH_CANDIDATES,
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
            await self.web.valid_grant(session, snapshot.parent_id)
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
            goal_terms = _tokens(goal.data["instruction"])
            overlap = sorted((_tokens(current_text) & _tokens(historical_text)) - goal_terms)
            model_quote = memory.data.get("evidence_quote")
            current_quote, historical_quote, shown_terms = _overlap_spans(
                current_text, historical_text, overlap
            )
            if len(shown_terms) >= 2 and current_quote and historical_quote:
                relation = "topic_overlap_candidate"
                status = "candidate"
                explanation = (
                    "The displayed source spans share lexical content terms "
                    + ", ".join(shown_terms[:6])
                    + ". This is a topic-overlap candidate only; it does not establish agreement, "
                    "support, contradiction or corroboration."
                )
            elif len(shown_terms) == 1 and current_quote and historical_quote:
                relation = "weak_lexical_overlap"
                status = "candidate"
                explanation = (
                    f"The displayed source spans share only the term '{shown_terms[0]}'. "
                    "This is a weak lexical overlap and requires owner review; it does not "
                    "establish a useful relation."
                )
            else:
                relation = "insufficient_evidence"
                status = "insufficient_evidence"
                explanation = (
                    "No inspectable shared evidence supports a research connection between these "
                    "two reviewed sources after goal vocabulary is excluded."
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
                    "model_evidence_quote": model_quote,
                    "shared_terms": shown_terms,
                    "goal_terms_excluded": sorted(goal_terms),
                    "relation_type": relation,
                    "explanation": explanation,
                    "status": status,
                    "evidence_policy": (
                        "displayed exact source spans; shared terms are limited to those spans; "
                        "shared words do not establish agreement"
                    ),
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

    async def connection_feedback(self, connection_id, feedback, rater_type="owner"):
        if isinstance(feedback, bool):
            feedback = {"useful": feedback}
        async with self.k.lock, self.k.db.sessions.begin() as session:
            row = await self.web.get(session, connection_id, CONNECTION_KIND)
            history = list(row.data.get("feedback_history", []))
            revision = len(history) + 1
            entry = {
                "revision": revision,
                "feedback": feedback,
                "at": now().isoformat(),
            }
            history.append(entry)
            useful = feedback.get("useful")
            if useful is None:
                if feedback.get("misleading") == "yes" or feedback.get("relevant_to_goal") == "no":
                    useful = False
                elif (
                    feedback.get("relevant_to_goal") == "yes"
                    and feedback.get("misleading") != "yes"
                ):
                    useful = True
            row.data = row.data | {
                "owner_useful": useful,
                "feedback": feedback,
                "feedback_revision": revision,
                "feedback_history": history[-20:],
                "feedback_at": entry["at"],
                "rater_type": rater_type,
                "rating_id": uid(),
                "rubric_version": "alive14r1-rubric-v1",
            }
            self.k.add_event(
                session,
                "research.connection_feedback",
                {
                    "connection_id": row.id,
                    "revision": revision,
                    "useful": useful,
                    "feedback": feedback,
                    "rater_type": rater_type,
                },
            )
            return record(row)
