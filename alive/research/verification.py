"""Independent verification for controlled research tasks.

The model's answer is checked against frozen labels and exact captured quotes. Citation existence
alone is never promoted to semantic truth for an ordinary, unlabelled owner question, and a
fabricated quote is a deterministic grounding failure rather than a successful citation.
"""

from __future__ import annotations

import re

from alive.research.contracts import ResearchAction, ResearchReference, ResearchVerification

SPACE = re.compile(r"\s+")


def _normal(text: str) -> str:
    value = SPACE.sub(" ", text.strip().lower())
    return value.rstrip(" .;:")


def _document(source_content: dict, document_id: str):
    for item in source_content.get("files", []):
        if str(item["path"]) == document_id:
            return item
    return None


def _quote_present(source_content: dict, document_id: str, quote: str) -> bool:
    item = _document(source_content, document_id)
    if item is None:
        return False
    haystack = _normal(str(item["content"]))
    needle = _normal(quote)
    return bool(needle) and needle in haystack


def _grounded(source_content: dict, citation) -> bool:
    return _quote_present(source_content, citation.document_id, citation.quote)


def _required_present(source_content: dict, action: ResearchAction, required) -> bool:
    for citation in action.citations:
        if citation.document_id != required.document_id:
            continue
        if not _grounded(source_content, citation):
            continue
        if _normal(required.quote) in _normal(citation.quote):
            return True
    return False


def verify(
    action: ResearchAction,
    *,
    source_content: dict,
    reference: ResearchReference | None,
) -> ResearchVerification:
    if action.action == "abstain":
        if reference is None:
            return ResearchVerification(
                status="ABSTAINED",
                basis="model_abstained",
                notes=[
                    "No independent reference was supplied; abstention is retained as a decision."
                ],
            )
        return ResearchVerification(
            status="ABSTAINED",
            basis="model_abstained_on_labelled_task",
            reference_id=reference.reference_id,
            matched_answer=False,
            notes=["The task had an independent reference answer."],
        )
    if action.action != "answer":
        return ResearchVerification(
            status="INCONCLUSIVE",
            basis="non_terminal_action",
            reference_id=reference.reference_id if reference else None,
        )

    grounded = sum(1 for citation in action.citations if _grounded(source_content, citation))
    ungrounded = len(action.citations) - grounded
    if reference is None:
        if ungrounded:
            return ResearchVerification(
                status="VERIFIED_FAILURE",
                basis="citations_not_grounded",
                citations_present=grounded,
                grounded=False,
                notes=[
                    "At least one cited quote was not found verbatim in the approved document. "
                    "Semantic correctness was not independently established."
                ],
            )
        return ResearchVerification(
            status="INCONCLUSIVE",
            basis="citations_present_semantics_unverified",
            citations_present=grounded,
            grounded=bool(action.citations),
            notes=[
                "No independent reference was supplied; the answer is retained with grounded "
                "citations, but semantic correctness is not established."
            ],
        )

    accepted = {_normal(reference.expected_answer)} | {
        _normal(value) for value in reference.accepted_answers
    }
    matched = _normal(action.answer) in accepted
    required = reference.required_citations
    required_present = sum(
        1 for citation in required if _required_present(source_content, action, citation)
    )
    required_ok = required_present == len(required)
    if matched and required_ok and not ungrounded:
        return ResearchVerification(
            status="VERIFIED_SUCCESS",
            basis="independent_reference_and_required_quotes",
            reference_id=reference.reference_id,
            matched_answer=True,
            citations_present=grounded,
            citations_required=len(required),
            required_present=required_present,
            grounded=True,
        )
    notes = []
    if not matched:
        notes.append("Answer did not match the frozen reference answer set.")
    if not required_ok:
        notes.append("The model citation list omitted one or more required exact quotes.")
    if ungrounded:
        notes.append("At least one cited quote was not found verbatim in the cited document.")
    return ResearchVerification(
        status="VERIFIED_FAILURE",
        basis="independent_reference_mismatch",
        reference_id=reference.reference_id,
        matched_answer=matched,
        citations_present=grounded,
        citations_required=len(required),
        required_present=required_present,
        grounded=ungrounded == 0 and bool(action.citations),
        notes=notes,
    )


__all__ = ["verify"]
