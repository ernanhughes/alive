"""Report-only analysis of an AI-FIRST-04 ledger. Reads evidence; performs no inference.

Every number below is computed from the retained ledger and the locked corpus. The paired test is
an exact two-sided McNemar (binomial on discordant pairs); the 24 held-out tasks share mechanisms,
so p-values are descriptive, not a population claim.
"""

import json
import statistics
import sys
from math import comb
from pathlib import Path

from alive.adaptation import oracle_v2

ARMS = "ABCD"
NAMES = {"A": "stateless", "B": "history", "C": "family-latest", "D": "selective"}


def mcnemar(wins, losses):
    n = wins + losses
    if n == 0:
        return 1.0
    tail = sum(comb(n, k) for k in range(min(wins, losses) + 1)) / 2**n
    return min(1.0, 2 * tail)


def rate(count, total):
    return f"{count}/{total}"


def explain(entry):
    g = entry["grade"]
    d = g["dimensions"]
    if d["run_failure"]:
        who = d["run_failure"]
        return f"no validated answer ({who}); semantic {d['semantic']}"
    if not d["contract_compliance"]["ok"]:
        c = d["contract_compliance"]
        bits = []
        if c["missing_cases"]:
            bits.append(f"missing predictions {','.join(c['missing_cases'])}")
        if not c["issue_flag"]:
            bits.append("no issue_present")
        if c["malformed_cases"]:
            bits.append("malformed " + ",".join(c["malformed_cases"]))
        return "incomplete structure: " + "; ".join(bits)
    if d["semantic"] == "incorrect":
        wrong = [
            f"{c['id']}:{'obs' if c['observed_prediction'] == 'incorrect' else 'req'}"
            for c in g["cases"]
            if "incorrect" in (c["observed_prediction"], c["required_prediction"])
        ]
        flag = "" if g["issue_flag"] != "incorrect" else " issue flag wrong"
        return "wrong prediction " + ",".join(wrong) + flag
    if not g["end_to_end"]:
        return "reference integrity invalid"
    return "ok"


def summarize(entries):
    n = len(entries)
    calls = [c for e in entries for c in e["review"]["calls"]]
    ok = sum(e["grade"]["end_to_end"] for e in entries)
    tokens = sum(e["review"]["usage"]["tokens"] for e in entries)
    requests = sum(e["review"]["usage"]["provider_requests"] for e in entries)
    dims = [e["grade"]["dimensions"] for e in entries]
    return {
        "n": n,
        "end_to_end": ok,
        "semantic_correct": sum(d["semantic"] == "correct" for d in dims),
        "semantic_incorrect": sum(d["semantic"] == "incorrect" for d in dims),
        "semantic_undetermined": sum(d["semantic"] == "undetermined" for d in dims),
        "contract_compliant": sum(d["contract_compliance"]["ok"] for d in dims),
        "run_failures": sum(bool(d["run_failure"]) for d in dims),
        "reference_normalized": sum(d["reference_normalized"] for d in dims),
        "grounded": sum(
            d["grounding"]["citations"] > 0
            and d["grounding"]["matching"] == d["grounding"]["citations"]
            for d in dims
        ),
        "provider_requests": requests,
        "tokens": tokens,
        "tokens_per_correct": round(tokens / ok) if ok else None,
        "requests_per_correct": round(requests / ok, 2) if ok else None,
        "median_invocation_latency_ms": round(
            statistics.median(c["latency_ms"] for c in calls if c["latency_ms"])
        )
        if calls
        else None,
        "median_context_bytes": statistics.median(
            (e["review"]["selection"] or {}).get("context_bytes", 0) for e in entries
        ),
        "lessons_supplied": sum(
            len((e["review"]["selection"] or {}).get("selected", [])) for e in entries
        ),
        "turns_with_a_lesson": sum(
            bool((e["review"]["selection"] or {}).get("selected")) for e in entries
        ),
    }


