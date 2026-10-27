"""Frozen ALIVE-10 decision-level comparison using the real v2 policy function.

This is not a native outcome study and not a new simulator. It replays a predeclared
eight-observation sequence against decision functions so the cost/abstention trade-off
is explicit. Labels describe whether an analysis would have been useful; they are not
model outputs or browser observations.
"""

import json
import subprocess
from pathlib import Path

from alive.web_experience import adaptive_recommendation, new_context, new_policy

OUT = Path("archives/ALIVE-10/evidence/policy-comparison.json")
SEQUENCE = [
    {"id": "e1", "useful": False},
    {"id": "e2", "useful": False},
    {"id": "e3", "useful": False},
    {"id": "e4", "useful": True},
    {"id": "e5", "useful": False},
    {"id": "e6", "useful": True},
    {"id": "e7", "useful": True},
    {"id": "e8", "useful": True},
]
COST_PER_CALL = 0.0003375


def policy(evidence, suppressions=0):
    document = new_policy()
    context = new_context("goal", "url", "auto")
    context["evidence"] = {
        unit: {"useful": useful, "feedback_id": unit, "note_id": unit}
        for unit, useful in evidence.items()
    }
    context["suppressions"] = suppressions
    document["contexts"]["goal|url|auto"] = context
    return document


def v2_decisions():
    evidence = {}
    suppressions = 0
    probes = 0
    decisions = []
    for item in SEQUENCE:
        document = policy(evidence, suppressions)
        adaptive = adaptive_recommendation(document, "goal|url|auto")
        if adaptive.get("probe"):
            action = "analyse"
            suppressions = 0
            probes += 1
        elif adaptive["recommendation"] == "no_action":
            action = "no_action"
            suppressions += 1
        else:
            action = "analyse"
        decisions.append({"id": item["id"], "action": action, "label_useful": item["useful"]})
        if action == "analyse" and item["id"] not in evidence:
            evidence[item["id"]] = item["useful"]
    return decisions, probes


def v1_decisions():
    evidence = {}
    decisions = []
    for item in SEQUENCE:
        useful = sum(1 for value in evidence.values() if value)
        support = len(evidence)
        rate = useful / support if support else None
        if support >= 3 and rate is not None and rate <= 0.20:
            action = "no_action"
        else:
            action = "analyse"
        decisions.append({"id": item["id"], "action": action, "label_useful": item["useful"]})
        if action == "analyse":
            evidence[item["id"]] = item["useful"]
    return decisions


def simple_decisions():
    evidence = {}
    decisions = []
    for item in SEQUENCE:
        useful = sum(1 for value in evidence.values() if value)
        support = len(evidence)
        rate = useful / support if support else None
        if support >= 1 and rate is not None and rate <= 0.20:
            action = "no_action"
        else:
            action = "analyse"
        decisions.append({"id": item["id"], "action": action, "label_useful": item["useful"]})
        if action == "analyse":
            evidence[item["id"]] = item["useful"]
    return decisions


def constant_decisions():
    return [
        {"id": item["id"], "action": "analyse", "label_useful": item["useful"]} for item in SEQUENCE
    ]


def summarize(decisions, probes=0):
    calls = sum(1 for row in decisions if row["action"] == "analyse")
    useful = sum(1 for row in decisions if row["action"] == "analyse" and row["label_useful"])
    missed = sum(1 for row in decisions if row["action"] != "analyse" and row["label_useful"])
    paused = sum(1 for row in decisions if row["action"] != "analyse")
    return {
        "calls": calls,
        "useful_analyses": useful,
        "useful_analyses_missed": missed,
        "paused_observations": paused,
        "probes": probes,
        "calls_avoided_vs_constant": 8 - calls,
        "estimated_counterfactual_cost_avoided_usd": round((8 - calls) * COST_PER_CALL, 7),
    }


def main():
    v2, probes = v2_decisions()
    arms = {
        "corrected_adaptive_v2": summarize(v2, probes),
        "alive09_v1_absorbing": summarize(v1_decisions()),
        "simple_one_negative": summarize(simple_decisions()),
        "constant_analyse": summarize(constant_decisions()),
    }
    result = {
        "kind": "frozen decision-level replay",
        "source_commit": subprocess.check_output(
            ["git", "rev-parse", "HEAD"],
            cwd=Path(__file__).resolve().parents[1],
            text=True,
        ).strip(),
        "not_native_outcome_evidence": True,
        "caveat": (
            "Eight predeclared observations with usefulness labels. No model was called. "
            "The sequence demonstrates decision and cost trade-offs, not task quality or "
            "Meta superiority. Suppressed observations are not independent native outcomes."
        ),
        "sequence": SEQUENCE,
        "decisions": {
            "corrected_adaptive_v2": v2,
            "alive09_v1_absorbing": v1_decisions(),
            "simple_one_negative": simple_decisions(),
            "constant_analyse": constant_decisions(),
        },
        "summary": arms,
        "cost_basis": {
            "synthetic_tokens_per_call": 150,
            "estimated_usd_per_call": COST_PER_CALL,
            "note": "Counterfactual estimate using ALIVE's price() formula; not a paid charge.",
        },
        "interpretation": (
            "The corrected policy recovers through a bounded probe, while the ALIVE-09 v1 "
            "policy remains paused. Constant analysis obtains more labelled useful analyses "
            "but makes more calls. The adaptive policy is not claimed superior."
        ),
    }
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    print(OUT)


if __name__ == "__main__":
    main()
