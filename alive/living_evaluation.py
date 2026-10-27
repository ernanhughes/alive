"""Keep facts, feedback corroboration, conclusion decisions and resolution distinct."""

from alive.living_policy import numeric_equal


def assess(output, sources, measured):
    source_value = sources[0]["value"] if sources else None
    claim = output.claims[0] if len(output.claims) == 1 else None
    supported = bool(
        sources
        and claim
        and claim.subject == "Aster"
        and claim.predicate == "endurance_hours"
        and numeric_equal(claim.value, source_value)
        and claim.evidence_refs == [sources[0]["id"]]
    )
    abstained = not sources and not output.claims and output.recommendation == "abstain"
    feedback_confirms_source = bool(sources) and numeric_equal(source_value, measured)
    resolved = supported and output.recommendation == "proceed" and feedback_confirms_source
    return {
        "resolved": bool(resolved),
        "safe_abstention": abstained,
        "factual_correct": bool(supported) if output.claims else None,
        "conclusion_contract_correct": bool(resolved or abstained),
        "source_value": source_value,
        "feedback_confirms_source": bool(feedback_confirms_source),
    }
