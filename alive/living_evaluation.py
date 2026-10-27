"""Keep supported facts, conclusion decisions and task resolution distinct."""

from alive.living_policy import numeric_equal


def assess(output, sources, measured):
    supported = (
        bool(sources)
        and len(output.claims) == 1
        and output.claims[0].subject == "Aster"
        and output.claims[0].predicate == "endurance_hours"
        and numeric_equal(output.claims[0].value, measured)
        and output.claims[0].evidence_refs == [sources[0]["id"]]
    )
    abstained = not sources and not output.claims and output.recommendation == "abstain"
    resolved = supported and output.recommendation == "proceed"
    return {
        "resolved": bool(resolved),
        "safe_abstention": abstained,
        "factual_correct": bool(supported) if output.claims else None,
        "conclusion_contract_correct": bool(resolved or abstained),
    }
