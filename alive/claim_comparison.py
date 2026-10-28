"""Conservative claim-comparison validator v2.

Verifies exact source provenance and structural requirements, never semantic truth.
No network or model access.
"""

from __future__ import annotations

import re
import unicodedata
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

CLAIM_VERSION = "alive-demo01-claim-v2"
NEGATOR = re.compile(r"\b(?:not|no|never|without|cannot|neither|nor|none|nothing)\b|n't\b", re.I)
QUALIFIER = re.compile(r"\b(?:only|unless|except)\b", re.I)
ASSERTIVE = re.compile(r"\b(?:proves?|confirmed?|definitely|certainly|verified)\b", re.I)
SUPERSESSION = re.compile(
    r"\b(?:deprecated since|deprecated in|is deprecated|superseded by|replaced by|"
    r"no longer recommended|removed in|erratum|retracted)\b|\bcorrection:",
    re.I,
)
SIGNATURE = re.compile(
    r"\b(?:classmethod|staticmethod|class|method|function|attribute|property|exception)\s+[A-Za-z_][\w.]*",
)
ABBREVIATIONS = ("e.g.", "i.e.", "etc.", "vs.", "cf.", "fig.", "no.", "dr.", "mr.", "ms.")


class ClaimComparisonOutput(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    relationship: Literal[
        "supports",
        "conflicts",
        "qualifies",
        "explicit_supersession",
        "unrelated",
        "insufficient_evidence",
    ]
    claim_aspect: Literal["behaviour", "recommendation", "status", "measurement", "other"]
    historical_claim_quote: str | None = Field(default=None, max_length=300)
    current_claim_quote: str | None = Field(default=None, max_length=300)
    historical_quote_start: int | None = Field(default=None, ge=0)
    current_quote_start: int | None = Field(default=None, ge=0)
    scope_alignment: Literal["same", "different", "unclear"]
    scope_note: str = Field(min_length=1, max_length=300)
    supersession_basis_quote: str | None = Field(default=None, max_length=300)
    reason: str = Field(min_length=1, max_length=600)
    limitations: str = Field(min_length=1, max_length=400)
    confidence: float = Field(ge=0, le=1)


def _occurrences(source: str, quote: str) -> list[int]:
    if not quote:
        return []
    offsets = []
    cursor = 0
    while True:
        found = source.find(quote, cursor)
        if found < 0:
            return offsets
        offsets.append(found)
        cursor = found + 1


def _span(source: str, quote: str, requested: int | None = None) -> tuple[int, int] | None:
    offsets = _occurrences(source, quote)
    if not offsets or (requested is None and len(offsets) != 1):
        return None
    start = offsets[0] if requested is None else requested
    if start not in offsets:
        return None
    return start, start + len(quote)


def _boundary(source: str, start: int, end: int) -> bool:
    if start < 0 or end > len(source) or end <= start:
        return False
    before = source[:start]
    if start == 0 or source[start - 1] == "\n":
        start_ok = True
    else:
        match = re.search(r"[.!?]\s+$", before)
        tokens = before.rstrip().lower().split()
        start_ok = bool(match) and not (tokens and tokens[-1] in ABBREVIATIONS)
        if match and re.search(r"\d\.$", before.rstrip()) and source[start].isdigit():
            start_ok = False
    if end == len(source) or source[end] == "\n":
        end_ok = True
    else:
        end_ok = bool(re.search(r"[.!?]$", source[start:end])) and source[end].isspace()
        if end_ok and re.search(r"\d\.$", source[start:end]) and source[end].isdigit():
            end_ok = False
    return start_ok and end_ok


def _bounded_sentence(excerpt: str, quote: str, occurrence_start: int | None = None) -> bool:
    """Compatibility helper for the anchor endpoint; honors chosen occurrence."""
    span = _span(excerpt, quote, occurrence_start)
    return bool(span and _boundary(excerpt, *span))


def _result(decision: str, label: str, reasons: list[str], retained: bool) -> dict:
    return {
        "valid": decision != "rejected",
        "decision": decision,
        "relationship": label,
        "reasons": reasons,
        "version": CLAIM_VERSION,
        "historical_quote_retained_in_current": retained,
    }


def validate_claim(output: ClaimComparisonOutput, payload: dict) -> dict:
    historical = str(payload.get("historical_excerpt") or "")[:2000]
    current = str(payload.get("current_excerpt") or "")[:3000]
    h = output.historical_claim_quote or ""
    c = output.current_claim_quote or ""
    retained = bool(h and h in current)
    errors: list[str] = []
    hspan = _span(historical, h, output.historical_quote_start)
    cspan = _span(current, c, output.current_quote_start)
    if not hspan or not _boundary(historical, *hspan):
        errors.append("historical_quote_not_exact_unique_and_bounded")
    if not cspan or not _boundary(current, *cspan):
        errors.append("current_quote_not_exact_unique_and_bounded")
    for q in (h, c, output.supersession_basis_quote or ""):
        if any(unicodedata.category(ch) in ("Cc", "Cf") for ch in q):
            errors.append("quote_contains_control_or_format_character")
            break
    if h == c and output.relationship != "supports":
        errors.append("identical_quotes_cannot_establish_change")
    if output.relationship == "supports":
        if bool(NEGATOR.search(h)) != bool(NEGATOR.search(c)) or bool(QUALIFIER.search(h)) != bool(
            QUALIFIER.search(c)
        ):
            errors.append("asymmetric_negation_or_qualification")
    if ASSERTIVE.search(output.reason):
        errors.append("assertive_reason")
    if output.relationship in ("unrelated", "insufficient_evidence") and output.confidence > 0.2:
        errors.append("overconfident_abstention")
    if errors:
        return _result("rejected", "insufficient_evidence", errors, retained)

    demotions: list[str] = []
    anchor = payload.get("reliance") or payload.get("reliance_anchor")
    if anchor:
        if not isinstance(anchor, dict):
            demotions.append("invalid_anchor_contract")
        else:
            start, end, quote = anchor.get("start"), anchor.get("end"), anchor.get("quote")
            if (
                not isinstance(start, int)
                or not isinstance(end, int)
                or not isinstance(quote, str)
                or historical[start:end] != quote
                or not hspan
                or not (
                    hspan[0] <= start and hspan[1] >= end or start <= hspan[0] and end >= hspan[1]
                )
            ):
                demotions.append("historical_quote_misses_reliance_anchor")
    capture_v2 = (
        payload.get("current_capture_format_version") == 2
        or payload.get("historical_capture_format_version") == 2
    )
    bound_subject = None
    if capture_v2:
        from alive.demo_live_01 import identify

        for prefix, excerpt in (("historical", historical), ("current", current)):
            identity = identify(
                payload.get(prefix + "_url", ""),
                excerpt,
                payload.get(prefix + "_capture_entries", []),
                payload.get(prefix + "_capture_format_version"),
            )
            if identity is None or identity != payload.get(prefix + "_source_identity"):
                demotions.append(prefix + "_capture_source_identity_unverified")
        historical_entries = [
            entry
            for entry in payload.get("historical_capture_entries", [])
            if hspan and entry.get("start", -1) <= hspan[0] and entry.get("end", -1) >= hspan[1]
        ]
        if len(historical_entries) != 1:
            demotions.append("historical_claim_entry_not_unique")
        else:
            bound_subject = historical_entries[0].get("subject")
            current_entries = [
                entry
                for entry in payload.get("current_capture_entries", [])
                if entry.get("subject") == bound_subject
            ]
            if len(current_entries) != 1:
                demotions.append("current_claim_entry_not_unique")
            else:
                entry = current_entries[0]
                for span in (
                    cspan,
                    _span(current, output.supersession_basis_quote or "")
                    if output.relationship == "explicit_supersession"
                    else cspan,
                ):
                    if not span or not entry["start"] <= span[0] < span[1] <= entry["end"]:
                        demotions.append("current_evidence_outside_anchored_subject_entry")
                        break
    if output.relationship == "conflicts":
        if output.scope_alignment != "same" or c in historical:
            demotions.append("conflict_scope_or_novelty_unverified")
    if output.relationship == "explicit_supersession":
        basis = output.supersession_basis_quote or ""
        marker = SUPERSESSION.search(basis)
        if marker:
            named_subjects = re.findall(r"\b([A-Za-z_][\w.]*)\s*\([^)]*\)", basis[: marker.start()])
            if named_subjects and not all(subject in h for subject in named_subjects):
                demotions.append("supersession_named_subject_not_bound")
        span = _span(current, basis)
        if (
            not span
            or not _boundary(current, *span)
            or not SUPERSESSION.search(basis)
            or NEGATOR.search(basis)
            or basis in historical
            or output.claim_aspect not in ("status", "recommendation")
        ):
            demotions.append("supersession_basis_not_authoritative")
        else:
            # Compare against *all* marker-bearing sentences after the anchored subject.
            anchor_at = current.find(h) if h in current else cspan[0]
            match_positions = [
                m.start() for m in SUPERSESSION.finditer(current) if m.start() >= anchor_at
            ]
            between = current[anchor_at : span[0]]
            if SIGNATURE.search(between[len(h) if h in current else 0 :]):
                demotions.append("another_subject_between_anchor_and_basis")
            if (
                not match_positions
                or span[0] - anchor_at > 1200
                or not (span[0] <= match_positions[0] < span[1])
            ):
                demotions.append("supersession_basis_not_nearest_to_subject")
    if demotions:
        return _result("demoted", "insufficient_evidence", demotions, retained)
    result = _result("accepted", output.relationship, [], retained)
    if capture_v2:
        result |= {"subject_entry": bound_subject, "capture_binding": "pinned_source_entry_v2"}
    return result
