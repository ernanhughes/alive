"""Policies cannot access Task labels, identifiers, categories or scoring outcomes."""

from typing import Protocol

from alive.cognitive_schema import RoleOutput
from alive.experiment.schema import Features, PolicyChoice

POLICY_VERSION = "cognitive-economy-v1"
WEIGHTS = {
    "uncertainty": 0.30,
    "contradiction": 0.30,
    "evidence_gap": 0.20,
    "weak_evidence": 0.10,
    "action_risk": 0.10,
}


def features(payload, initial: RoleOutput, estimated_tokens):
    fields = payload["required_fields"]
    values = {key: set() for key in fields}
    for source in payload["sources"]:
        if source["authority"] == "verified":
            for fact in source["facts"]:
                if fact["key"] in values:
                    values[fact["key"]].add(float(fact["value"]))
    return Features(
        uncertainty=1 - initial.confidence,
        contradiction=sum(len(v) > 1 for v in values.values()) / max(1, len(fields)),
        evidence_gap=sum(not v for v in values.values()) / max(1, len(fields)),
        weak_evidence=sum(s["authority"] != "verified" for s in payload["sources"])
        / max(1, len(payload["sources"])),
        action_risk=payload["action_risk"],
        estimated_tokens=estimated_tokens,
    )


class CriticPolicy(Protocol):
    def choose(self, state: Features) -> PolicyChoice: ...


class AlwaysCritic:
    def choose(self, state):
        return PolicyChoice(
            policy="always",
            invoke=True,
            score=1,
            threshold=0,
            reason="Fixed review policy",
            features=state,
        )


class NeverCritic:
    def choose(self, state):
        return PolicyChoice(
            policy="never",
            invoke=False,
            score=0,
            threshold=1,
            reason="Fixed no-review policy",
            features=state,
        )


class SelectiveCritic:
    def __init__(self, threshold, cost_weight=0.03):
        if not 0 <= threshold <= 1.1:
            raise ValueError("Invalid selection threshold")
        self.threshold, self.cost_weight = threshold, cost_weight

    def choose(self, state):
        value = sum(WEIGHTS[key] * getattr(state, key) for key in WEIGHTS)
        cost = self.cost_weight * min(1, state.estimated_tokens / 3000)
        bid = value - cost
        return PolicyChoice(
            policy="selective",
            invoke=bid >= self.threshold,
            score=bid,
            threshold=self.threshold,
            reason=f"General signal value {value:.4f} minus anticipated cost {cost:.4f}",
            features=state,
        )


def calibrate(records):
    """Choose one threshold using actual development paired outcomes, never evaluation data."""
    if not records or any(r["split"] != "calibration" for r in records):
        raise ValueError("Only nonempty development calibration records are allowed")
    options = []
    for threshold in [0, 0.1, 0.2, 0.3, 0.4, 0.5, 0.6, 0.7, 0.8, 0.9, 1.1]:
        policy = SelectiveCritic(threshold)
        utility = 0
        invocations = 0
        for row in records:
            invoke = policy.choose(Features.model_validate(row["features"])).invoke
            utility += float(
                row["critic_score"]["correct"] if invoke else row["initial_score"]["correct"]
            )
            if invoke:
                utility -= 0.05 * min(1, row["critic_tokens"] / 3000)
                invocations += 1
        options.append(
            {"threshold": threshold, "utility": utility / len(records), "invocations": invocations}
        )
    # Equal utility favours fewer calls, then the higher threshold. No category/ID exceptions.
    selected = max(options, key=lambda r: (r["utility"], -r["invocations"], r["threshold"]))
    return {
        "schema_version": 1,
        "policy_version": POLICY_VERSION,
        "weights": WEIGHTS,
        "threshold": selected["threshold"],
        "cost_weight": 0.03,
        "calibration_count": len(records),
        "selection_criterion": "mean correctness minus 0.05*(critic tokens/3000, capped at 1)",
        "candidates": options,
        "evaluation_labels_used": False,
        "limitation": (
            "Eight development pairs provide weak calibration; this is "
            "deterministic parameter selection, not learned policy "
            "optimization."
        ),
    }
