"""Paired descriptive statistics; small pilots never support superiority claims."""

import math

import numpy as np


def price(usage):
    if not usage or "prompt_tokens" not in usage or "completion_tokens" not in usage:
        return None
    cached = min(
        usage["prompt_tokens"], usage.get("prompt_tokens_details", {}).get("cached_tokens", 0)
    )
    return (
        (usage["prompt_tokens"] - cached) * 1.25 + cached * 0.15 + usage["completion_tokens"] * 4.25
    ) / 1e6


def wilson(success, n):
    if not n:
        return None
    z = 1.959963984540054
    p = success / n
    den = 1 + z * z / n
    centre = (p + z * z / (2 * n)) / den
    radius = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / den
    return [max(0, centre - radius), min(1, centre + radius)]


def summarize(rows, ledger):
    policies = ["always", "never", "selective"]
    metrics = {}
    for policy in policies:
        available = [r for r in rows if policy in r["arms"]]
        arms = [r["arms"][policy] for r in available]
        n = len(arms)
        correct = sum(a["score"]["correct"] for a in arms)
        abstention_tasks = sum(a["score"]["expected_status"] == "ABSTAIN" for a in arms)
        tokens = sum(a["allocated_tokens"] for a in arms)
        dollars = [a.get("estimated_usd") for a in arms]
        known_cost = all(value is not None for value in dollars)
        correct_abstentions = sum(a["score"]["correct_abstention"] for a in arms)
        abstained = sum(a["score"].get("abstained", False) for a in arms)
        citations = [
            a["score"]["citation_validity"]
            for a in arms
            if a["score"]["citation_validity"] is not None
        ]
        metrics[policy] = {
            "tasks": n,
            "correct": correct,
            "accuracy": correct / n if n else None,
            "accuracy_wilson_95": wilson(correct, n),
            "correct_abstentions": sum(a["score"]["correct_abstention"] for a in arms),
            "abstention_precision": correct_abstentions / abstained if abstained else None,
            "abstention_recall": correct_abstentions / abstention_tasks
            if abstention_tasks
            else None,
            "citation_validity_rate": sum(citations) / len(citations) if citations else None,
            "citation_evaluable_tasks": len(citations),
            "abstention_opportunities": abstention_tasks,
            "unsupported_claim_acceptance": sum(a["score"]["unsupported_acceptance"] for a in arms),
            "critic_calls": sum(a["invoked"] for a in arms),
            "critic_invocation_rate": sum(a["invoked"] for a in arms) / n if n else None,
            "allocated_tokens": tokens,
            "tokens_per_task": tokens / n if n else None,
            "estimated_usd": sum(dollars) if known_cost else None,
            "estimated_usd_per_correct": sum(dollars) / correct if correct and known_cost else None,
            "mean_path_latency_ms": sum(a["path_latency_ms"] for a in arms) / n if n else None,
            "mean_end_to_end_latency_ms": sum(a.get("end_to_end_latency_ms", 0) for a in arms) / n
            if n
            else None,
            "failures": sum(bool(a.get("error")) for a in arms),
            "failure_rate": sum(bool(a.get("error")) for a in arms) / n if n else None,
            "timeouts": sum(a.get("error") == "timeout" for a in arms),
            "timeout_rate": sum(a.get("error") == "timeout" for a in arms) / n if n else None,
            "critic_rescues": sum(
                not r["initial_score"]["correct"] and a["score"]["correct"] and a["invoked"]
                for r, a in zip(available, arms, strict=True)
            ),
            "critic_regressions": sum(
                r["initial_score"]["correct"] and not a["score"]["correct"] and a["invoked"]
                for r, a in zip(available, arms, strict=True)
            ),
            "by_difficulty": {
                category: {
                    "n": sum(r["category"] == category for r in available),
                    "correct": sum(
                        r["category"] == category and r["arms"][policy]["score"]["correct"]
                        for r in available
                    ),
                }
                for category in sorted({r["category"] for r in available})
            },
        }
    paired = []
    for row in rows:
        if not all(p in row["arms"] for p in policies):
            continue
        a, n, s = (row["arms"][p] for p in policies)
        paired.append(
            {
                "task_id": row["task_id"],
                "family": row["family"],
                "always_minus_never": int(a["score"]["correct"]) - int(n["score"]["correct"]),
                "selective_minus_never": int(s["score"]["correct"]) - int(n["score"]["correct"]),
                "selective_minus_always": int(s["score"]["correct"]) - int(a["score"]["correct"]),
                "missed_observed_rescue": not s["invoked"]
                and not n["score"]["correct"]
                and a["score"]["correct"],
                "invoked_with_observed_always_regression": s["invoked"]
                and n["score"]["correct"]
                and not a["score"]["correct"],
            }
        )
    intervals = {}
    families = sorted({r["family"] for r in paired})
    rng = np.random.default_rng(3031)
    for comparison in ["always_minus_never", "selective_minus_never", "selective_minus_always"]:
        if not paired:
            continue
        samples = []
        for _ in range(2000):
            selected = rng.choice(families, size=len(families), replace=True)
            values = [r[comparison] for family in selected for r in paired if r["family"] == family]
            samples.append(float(np.mean(values)))
        intervals[comparison] = {
            "mean_difference": float(np.mean([r[comparison] for r in paired])),
            "family_cluster_bootstrap_95": np.quantile(samples, [0.025, 0.975]).tolist(),
            "family_clusters": len(families),
        }
    valid = [entry for entry in ledger if entry.get("usage")]
    costs = [price(entry.get("usage")) for entry in ledger]
    return {
        "policies": metrics,
        "paired_per_task": paired,
        "paired_intervals": intervals,
        "physical_unique_calls": len(ledger),
        "reported_unique_tokens": sum(e["usage"].get("total_tokens", 0) for e in valid),
        "estimated_unique_usd": sum(costs) if all(c is not None for c in costs) else None,
        "known_usage_estimated_usd_lower_bound": sum(c for c in costs if c is not None),
        "unknown_usage_calls": sum(c is None for c in costs),
        "selection_errors": {
            "missed_observed_rescues": sum(p["missed_observed_rescue"] for p in paired),
            "invoked_with_observed_regression": sum(
                p["invoked_with_observed_always_regression"] for p in paired
            ),
        },
        "latency_note": "Policy end-to-end paths include initial and own review with Governor I/O; "
        "exclude competing arms' queue time. Paired execution wall time is recorded per task. "
        "These are shared-artifact paths, not independently timed policy deployments.",
        "cost_note": (
            "Rate-card estimate, not confirmed billing. Shared initial "
            "calls are charged once physically, attributed once to each "
            "policy path; never sum policy allocations as billing."
        ),
        "uncertainty_note": (
            "Wilson intervals are descriptive; paired intervals resample "
            "task families because templated tasks are correlated. Tiny "
            "pilots provide weak uncertainty estimates."
        ),
        "selection_error_note": (
            "Observed Always-arm rescue/regression is a paired proxy, not a"
            " stochastic counterfactual guarantee for Selective."
        ),
    }
