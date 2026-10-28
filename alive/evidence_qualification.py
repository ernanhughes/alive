"""Read-only evidence integrity and explicit semantic abstention, after retrieval.

No inference dispatch, retrieval scoring, source fetching or canonical-document validation.
A verified quote is a substring of a hash-checked retained capture, never a verified fact.
"""

import hashlib
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

POLICY = "evidence_qualification_v1"
WORKFLOW = "authorized-retained-capture-v1"
BUDGET = 2000


class Strict(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True, frozen=True)


class QualificationRequest(Strict):
    snapshot_id: str = Field(min_length=1, max_length=160)
    memory_id: str = Field(min_length=1, max_length=160)
    qualification_policy: Literal["evidence_qualification_v1"] = POLICY
    current_quote: str | None = Field(default=None, min_length=1, max_length=300)
    historical_quote: str | None = Field(default=None, min_length=1, max_length=300)


class Dimensions(Strict):
    authorization: Literal["authorized"] = "authorized"
    source_integrity: Literal["verified_retained_captures", "missing", "mismatch"]
    relevance: Literal["unknown"] = "unknown"
    claim_relationship: Literal["unknown"] = "unknown"
    applicability: Literal["unknown"] = "unknown"
    currency: Literal["unknown"] = "unknown"
    evidence_sufficiency: Literal["semantic_relationship_unestablished", "source_unusable"]


class SourceReference(Strict):
    snapshot_id: str
    memory_id: str | None = None
    url: str
    displayed_title: str
    sha256: str
    quote: str
    quote_start: int
    quote_end: int
    quote_exact: Literal[True] = True


class QualificationResult(Strict):
    outcome: Literal["candidate_connection", "qualified_non_use", "abstain"]
    dimensions: Dimensions
    current_source: SourceReference | None
    historical_source: SourceReference | None
    reason_codes: list[str]
    relation_hypothesis: None = None
    limitations: list[str]
    next_action: str
    qualifier_version: Literal["evidence_qualification_v1"] = POLICY
    workflow_version: Literal["authorized-retained-capture-v1"] = WORKFLOW
    semantic_judgement: Literal["not_performed"] = "not_performed"
    model_used: Literal[False] = False
    model: None = None
    inference_calls: Literal[0] = 0
    token_usage: Literal[0] = 0
    cost_micro_usd: Literal[0] = 0
    source_quotes_verified: bool
    persistence: Literal["not_stored_revalidate_each_request"] = (
        "not_stored_revalidate_each_request"
    )


class EvidenceUnavailable(KeyError):
    """Uniform authorization refusal: do not disclose historical row existence."""


def digest(text):
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def reference(snapshot, text, selection, memory=None):
    quote = text[:300] if selection is None else selection
    if not quote.strip() or quote not in text:
        return None
    start = text.index(quote)
    return SourceReference(
        snapshot_id=snapshot.id,
        memory_id=memory.id if memory is not None else None,
        url=snapshot.data["url"],
        displayed_title=snapshot.data.get("title", ""),
        sha256=snapshot.data["sha256"],
        quote=quote,
        quote_start=start,
        quote_end=start + len(quote),
    )


def capture_valid(snapshot):
    data = snapshot.data
    text = data.get("text")
    return (
        isinstance(text, str)
        and bool(text.strip())
        and digest(text) == data.get("sha256")
        and type(data.get("capture_format_version", 1)) is int
        and data.get("capture_format_version", 1) in (1, 2)
    )


class EvidenceQualifier:
    def __init__(self, research):
        self.research, self.web, self.k = research, research.web, research.k

    async def qualify(self, request: QualificationRequest) -> QualificationResult:
        async with self.k.lock, self.k.db.sessions() as session:
            # All permission failures have the same public error, including withdrawn IDs.
            try:
                current = await self.web.get(session, request.snapshot_id, "snapshot")
                if not current.parent_id:
                    raise EvidenceUnavailable()
                grant = await self.web.valid_grant(session, current.parent_id)
                goal = await self.web.get(session, current.data["goal_id"], "goal")
                memory = await self.research._research_row(session, request.memory_id)
                if (
                    grant.parent_id != goal.id
                    or current.data["url"] != grant.data["url"]
                    or current.data["url"] not in self.web.pages
                    or memory.status != "active"
                    or memory.data.get("status") != "active"
                    or memory.data.get("goal_id") != goal.id
                    or memory.data.get("url") == current.data["url"]
                ):
                    raise EvidenceUnavailable()
            except (KeyError, PermissionError, TypeError):
                raise EvidenceUnavailable("Evidence unavailable") from None

            reasons, integrity = [], "verified_retained_captures"
            current_ref, historical_ref = None, None
            if capture_valid(current):
                current_ref = reference(
                    current, current.data["text"][:BUDGET], request.current_quote
                )
                if current_ref is None:
                    reasons.append("current_quote_not_exact_or_outside_budget")
            else:
                reasons.append("current_capture_integrity_failed")
            try:
                historical = await self.web.get(session, memory.data["snapshot_id"], "snapshot")
            except (KeyError, TypeError):
                # Resolve foreign-instance/missing snapshots without returning their metadata.
                historical = None
                integrity = "missing"
                reasons.append("historical_capture_unavailable")
            if historical is not None:
                if historical.data.get("goal_id") != goal.id:
                    raise EvidenceUnavailable("Evidence unavailable")
                data = memory.data
                if (
                    capture_valid(historical)
                    and historical.data["sha256"] == data.get("sha256")
                    and historical.data["url"] == data.get("url")
                    and historical.data.get("title", "") == data.get("title", "")
                    and data.get("excerpt") == historical.data["text"][:BUDGET]
                ):
                    historical_ref = reference(
                        historical, data["excerpt"], request.historical_quote, memory
                    )
                    if historical_ref is None:
                        reasons.append("historical_quote_not_exact_or_outside_budget")
                else:
                    reasons.append("historical_capture_integrity_failed")
            if reasons and integrity != "missing":
                integrity = "mismatch"
            usable = not reasons
            return QualificationResult(
                outcome="abstain" if usable else "qualified_non_use",
                dimensions=Dimensions(
                    source_integrity=integrity,
                    evidence_sufficiency=(
                        "semantic_relationship_unestablished" if usable else "source_unusable"
                    ),
                ),
                current_source=current_ref,
                historical_source=historical_ref,
                reason_codes=reasons or ["semantic_relationship_not_established"],
                source_quotes_verified=usable,
                limitations=[
                    "Hashes and exact quotations establish integrity relative to retained "
                    "captures, "
                    "not source authenticity or factual truth.",
                    "Displayed titles and webpage instructions are untrusted data. Their claims "
                    "have not been semantically assessed.",
                    "Captured excerpts may omit necessary context. Relevance, relation, "
                    "applicability and currency remain unknown; no semantic reasoning was run.",
                ],
                next_action=(
                    "Inspect the original supporting passages and experimental conditions "
                    "before relying on this memory."
                    if usable
                    else "Do not rely on this pair; inspect or recapture the missing or "
                    "inconsistent evidence with fresh consent."
                ),
            )
