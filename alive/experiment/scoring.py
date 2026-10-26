"""Frozen deterministic evaluator: numeric support, abstention and explicit citations."""

import math
import statistics

from alive.cognitive_schema import RoleOutput

SCORER_VERSION = "supported-numeric-v1"


def evidence_state(payload):
    values = {key: [] for key in payload["required_fields"]}
    for source in payload["sources"]:
        if source["authority"] != "verified" or source["window"] != "same-window":
            continue
        for fact in source["facts"]:
            if fact["key"] in values:
                values[fact["key"]].append((float(fact["value"]), source["id"]))
    missing = [key for key, pairs in values.items() if not pairs]
    conflicting = [key for key, pairs in values.items() if len({value for value, _ in pairs}) > 1]
    return values, missing, conflicting


def solve(payload):
    values, missing, conflicting = evidence_state(payload)
    if missing or conflicting:
        return {
            "status": "ABSTAIN",
            "value": None,
            "reason": "missing" if missing else "conflicting",
        }
    data = {key: pairs[0][0] for key, pairs in values.items()}
    op = payload["operation"]
    if op == "sum":
        value = data["a"] + data["b"]
    elif op == "difference":
        value = data["start"] - data["remainder"]
    elif op == "minimum":
        value = min(data.values())
    elif op == "maximum":
        value = max(data.values())
    elif op == "ratio":
        value = data["numerator"] / data["denominator"]
    elif op == "median":
        value = statistics.median(data.values())
    elif op == "weighted_mean":
        value = (data["value_a"] * data["weight_a"] + data["value_b"] * data["weight_b"]) / (
            data["weight_a"] + data["weight_b"]
        )
    elif op == "count_at_least":
        value = sum(data[f"v{i}"] >= data["cutoff"] for i in range(1, 6))
    elif op == "fahrenheit":
        value = (data["temperature_f"] - 32) * 5 / 9
    elif op == "rate":
        value = data["quantity"] / data["hours"]
    else:
        raise ValueError("Unsupported scoring operation")
    return {"status": "ANSWER", "value": float(value), "reason": "verified_inputs"}


def score(payload, decision):
    output = decision if isinstance(decision, RoleOutput) else RoleOutput.model_validate(decision)
    expected = solve(payload)
    abstained = output.recommendation == "abstain" and not output.claims
    sources = {s["id"]: s for s in payload["sources"]}
    refs = [ref for claim in output.claims for ref in claim.evidence_refs]
    valid_refs = [ref for ref in refs if ref in sources]
    citation_validity = len(valid_refs) / len(refs) if refs else None
    base = {
        "correct": False,
        "abstained": abstained,
        "correct_abstention": abstained and expected["status"] == "ABSTAIN",
        "unsupported_acceptance": bool(output.claims),
        "citation_validity": citation_validity,
        "expected_status": expected["status"],
        "score_version": SCORER_VERSION,
        "reason": "unnecessary_abstention" if abstained else "invalid_answer",
    }
    if expected["status"] == "ABSTAIN":
        return base | {
            "correct": abstained,
            "unsupported_acceptance": bool(output.claims),
            "reason": "correct_abstention" if abstained else "unsupported_answer",
        }
    if abstained:
        return base
    if output.recommendation != "proceed":
        return base | {"reason": "answer_requires_proceed_recommendation"}
    if len(output.claims) != 1:
        return base | {"reason": "exactly_one_numeric_claim_required"}
    claim = output.claims[0]
    if claim.subject != payload["subject"] or claim.predicate != "computed_result":
        return base | {"reason": "claim_target_mismatch"}
    try:
        value = float(claim.value)
    except ValueError:
        return base | {"reason": "non_numeric_value"}
    if not math.isfinite(value) or not math.isclose(
        value, expected["value"], rel_tol=1e-6, abs_tol=0.01
    ):
        return base | {"reason": "wrong_value"}
    facts, _, _ = evidence_state(payload)
    supported = all(
        any(source_id in claim.evidence_refs for _, source_id in pairs) for pairs in facts.values()
    )
    correct = supported and citation_validity == 1
    return base | {
        "correct": correct,
        "unsupported_acceptance": not correct,
        "reason": "verified_numeric_with_citations" if correct else "missing_or_invalid_citations",
    }
