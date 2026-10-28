"""Realistic space-joined text and wrong-subject regression gates for v2.

These assertions exercise the precise failure modes found by the independent review.
They use local source strings and invoke no inference provider.
"""
from alive.claim_comparison import (
    ClaimComparisonOutput, _bounded_sentence, validate_claim,
)


def candidate(h, c, relationship="explicit_supersession", aspect="status", basis=None):
    return ClaimComparisonOutput(
        relationship=relationship, claim_aspect=aspect,
        historical_claim_quote=h, current_claim_quote=c,
        scope_alignment="same", scope_note="same API",
        supersession_basis_quote=basis if basis is not None else c,
        reason="A source-stated API status change.",
        limitations="Source interpretation has not been independently fact-checked.",
        confidence=0.4,
    )


def test_mid_excerpts_space_joined_boundary():
    text = "First sentence here. Second sentence is fine."
    assert _bounded_sentence(text, "Second sentence is fine.")


def test_year_sentence_and_abbreviation_token():
    assert _bounded_sentence("Released in 2024. The API changed.", "The API changed.")
    assert _bounded_sentence("It plays piano. The model is slow.", "The model is slow.")
    assert not _bounded_sentence("It is not true, i.e. Caching improves recall.",
                                 "Caching improves recall.")


def test_utcnow_superset_with_following_method_deprecation():
    behaviour = "Return the current UTC date and time, with tzinfo None."
    rest = " This is like now(), but returns the current UTC date and time."
    basis = "Deprecated since version 3.12: Use datetime.now() with UTC instead."
    next_method = " classmethod datetime.utcfromtimestamp (timestamp) Return UTC time."
    second_basis = "Deprecated since version 3.12: Use datetime.fromtimestamp() instead."
    old = "Intro text. " + behaviour + rest
    new = old + " " + basis + next_method + " " + second_basis
    reliance = {"quote": behaviour, "start": old.index(behaviour),
                "end": old.index(behaviour) + len(behaviour)}
    valid = validate_claim(candidate(behaviour, basis),
                           {"historical_excerpt": old, "current_excerpt": new,
                            "reliance": reliance})
    assert valid["decision"] == "accepted", valid
    assert valid["historical_quote_retained_in_current"] is True
    wrong = validate_claim(candidate(behaviour, second_basis),
                           {"historical_excerpt": old, "current_excerpt": new,
                            "reliance": reliance})
    assert wrong["decision"] == "demoted", wrong


def test_next_entry_is_only_deprecated_entry():
    behaviour = "Return the current UTC date and time, with tzinfo None."
    rest = " This is like now(), but returns the current UTC date and time."
    next_method = " classmethod datetime.utcfromtimestamp (timestamp) Return UTC time."
    basis = "Deprecated since version 3.12: Use datetime.fromtimestamp() instead."
    current = behaviour + rest + next_method + " " + basis
    result = validate_claim(candidate(behaviour, basis),
                            {"historical_excerpt": behaviour + rest,
                             "current_excerpt": current})
    assert result["decision"] == "demoted", result
    assert "another_subject_between_anchor_and_basis" in result["reasons"]


def test_partial_version_number_is_not_complete_sentence():
    c = "The interface is deprecated in version 3.12. It remains available."
    h = "The interface is recommended."
    partial = "The interface is deprecated in version 3."
    result = validate_claim(candidate(h, partial, basis=partial),
                            {"historical_excerpt": h, "current_excerpt": c})
    assert result["decision"] != "accepted", result
