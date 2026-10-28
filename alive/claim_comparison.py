"""ALIVE-DEMO-01 C1: constrained, deterministic claim-comparison contract.

A model's relationship label is a hypothesis. This validator only verifies exact
evidence provenance and conservative demotion rules; it cannot verify semantic truth.
No provider dispatch, new permissions, or experiment integration in this module.
"""
from __future__ import annotations

import re
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

CLAIM_VERSION = "alive-demo01-claim-v1"
MARKER = re.compile(
    r"\b(deprecat(?:ed|ion)|supersed(?:ed|es)|replaced by|no longer recommended|"
    r"removed in|errat(?:um|a)|correction|retract(?:ed|ion))\b", re.I
)
NEGATOR = re.compile(r"\b(?:not|no|never|without)\b|n't\b", re.I)
ASSERTIVE = re.compile(r"\b(?:proves?|confirmed?|definitely|certainly|verified)\b", re.I)
BOUNDARY = re.compile(r"(?:^|(?<=[.!?:])\s+|\n)")


class ClaimComparisonOutput(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    relationship: Literal[
        "supports", "conflicts", "qualifies", "explicit_supersession",
        "unrelated", "insufficient_evidence"
    ]
    claim_aspect: Literal["behaviour", "recommendation", "status", "measurement", "other"]
    historical_claim_quote: str | None = Field(default=None, max_length=300)
    current_claim_quote: str | None = Field(default=None, max_length=300)
    scope_alignment: Literal["same", "different", "unclear"]
    scope_note: str = Field(max_length=300)
    supersession_basis_quote: str | None = Field(default=None, max_length=300)
    reason: str = Field(max_length=600)
    limitations: str = Field(max_length=400)
    confidence: float = Field(ge=0, le=1)


def _bounded_sentence(excerpt: str, quote: str) -> bool:
    """An exact quote cannot start/end in the middle of a source sentence."""
    start = excerpt.find(quote)
    if start < 0:
        return False
    # A boundary can be excerpt start, a newline, or punctuation followed by whitespace.
    pre = excerpt[:start]
    at_start = not pre or pre.endswith("\n") or bool(re.search(r"[.!?:]\s+$", pre))
    suffix = excerpt[start + len(quote):]
    at_end = (not suffix or quote.rstrip().endswith((".", "!", "?"))
              or suffix.startswith("\n"))
    return at_start and at_end


def validate_claim(output: ClaimComparisonOutput, payload: dict) -> dict:
    """Return accept/demote/reject with evidence reasons; default fail-closed."""
    historical = payload.get("historical_excerpt", "")
    current = payload.get("current_excerpt", "")
    h = output.historical_claim_quote or ""
    c = output.current_claim_quote or ""
    errors = []
    if not h or h not in historical or not c or c not in current:
        errors.append("missing_or_nonexact_source_quote")
    if h and h in current or c and c in historical:
        errors.append("cross_source_ambiguous_quote")
    if h and not _bounded_sentence(historical, h):
        errors.append("historical_quote_not_sentence_bounded")
    if c and not _bounded_sentence(current, c):
        errors.append("current_quote_not_sentence_bounded")
    if output.relationship == "supports" and bool(NEGATOR.search(h)) != bool(NEGATOR.search(c)):
        errors.append("asymmetric_negation")
    if output.relationship in ("unrelated", "insufficient_evidence"):
        if output.confidence > 0.2 or ASSERTIVE.search(output.reason):
            errors.append("assertive_or_overconfident_abstention")
    if errors:
        return {"valid": False, "relationship": "insufficient_evidence",
                "decision": "rejected", "reasons": errors, "version": CLAIM_VERSION}
    demotions = []
    anchor = payload.get("reliance_anchor")
    if anchor:
        if not isinstance(anchor, str) or anchor not in historical or not (
            h in anchor or anchor in h
        ):
            demotions.append("historical_quote_misses_reliance_anchor")
    if output.relationship == "conflicts" and output.scope_alignment != "same":
        demotions.append("conflict_scope_not_aligned")
    if output.relationship == "explicit_supersession":
        basis = output.supersession_basis_quote
        if (not basis or basis not in current or
                not _bounded_sentence(current, basis) or not MARKER.search(basis)):
            demotions.append("no_explicit_source_supersession_basis")
    if demotions:
        return {"valid": True, "relationship": "insufficient_evidence",
                "decision": "demoted", "reasons": demotions, "version": CLAIM_VERSION}
    return {"valid": True, "relationship": output.relationship,
            "decision": "accepted", "reasons": [], "version": CLAIM_VERSION}
