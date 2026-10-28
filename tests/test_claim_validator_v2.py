"""Regression cases for conservative claim-validator v2. No network calls."""
from alive.claim_comparison import ClaimComparisonOutput, validate_claim, _bounded_sentence


def output(h, c, **updates):
    fields = dict(relationship="explicit_supersession", claim_aspect="status",
                  historical_claim_quote=h, current_claim_quote=c,
                  scope_alignment="same", scope_note="same method",
                  supersession_basis_quote=c, reason="Source marks status change.",
                  limitations="Model interpretation, not independently verified.",
                  confidence=0.3)
    fields.update(updates)
    return ClaimComparisonOutput(**fields)


def test_earlier_passage_repeated_in_new_source_allowed():
    h = "Return the current UTC date and time, with tzinfo None."
    c = "Deprecated since version 3.12: Use datetime.now() with UTC instead."
    current = h + "\n" + c
    result = validate_claim(output(h, c), {"historical_excerpt": h, "current_excerpt": current})
    assert result["decision"] == "accepted", result
    assert result["historical_quote_retained_in_current"] is True


def test_negated_deprecation_not_a_supersession():
    h, c = "Use this method as documented.", "This method is not deprecated."
    result = validate_claim(output(h, c), {"historical_excerpt": h, "current_excerpt": c})
    assert result["decision"] != "accepted"


def test_not_the_same_as_recommended_behavior():
    h, c = "The method returns UTC time.", "The method is deprecated since 3.12."
    result = validate_claim(output(h, c, claim_aspect="behaviour"),
                            {"historical_excerpt": h, "current_excerpt": c})
    assert result["decision"] != "accepted"


def test_cannot_negation_suppresses_support():
    h, c = "The parser cannot stream input.", "The parser streams input."
    result = validate_claim(output(h, c, relationship="supports",
                                   supersession_basis_quote=None),
                            {"historical_excerpt": h, "current_excerpt": c})
    assert result["decision"] == "rejected"


def test_duplicate_without_offset_rejected():
    h = "Caching improves recall."
    historical = h + "\n" + h
    c = "Caching improves recall in v2."
    result = validate_claim(output(h, c, relationship="supports",
                                   supersession_basis_quote=None),
                            {"historical_excerpt": historical, "current_excerpt": c})
    assert result["decision"] == "rejected"


def test_anchoring_honors_selected_occurrence():
    quote = "A complete sentence here."
    excerpt = quote + "\n" + quote
    assert not _bounded_sentence(excerpt, quote)
    assert _bounded_sentence(excerpt, quote, occurrence_start=len(quote) + 1)


def test_unsupported_unverified_claim_abstains():
    h, c = "The interface remains supported.", "The interface is deprecated in v3."
    result = validate_claim(output(h, c, supersession_basis_quote=None),
                            {"historical_excerpt": h, "current_excerpt": c})
    assert result["relationship"] == "insufficient_evidence"
