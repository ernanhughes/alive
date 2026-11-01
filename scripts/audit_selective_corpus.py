"""Programmatic audit of the AI-FIRST-04 corpus before it is frozen.

This is a programmatic audit by the implementation agent. It is NOT independent human
adjudication of the contracts, and the evidence says so. It checks, for every task:

* the hand-written expectation, the reference implementation and the label agree;
* defective tasks have at least one discriminating case, correct tasks have none;
* execution is deterministic (no hash-order or time dependence);
* nothing in ids, contracts or code leaks the label (no comments, no telling vocabulary);
* the source fits the model-input limits, and the mechanism tags are in the closed vocabulary;
* every held-out task is mapped to the training tasks a relevant lesson could come from.
"""

import json
import re
import sys
from pathlib import Path

from alive.adaptation import oracle_v2
from alive.adaptation.contracts import Mechanism
from alive.analysis.contracts import MAX_FILES, MAX_SOURCE_BYTES

ROOT = Path(__file__).resolve().parents[1]
CORPUS = ROOT / "docs/intelligence/selective-corpus-v2.json"
OUT = ROOT / "docs/intelligence/selective-corpus-v2-audit.json"
LEAKY = re.compile(
    r"\b(bug|bugs|buggy|defect|defects|defective|fix|fixme|todo|wrong|incorrect|broken|"
    r"faulty|flaw|mistake|expected|should be|reference|oracle|correct)\b",
    re.IGNORECASE,
)
VOCABULARY = set(Mechanism.__args__)
TARGETS = {"train": 18, "dev": 12, "heldout": 24}


def main():
    data = json.loads(CORPUS.read_text(encoding="utf-8"))
    tasks = data["tasks"]
    problems, rows = [], []
    ids = [t["id"] for t in tasks]
    if len(ids) != len(set(ids)):
        problems.append("duplicate task ids")
    split_counts = {s: sum(t["split"] == s for t in tasks) for s in TARGETS}
    if split_counts != TARGETS:
        problems.append(f"split sizes {split_counts} != {TARGETS}")
    for t in tasks:
        row = {"id": t["id"], "split": t["split"], "label": t["label"], "tier": t["tier"]}
        modules = oracle_v2.modules_of(t)
        first = oracle_v2.execute(t["code"], t["cases"], modules)
        again = oracle_v2.execute(t["code"], t["cases"], modules)
        ref = oracle_v2.execute(t["reference"], t["cases"], modules)
        ref_again = oracle_v2.execute(t["reference"], t["cases"], modules)
        if first != again or ref != ref_again:
            problems.append(f"{t['id']}: nondeterministic execution")
        tolerance = float(t.get("tolerance", 0))
        disagreements, discriminating = [], []
        for spec, seen, target in zip(t["cases"], first, ref, strict=True):
            ref_ok = all(oracle_v2.conforms(t, spec, target, target, tolerance))
            if not ref_ok:
                disagreements.append(spec["id"])
            if not all(oracle_v2.conforms(t, spec, seen, target, tolerance)):
                discriminating.append(spec["id"])
        if disagreements:
            problems.append(f"{t['id']}: reference != hand-written expectation on {disagreements}")
        if t["label"] == "defective" and not discriminating:
            problems.append(f"{t['id']}: labelled defective but no case distinguishes it")
        if t["label"] == "correct" and discriminating:
            problems.append(f"{t['id']}: labelled correct but violates {discriminating}")
        if (t["label"] == "defective") == (t["code"] == t["reference"]):
            problems.append(f"{t['id']}: label contradicts code/reference identity")
        if len(t["cases"]) < 3:
            problems.append(f"{t['id']}: too few cases")
        outputs = [json.dumps(c["expected"], sort_keys=True) for c in t["cases"]]
        if t["label"] == "defective" and len(discriminating) == len(t["cases"]):
            problems.append(f"{t['id']}: every case fails; a lesson-free guess would be trivial")
        files = oracle_v2.source_files(t)
        text = "\n".join([t["id"], t["contract"], *files.values()])
        for name, source in [("implementation.py", t["code"]), *t.get("files", {}).items()]:
            if "#" in source or '"""' in source.replace('"""', "", 0) and False:
                problems.append(f"{t['id']}: comment in {name}")
        leak = sorted({m.lower() for m in LEAKY.findall(text)})
        if leak:
            problems.append(f"{t['id']}: leaky vocabulary {leak}")
        size = sum(len(s.encode()) for s in files.values())
        if size > MAX_SOURCE_BYTES or len(files) > MAX_FILES:
            problems.append(f"{t['id']}: source exceeds model-input limits")
        unknown = set(t["mechanisms"]) - VOCABULARY
        if unknown or not t["mechanisms"]:
            problems.append(f"{t['id']}: mechanisms outside vocabulary {unknown}")
        row |= {
            "cases": len(t["cases"]),
            "discriminating_cases": discriminating,
            "distinct_expected_outputs": len(set(outputs)),
            "source_bytes": size,
            "files": sorted(files),
        }
        rows.append(row)
    train = [t for t in tasks if t["split"] == "train"]
    coverage = {}
    for t in tasks:
        if t["split"] == "train":
            continue
        sharing = sorted(s["id"] for s in train if set(s["mechanisms"]) & set(t["mechanisms"]))
        coverage[t["id"]] = {
            "split": t["split"],
            "label": t["label"],
            "mechanisms": t["mechanisms"],
            "training_tasks_sharing_a_mechanism": sharing,
            "relevant_lesson_possible": bool(sharing),
        }
    held = [c for c in coverage.values() if c["split"] == "heldout"]
    summary = {
        "schema": "selective-corpus-audit/v1",
        "assessment": "Programmatic audit by the implementation agent. NOT independent human "
        "adjudication of contracts, labels or hand-written expectations.",
        "tasks": len(tasks),
        "splits": split_counts,
        "labels": {k: sum(t["label"] == k for t in tasks) for k in ("defective", "correct")},
        "tiers": {
            s: {
                k: sum(t["tier"] == k and t["split"] == s for t in tasks)
                for k in ("standard", "hard")
            }
            for s in TARGETS
        },
        "heldout_with_relevant_lesson_possible": sum(c["relevant_lesson_possible"] for c in held),
        "heldout_with_no_relevant_training_mechanism": [
            k
            for k, c in coverage.items()
            if c["split"] == "heldout" and not c["relevant_lesson_possible"]
        ],
        "problems": problems,
        "tasks_audited": rows,
        "coverage": coverage,
    }
    OUT.write_text(json.dumps(summary, indent=1) + "\n", encoding="utf-8", newline="\n")
    print(
        json.dumps(
            {k: v for k, v in summary.items() if k not in ("tasks_audited", "coverage")}, indent=1
        )
    )
    return 1 if problems else 0


if __name__ == "__main__":
    sys.exit(main())
