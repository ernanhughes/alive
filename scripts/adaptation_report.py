"""Summarize retained outcomes without calling a model, changing labels or updating policy."""

import argparse
import json
import statistics
from pathlib import Path


def summary(ledger):
    result = {
        "implementation_sha": ledger["implementation_sha"],
        "status": ledger["status"],
        "cost": ledger["cost"],
        "conditions": {},
        "paired_heldout": [],
        "repeats": [],
    }
    for phase in ("dev", "heldout", "repeat"):
        result["conditions"][phase] = {}
        for arm in ("A", "B", "C"):
            rows = [r for r in ledger["evaluation"] if r["phase"] == phase and r["arm"] == arm]
            result["conditions"][phase][arm] = {
                "n": len(rows),
                "fully_correct": sum(r["grade"]["passed"] for r in rows),
                "mean_factual_score": statistics.mean(r["grade"]["score"] for r in rows)
                if rows
                else None,
                "lessons_used": sum(
                    bool((r["review"]["answer"] or {}).get("lesson_ids_used")) for r in rows
                ),
                "context_supplied": sum(bool(r["review"]["context"]["items"]) for r in rows),
                "failed_or_missing_answers": sum(not r["review"]["answer"] for r in rows),
            }
    heldout = {}
    for row in ledger["evaluation"]:
        if row["phase"] == "heldout":
            heldout.setdefault(row["task_id"], {})[row["arm"]] = row
    for task_id, arms in heldout.items():
        if set(arms) != {"A", "B", "C"}:
            continue
        scores = {a: r["grade"]["score"] for a, r in arms.items()}
        result["paired_heldout"].append(
            {
                "task_id": task_id,
                **scores,
                "C_minus_A": scores["C"] - scores["A"],
                "C_minus_B": scores["C"] - scores["B"],
                "used": (arms["C"]["review"]["answer"] or {}).get("lesson_ids_used", []),
            }
        )
    for row in ledger["evaluation"]:
        if row["phase"] == "repeat" and row["task_id"] in heldout:
            original = heldout[row["task_id"]][row["arm"]]
            result["repeats"].append(
                {
                    "task_id": row["task_id"],
                    "arm": row["arm"],
                    "original_score": original["grade"]["score"],
                    "repeat_score": row["grade"]["score"],
                    "changed": original["grade"]["score"] != row["grade"]["score"],
                }
            )
    values = [t["review"] for t in ledger["training"]]
    values += [t["extraction"] for t in ledger["training"] if "extraction" in t]
    values += [t["review"] for t in ledger["evaluation"]]
    calls = [c for value in values for c in value["calls"]]
    receipts = [p for c in calls for p in c["provider_receipts"]]
    result["usage"] = {
        "provider_requests": len(receipts),
        "http_200": sum(p["http_status"] == 200 for p in receipts),
        "production_network": sum(p["transport"] == "network" for p in receipts),
        "validated_invocations": sum(c["status"] == "validated" for c in calls),
        "prompt_tokens": sum(c["usage"].get("prompt_tokens", 0) for c in calls),
        "completion_tokens": sum(c["usage"].get("completion_tokens", 0) for c in calls),
        "total_tokens": sum(c["usage"].get("total_tokens", 0) for c in calls),
        "provider_latency_ms": sum(p["latency_ms"] or 0 for p in receipts),
        "wall_seconds": sum(v["wall_seconds"] for v in values),
        "models_observed": sorted({p["model_observed"] for p in receipts if p["model_observed"]}),
        "models_requested": sorted({c["model"] for c in calls}),
    }
    for phase in ("train", "extract", "dev", "heldout", "repeat"):
        phase_values = (
            [t["review"] for t in ledger["training"]]
            if phase == "train"
            else [t["extraction"] for t in ledger["training"] if "extraction" in t]
            if phase == "extract"
            else [t["review"] for t in ledger["evaluation"] if t["phase"] == phase]
        )
        phase_calls = [c for v in phase_values for c in v["calls"]]
        result.setdefault("phase_usage", {})[phase] = {
            "calls": len(phase_calls),
            "total_tokens": sum(c["usage"].get("total_tokens", 0) for c in phase_calls),
            "wall_seconds": sum(v["wall_seconds"] for v in phase_values),
        }
    result["negative_transfer"] = [
        p for p in result["paired_heldout"] if p["C_minus_A"] < 0 or p["C_minus_B"] < 0
    ]
    result["improvements"] = [
        p for p in result["paired_heldout"] if p["C_minus_A"] > 0 or p["C_minus_B"] > 0
    ]
    result["restart_replay"] = ledger.get("restart_replay")
    result["post_evaluation_guards"] = ledger.get("post_evaluation_guards")
    result["training_experiences"] = len(ledger.get("frozen_policy", {}).get("experiences", []))
    result["active_provisional_lessons"] = sum(
        lesson["state"] == "active" for lesson in ledger.get("frozen_policy", {}).get("lessons", [])
    )
    result["known_label_issue"] = {
        "task_id": "errors-4",
        "reason": "Contract requires a copied list; reference/issue oracle observe returns only. "
        "All arms correctly identify input mutation but frozen issue label is false.",
        "original_scores_retained": True,
        "independent_label_review": "NOT_RUN",
    }
    result["sensitivity_excluding_errors_4"] = {}
    for arm in ("A", "B", "C"):
        selected = [
            r
            for r in ledger["evaluation"]
            if r["phase"] == "heldout" and r["arm"] == arm and r["task_id"] != "errors-4"
        ]
        result["sensitivity_excluding_errors_4"][arm] = {
            "n": len(selected),
            "fully_correct": sum(r["grade"]["passed"] for r in selected),
            "mean_frozen_score": statistics.mean(r["grade"]["score"] for r in selected)
            if selected
            else None,
        }
    return result


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("ledger", type=Path)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    content = (
        json.dumps(summary(json.loads(args.ledger.read_text(encoding="utf-8"))), indent=2) + "\n"
    )
    if args.output:
        args.output.write_text(content, encoding="utf-8")
    print(content)
