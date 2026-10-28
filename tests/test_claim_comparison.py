"""Deterministic C1 contract checks; no provider calls."""

from alive.claim_comparison import ClaimComparisonOutput, validate_claim

H = "The interface is recommended for all clients."
C = "The interface is deprecated in version 3.12."
P = {"historical_excerpt": H, "current_excerpt": C}


def example(**changes):
    values = {
        "relationship": "explicit_supersession",
        "claim_aspect": "status",
        "historical_claim_quote": H,
        "current_claim_quote": C,
        "scope_alignment": "same",
        "scope_note": "Same interface, later release",
        "supersession_basis_quote": C,
        "reason": "New documentation states deprecation.",
        "limitations": "No factual truth assessment.",
        "confidence": 0.5,
    }
    values.update(changes)
    return ClaimComparisonOutput(**values)


def test_explicit_source_deprecation_can_pass():
    result = validate_claim(example(), P)
    assert (result["decision"], result["relationship"]) == ("accepted", "explicit_supersession")


def test_recency_without_explicit_basis_abstains():
    result = validate_claim(example(supersession_basis_quote=None), P)
    assert result["decision"] == "demoted"
    assert result["relationship"] == "insufficient_evidence"


def test_invented_quote_is_rejected():
    assert (
        validate_claim(example(current_claim_quote="Not in source."), P)["decision"] == "rejected"
    )


def test_conflict_requires_same_scope():
    result = validate_claim(example(relationship="conflicts", scope_alignment="different"), P)
    assert result["decision"] == "demoted"


def test_reliance_anchor_must_overlap_historical_quote():
    result = validate_claim(example(), P | {"reliance_anchor": "unrelated"})
    assert result["decision"] == "demoted"


def test_truncated_quote_cannot_drop_negation():
    historical = "It is not true that caching improves recall."
    current = "Caching improves recall."
    payload = {"historical_excerpt": historical, "current_excerpt": current}
    item = example(
        relationship="supports",
        historical_claim_quote="caching improves recall.",
        current_claim_quote=current,
    )
    assert validate_claim(item, payload)["decision"] == "rejected"


def test_overconfident_abstention_rejected():
    item = example(relationship="insufficient_evidence", confidence=0.9)
    assert validate_claim(item, P)["decision"] == "rejected"


def test_extra_schema_fields_disallowed():
    import pytest
    from pydantic import ValidationError

    with pytest.raises(ValidationError):
        ClaimComparisonOutput(**(example().model_dump() | {"secret": "unexpected"}))
