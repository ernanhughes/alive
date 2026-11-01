"""Supplementary, clearly labelled regrade of retained AI-FIRST-03 answers under oracle v2.

This never replaces the original v1 scores or labels. Output is a separate evidence file. It uses
only retained responses: no inference, no ledger mutation.
"""

import json
from pathlib import Path

from alive.adaptation import oracle, oracle_v2

ROOT = Path(__file__).resolve().parents[1]
EVIDENCE = ROOT / "docs/intelligence/evidence"
OUT = EVIDENCE / "ai-first-04-v1-regrade.json"
# errors-4 contract: "Pop last element from a copied list". Every other v1 contract is
# return-oriented, so the reference's own resulting state is the contract there.
UNCHANGED = {"errors-4"}


def as_v2(task):
    return task | {
        "input_state": "unchanged" if task["id"] in UNCHANGED else "as_reference",
    }


def main():
    corpus, _ = oracle.frozen_corpus()
    tasks = {t["id"]: as_v2(t) for t in corpus["tasks"]}
    ledger = json.loads((EVIDENCE / "adaptation-live-ledger.json").read_text("utf-8"))
    raw = {(f["phase"], f["task_id"], f["arm"]): f for f in ledger.get("workflow_failures", [])}
    rows = []
    for record in ledger["evaluation"]:
        key = (record["phase"], record["task_id"], record["arm"])
        task = tasks[record["task_id"]]
        answer = record["review"]["answer"]
        failure = raw.get(key)
        source = "retained validated artifact"
        run_failure = None
        if answer is None and failure:
            run_failure = failure["terminal_reason"]
            outputs = [o for o in failure["model_outputs"] if o.get("output")]
            answer = outputs[0]["output"] if outputs else None
            source = (
                "raw validated model output retained on the failed run"
                if answer
                else "no usable model output (provider truncation)"
            )
        v2 = oracle_v2.grade(task, answer, run_failure=run_failure, check_reference=False)
        # End-to-end for these rows ignores run-level refusals: that is the point of the regrade.
        rows.append(
            {
                "phase": record["phase"],
                "task_id": record["task_id"],
                "arm": record["arm"],
                "v1_score": record["grade"]["score"],
                "v1_issue_label": record["grade"]["issue_present"],
                "v2_issue_label": v2["issue_present"],
                "v2_semantic": v2["dimensions"]["semantic"],
                "v2_compliance": v2["dimensions"]["contract_compliance"]["ok"],
                "v2_end_to_end_ignoring_run_refusal": v2["end_to_end"],
                "run_failure": run_failure,
                "answer_source": source,
            }
        )
    summary = {}
    for phase in ("dev", "heldout"):
        for arm in "ABC":
            sel = [r for r in rows if r["phase"] == phase and r["arm"] == arm]
            summary[f"{phase}:{arm}"] = {
                "n": len(sel),
                "v1_full": sum(r["v1_score"] == 1 for r in sel),
                "v2_semantic_correct": sum(r["v2_semantic"] == "correct" for r in sel),
                "v2_semantic_incorrect": sum(r["v2_semantic"] == "incorrect" for r in sel),
                "v2_semantic_undetermined": sum(r["v2_semantic"] == "undetermined" for r in sel),
                "v2_structurally_compliant": sum(r["v2_compliance"] for r in sel),
                "v2_end_to_end_ignoring_run_refusal": sum(
                    r["v2_end_to_end_ignoring_run_refusal"] for r in sel
                ),
            }
    OUT.write_text(
        json.dumps(
            {
                "schema": "ai-first-04-v1-regrade/v1",
                "label": "SUPPLEMENTARY. Original AI-FIRST-03 scores/labels are unchanged.",
                "verifier": oracle_v2.VERIFIER,
                "method": "retained answers regraded; errors-4 input_state=unchanged, all other "
                "v1 tasks input_state=as_reference; fixture reference self-check disabled",
                "summary": summary,
                "rows": rows,
            },
            indent=1,
        ),
        encoding="utf-8",
    )
    print(json.dumps(summary, indent=1))


if __name__ == "__main__":
    main()
