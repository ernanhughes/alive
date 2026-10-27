"""Execute the frozen ALIVE-11-R1 four-policy decision replay.

No model is called. Labels and policy definitions are read from the archived protocol.
"""

import json
from pathlib import Path

from alive.experiment.metrics import price

ROOT = Path(__file__).resolve().parents[1]
PROTOCOL = ROOT / "archives/ALIVE-11-R1/protocol.json"
OUT = ROOT / "archives/ALIVE-11-R1/evidence/policy-comparison.json"
CALL_USAGE = {"prompt_tokens": 100, "completion_tokens": 50, "total_tokens": 150}


def fresh_state():
    return {
        "evidence": {},
        "suppressed": set(),
        "probed": set(),
        "exact_negative": set(),
        "suppressions": 0,
        "probes": 0,
    }


def counts(state):
    useful = sum(1 for value in state["evidence"].values() if value)
    support = len(state["evidence"])
    return useful, support, useful / support if support else None


def action_for(arm, state, case):
    useful, support, rate = counts(state)
    sha = case["sha"]
    if not case["eligible"]:
        return "no_action", False
    if arm == "A_frozen_context_wide":
        if support >= 3 and rate is not None and rate <= 0.20:
            if state["suppressions"] >= 3:
                state["suppressions"] = 0
                state["probes"] += 1
                return "analyse", True
            state["suppressions"] += 1
            return "no_action", False
        return "analyse", False
    if arm == "B_exact_negative_reuse":
        return ("no_action" if sha in state["exact_negative"] else "analyse"), False
    if arm == "C_evidence_aware_contextual":
        if support >= 3 and rate is not None and rate <= 0.20:
            if sha in state["evidence"] or sha in state["suppressed"] or sha in state["probed"]:
                return "no_action", False
            if len(state["suppressed"]) >= 3:
                state["suppressed"].clear()
                state["probed"].add(sha)
                state["probes"] += 1
                return "analyse", True
            state["suppressed"].add(sha)
            return "no_action", False
        return "analyse", False
    return "analyse", False


def apply_feedback(arm, state, case):
    if case.get("feedback") is None:
        return
    sha = case["sha"]
    useful = bool(case["feedback"])
    if arm in {"A_frozen_context_wide", "C_evidence_aware_contextual"}:
        state["evidence"][sha] = useful
    elif arm == "B_exact_negative_reuse":
        if useful:
            state["exact_negative"].discard(sha)
        else:
            state["exact_negative"].add(sha)
    # D has no feedback-conditioned state.


def roundtrip(state):
    encoded = {
        key: sorted(value) if isinstance(value, set) else value for key, value in state.items()
    }
    return json.loads(json.dumps(encoded)) | {
        "suppressed": set(encoded["suppressed"]),
        "probed": set(encoded["probed"]),
        "exact_negative": set(encoded["exact_negative"]),
    }


def run(arm, cases, restart_after):
    state = fresh_state()
    decisions = []
    analysed = set()
    calls = useful = missed = wasted = repeated = corrections = paused = 0
    for case in cases:
        action, probe = action_for(arm, state, case)
        correction = False
        if action == "no_action" and case.get("owner_correction"):
            action = "analyse"
            correction = True
            corrections += 1
            if arm == "A_frozen_context_wide":
                state["suppressions"] = 0
            elif arm == "C_evidence_aware_contextual":
                state["suppressed"].clear()
        decisions.append(
            {
                "id": case["id"],
                "sha": case["sha"],
                "eligible": case["eligible"],
                "source_adequate": case["source_adequate"],
                "action": action,
                "probe": probe,
                "owner_correction": correction,
            }
        )
        if action == "analyse":
            calls += 1
            if case["source_adequate"]:
                useful += 1
            else:
                wasted += 1
            if case["sha"] in analysed:
                repeated += 1
            analysed.add(case["sha"])
            apply_feedback(arm, state, case)
        else:
            paused += 1
            if case["source_adequate"]:
                missed += 1
        if case["id"] == restart_after:
            state = roundtrip(state)
    estimated = round(calls * price(CALL_USAGE), 7)
    return {
        "summary": {
            "calls": calls,
            "useful_opportunities_met": useful,
            "missed_opportunities": missed,
            "wasted_calls": wasted,
            "repeated_work": repeated,
            "owner_corrections": corrections,
            "paused_observations": paused,
            "probes": state["probes"],
            "estimated_synthetic_usd": estimated,
            "restart_boundary_roundtrip": restart_after,
        },
        "decisions": decisions,
    }


def main():
    protocol = json.loads(PROTOCOL.read_text(encoding="utf-8"))
    result = {
        "protocol_version": protocol["protocol_version"],
        "kind": protocol["kind"],
        "protocol_sha256": __import__("hashlib").sha256(PROTOCOL.read_bytes()).hexdigest(),
        "paid_inference": False,
        "caveat": protocol["caveat"],
        "arms": {},
    }
    for arm in protocol["arms"]:
        result["arms"][arm] = run(arm, protocol["cases"], protocol["restart_boundary_after"])
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({arm: data["summary"] for arm, data in result["arms"].items()}, indent=2))
    print(OUT)


if __name__ == "__main__":
    main()