def paired(table, x, y):
    wins = [
        t
        for t, r in table.items()
        if r[x]["grade"]["end_to_end"] and not r[y]["grade"]["end_to_end"]
    ]
    losses = [
        t
        for t, r in table.items()
        if r[y]["grade"]["end_to_end"] and not r[x]["grade"]["end_to_end"]
    ]
    both = sum(r[x]["grade"]["end_to_end"] and r[y]["grade"]["end_to_end"] for r in table.values())
    neither = sum(
        not r[x]["grade"]["end_to_end"] and not r[y]["grade"]["end_to_end"] for r in table.values()
    )
    return {
        "pair": f"{x} vs {y}",
        "x_wins": len(wins),
        "x_losses": len(losses),
        "ties_both_pass": both,
        "ties_both_fail": neither,
        "exact_mcnemar_p": round(mcnemar(len(wins), len(losses)), 4),
        "x_win_tasks": wins,
        "x_loss_tasks": losses,
    }


def gold_relevance(ledger, tasks, table):
    """Selection quality against corpus gold mechanisms (independent of any model outcome)."""
    lessons = ledger["dev_policy"]["lessons"]
    to_lesson = {x["id"]: x["lesson_id"] for x in lessons}
    active = {
        x["lesson_id"]: set(x["proposal"].get("mechanisms", []))
        for x in lessons
        if x["state"] == "active"
    }
    out = {}
    for arm in ARMS:
        supplied = relevant_supplied = 0
        with_available = hit = without_available = quiet = 0
        for task_id, row in table.items():
            gold = set(tasks[task_id]["mechanisms"])
            available = {i for i, m in active.items() if m & gold}
            selected = (row[arm]["review"]["selection"] or {}).get("selected", [])
            chosen = [to_lesson[s["item_id"]] for s in selected if s["item_id"] in to_lesson]
            supplied += len(chosen)
            relevant_supplied += sum(c in available for c in chosen)
            if available:
                with_available += 1
                hit += any(c in available for c in chosen)
            else:
                without_available += 1
                quiet += not chosen
        out[arm] = {
            "lessons_supplied": supplied,
            "supplied_gold_relevant": relevant_supplied,
            "precision": round(relevant_supplied / supplied, 3) if supplied else None,
            "tasks_with_a_relevant_lesson_available": with_available,
            "recall_of_available_relevant": rate(hit, with_available),
            "tasks_with_no_relevant_lesson_available": without_available,
            "correctly_supplied_none": rate(quiet, without_available),
        }
    return out


def main(path, out=None):
    ledger = json.loads(Path(path).read_text(encoding="utf-8"))
    corpus, _ = oracle_v2.frozen_corpus()
    tasks = {t["id"]: t for t in corpus["tasks"]}
    held = [e for e in ledger["evaluation"] if e["phase"] == "heldout"]
    table = {}
    for e in held:
        table.setdefault(e["task_id"], {})[e["arm"]] = e
    table = {t: r for t, r in table.items() if all(a in r for a in ARMS)}
    result = {
        "schema": "selective-summary/v1",
        "ledger_status": ledger["status"],
        "implementation_sha": ledger["implementation_sha"],
        "heldout_tasks_complete": len(table),
        "arms": {a: summarize([r[a] for r in table.values()]) for a in ARMS},
        "by_tier": {
            tier: {
                a: rate(
                    sum(
                        r[a]["grade"]["end_to_end"]
                        for t, r in table.items()
                        if tasks[t]["tier"] == tier
                    ),
                    sum(tasks[t]["tier"] == tier for t in table),
                )
                for a in ARMS
            }
            for tier in ("standard", "hard", "extreme")
        },
        "by_label": {
            label: {
                a: rate(
                    sum(
                        r[a]["grade"]["end_to_end"]
                        for t, r in table.items()
                        if tasks[t]["label"] == label
                    ),
                    sum(tasks[t]["label"] == label for t in table),
                )
                for a in ARMS
            }
            for label in ("defective", "correct")
        },
        "paired": [
            paired(table, x, y)
            for x, y in (("D", "A"), ("D", "C"), ("D", "B"), ("C", "A"), ("B", "A"))
        ],
        "per_task": [
            {
                "task": t,
                "tier": tasks[t]["tier"],
                "label": tasks[t]["label"],
                **{a: int(r[a]["grade"]["end_to_end"]) for a in ARMS},
                "supplied_D": [
                    s["lesson_id"][:8]
                    for s in (r["D"]["review"]["selection"] or {}).get("selected", [])
                ],
                "explanation": "; ".join(
                    f"{a}: {explain(r[a])}" for a in ARMS if not r[a]["grade"]["end_to_end"]
                )
                or "all arms ok",
            }
            for t, r in sorted(table.items())
        ],
        "selection_vs_gold": gold_relevance(ledger, tasks, table)
        if "dev_policy" in ledger and table
        else None,
    }
    dev = [e for e in ledger["evaluation"] if e["phase"] == "dev"]
    result["development"] = {
        a: summarize([e for e in dev if e["arm"] == a])
        for a in "AD"
        if any(e["arm"] == a for e in dev)
    }
    cal = [e for e in ledger["evaluation"] if e["phase"] == "calibration"]
    result["calibration_A"] = {
        "end_to_end": rate(sum(e["grade"]["end_to_end"] for e in cal), len(cal)),
        "tasks": {e["task_id"]: explain(e) for e in cal},
    }
    result["development_calibration_A_by_tier"] = {
        tier: rate(
            sum(
                e["grade"]["end_to_end"]
                for e in dev
                if e["arm"] == "A" and tasks[e["task_id"]]["tier"] == tier
            ),
            sum(e["arm"] == "A" and tasks[e["task_id"]]["tier"] == tier for e in dev),
        )
        for tier in ("standard", "hard")
    }
    repeats = {}
    for e in ledger["evaluation"]:
        if e["phase"] == "repeat":
            first = (
                next(x for x in held if x["task_id"] == e["task_id"] and x["arm"] == e["arm"])
                if any(x["task_id"] == e["task_id"] and x["arm"] == e["arm"] for x in held)
                else None
            )
            if first:
                repeats.setdefault(e["task_id"], {})[e["arm"]] = {
                    "first": first["grade"]["end_to_end"],
                    "repeat": e["grade"]["end_to_end"],
                }
    result["repeats"] = repeats
    result["ablation"] = [
        {
            "task": e["task_id"],
            "condition": e["condition"],
            "end_to_end": e["grade"]["end_to_end"],
            "semantic": e["grade"]["dimensions"]["semantic"],
            "compliant": e["grade"]["dimensions"]["contract_compliance"]["ok"],
            "lessons": len(e["lessons"]),
            "relevant_included": bool(set(e["lessons"]) & set(e["relevant_lessons"])),
        }
        for e in ledger.get("ablation", [])
    ]
    base = {e["task_id"]: e["grade"]["end_to_end"] for e in dev if e["arm"] == "A"}
    for row in result["ablation"]:
        row["stateless_baseline"] = base.get(row["task"])
    result["positive_transfer_ablation"] = [
        {
            "task": e["task_id"],
            "condition": e["condition"],
            "repetition": e["repetition"],
            "end_to_end": e["grade"]["end_to_end"],
        }
        for e in ledger.get("positive_ablation", [])
    ]
    result["totals"] = ledger.get("totals")
    result["restart_replay"] = ledger.get("restart_replay")
    result["training"] = {
        "tasks": len(ledger["training"]),
        "end_to_end": sum(t["grade"]["end_to_end"] for t in ledger["training"]),
        "lessons_exported": sum(bool(t.get("approved_public_export")) for t in ledger["training"]),
        "extraction_retries": sum("extraction_retry" in t for t in ledger["training"]),
    }
    text = json.dumps(result, indent=1)
    if out:
        Path(out).write_text(text + "\n", encoding="utf-8", newline="\n")
    print(text)


if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2] if len(sys.argv) > 2 else None)
