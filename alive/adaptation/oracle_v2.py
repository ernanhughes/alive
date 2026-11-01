"""Trusted owner-local fixture oracle v2 (``frozen-executable-fixture/v2``).

v1 (``oracle.py``) stays byte-identical so its lock and every AI-FIRST-03 measurement keep their
meaning. v2 measures *observable behaviour*: return value or exception type, the input's state
before and after execution (including nested structures), and keeps three things apart:

* execution observation - what the supplied implementation actually did;
* reference observation - what the independently specified contract requires;
* model prediction     - what ALIVE claimed would happen.

A structurally incomplete answer is never scored as wrong reasoning: semantics are tri-state
(correct / incorrect / undetermined) and structural, reference and end-to-end outcomes are
reported separately.

Security: this executes *vetted, author-owned fixture code* in a disposable ``python -I``
subprocess with a scrubbed environment and a timeout. That is a convenience boundary, not an OS
security sandbox. It must never be pointed at model output, patches or captured repositories.
"""

import json
import os
import subprocess
import sys
from pathlib import Path

from alive.adaptation.service import MEASURED, ORACLE, put
from alive.admission.service import row_for
from alive.continuity.service import artifact
from alive.workflows.context import digest, require

VERIFIER = "frozen-executable-fixture/v2"
CORPUS = Path(__file__).resolve().parents[2] / "docs/intelligence/selective-corpus-v2.json"
MANIFEST = CORPUS.with_name("selective-corpus-v2-lock.json")
IMPLEMENTATION = "implementation.py"
RUNNER = r"""
import copy, json, math, sys, types
data = json.load(sys.stdin)
for name, source in data["modules"].items():
    module = types.ModuleType(name)
    exec(source, module.__dict__)
    sys.modules[name] = module
namespace = {"__name__": "fixture"}
exec(data["code"], namespace)

def enc(v):
    if v is None or isinstance(v, (bool, int, str)):
        return v
    if isinstance(v, float):
        return v if math.isfinite(v) else {"$nonfinite": repr(v)}
    if isinstance(v, (list, tuple)):
        return [enc(x) for x in v]
    if isinstance(v, dict):
        return {str(k): enc(x) for k, x in v.items()}
    return {"$unserializable": type(v).__name__}

out = []
for case in data["cases"]:
    argument = copy.deepcopy(case["input"])
    record = {"id": case["id"]}
    try:
        record["value"] = enc(namespace["solve"](argument))
    except Exception as error:
        record["error"] = type(error).__name__
    record["input_after"] = enc(argument)
    out.append(record)
print(json.dumps(out, allow_nan=False))
"""


def frozen_corpus():
    data = json.loads(CORPUS.read_text(encoding="utf-8"))
    lock = json.loads(MANIFEST.read_text(encoding="utf-8"))
    require(digest(data) == lock["corpus_sha256"], "oracle_corpus_changed")
    require(
        digest(Path(__file__).read_text(encoding="utf-8")) == lock["oracle_sha256"],
        "oracle_implementation_changed",
    )
    return data, lock


def modules_of(task):
    return {name[:-3]: text for name, text in task.get("files", {}).items()}


def execute(code, cases, modules=None):
    env = {
        k: v for k, v in os.environ.items() if k.upper() in ("SYSTEMROOT", "WINDIR", "TEMP", "TMP")
    }
    result = subprocess.run(
        [sys.executable, "-I", "-c", RUNNER],
        input=json.dumps({"code": code, "cases": cases, "modules": modules or {}}),
        text=True,
        capture_output=True,
        timeout=5,
        env=env,
        check=True,
    )
    return json.loads(result.stdout)


def number(x):
    return isinstance(x, (int, float)) and not isinstance(x, bool)


def same(a, b, tolerance=0.0):
    """JSON equality: booleans are not numbers; 2 and 2.0 agree; null is not missing."""
    if isinstance(a, bool) != isinstance(b, bool):
        return False
    if number(a) and number(b):
        return a == b or (tolerance > 0 and abs(a - b) <= tolerance)
    if isinstance(a, dict) and isinstance(b, dict):
        return a.keys() == b.keys() and all(same(a[k], b[k], tolerance) for k in a)
    if isinstance(a, list) and isinstance(b, list):
        return len(a) == len(b) and all(same(x, y, tolerance) for x, y in zip(a, b, strict=True))
    return type(a) is type(b) and a == b


def outcome(observation):
    """The return-or-raise part of an observation. ``value: null`` is a real return value."""
    return {k: observation[k] for k in ("value", "error") if k in observation}


def predicted(text):
    """Parse a model prediction. ``None`` means the model supplied nothing parseable."""
    if not isinstance(text, str):
        return None
    text = text.strip()
    if text.startswith("ERROR:"):
        name = text[6:].strip()
        return {"error": name} if name else None
    try:
        return {"value": json.loads(text)}
    except (ValueError, TypeError):
        return None


def target_of(case, reference):
    """Hand-written expectation when the fixture has one, else the reference observation."""
    expected = case.get("expected")
    if expected is None:
        return reference
    return {k: expected[k] for k in ("value", "error", "input_after") if k in expected} | (
        {} if "input_after" in expected else {"input_after": reference["input_after"]}
    )


def conforms(task, case, observation, reference, tolerance):
    """Does an observation satisfy the contract for this case: outcome *and* resulting state.

    ``input_state: unchanged`` (default) forbids any mutation of the case input, including nested
    structures; ``as_reference`` requires the same resulting state as the specified contract.
    """
    target = target_of(case, reference)
    result = same(outcome(observation), outcome(target), tolerance)
    if task.get("input_state", "unchanged") == "unchanged":
        wanted = case["input"]
    else:
        wanted = target["input_after"]
    return result, same(observation["input_after"], wanted, tolerance)


def verdict(entry, field, truth, tolerance):
    """Grade one claimed outcome. Structural problems stay distinct from a wrong claim."""
    if entry is None:
        return "missing"
    claim = predicted(entry.get(field))
    if claim is None:
        return "malformed"
    return "correct" if same(claim, truth, tolerance) else "incorrect"


def compliance(task, answer):
    """Required structure only; never a statement about whether the prose is right."""
    ids = [c["id"] for c in task["cases"]]
    if not isinstance(answer, dict):
        return {
            "ok": False,
            "missing_cases": ids,
            "malformed_cases": [],
            "duplicate_cases": [],
            "issue_flag": False,
        }
    seen, duplicate = {}, []
    for entry in answer.get("predictions") or []:
        key = entry.get("case_id")
        if key in seen:
            duplicate.append(key)
        seen.setdefault(key, entry)
    missing = [key for key in ids if key not in seen]
    malformed = [
        key
        for key in ids
        if key in seen
        and (
            predicted(seen[key].get("observed")) is None
            or predicted(seen[key].get("required")) is None
        )
    ]
    flag = isinstance(answer.get("issue_present"), bool)
    return {
        "ok": not (missing or malformed or duplicate) and flag,
        "missing_cases": missing,
        "malformed_cases": malformed,
        "duplicate_cases": duplicate,
        "issue_flag": flag,
    }


def grade(task, answer, *, run_failure=None, reference_valid=True, check_reference=True):
    """Grade one answer. ``run_failure`` names why no answer exists (truncation, refusal...)."""
    tolerance = float(task.get("tolerance", 0))
    modules = modules_of(task)
    actual = execute(task["code"], task["cases"], modules)
    required = execute(task["reference"], task["cases"], modules)
    answer = answer if isinstance(answer, dict) else None
    predictions = {}
    for entry in (answer or {}).get("predictions") or []:
        predictions.setdefault(entry.get("case_id"), entry)
    cases, wrong, provided_correct, provided = [], 0, 0, 0
    for spec, seen, target in zip(task["cases"], actual, required, strict=True):
        got_result, got_state = conforms(task, spec, seen, target, tolerance)
        if check_reference:
            # The reference run must itself satisfy the contract; a fixture bug is never a score.
            require(
                all(conforms(task, spec, target, target, tolerance)),
                "fixture_reference_disagrees_with_expectation",
            )
        entry = predictions.get(spec["id"])
        verdicts = {
            field: verdict(entry, field, outcome(observation), tolerance)
            for field, observation in (("observed", seen), ("required", target))
        }
        scored = [v for v in verdicts.values() if v in ("correct", "incorrect")]
        provided += len(scored)
        provided_correct += scored.count("correct")
        wrong += scored.count("incorrect")
        cases.append(
            {
                "id": spec["id"],
                "actual": outcome(seen),
                "state_changed": not same(seen["input_after"], spec["input"], tolerance),
                "conforms": got_result and got_state,
                "return_conforms": got_result,
                "state_conforms": got_state,
                "observed_prediction": verdicts["observed"],
                "required_prediction": verdicts["required"],
            }
        )
    issue = any(not c["conforms"] for c in cases)
    flag = (answer or {}).get("issue_present")
    flag_state = (
        "missing" if not isinstance(flag, bool) else "correct" if flag is issue else "incorrect"
    )
    wrong += flag_state == "incorrect"
    structure = compliance(task, answer)
    units = len(cases) * 2 + 1
    provided_units = provided + (flag_state != "missing")
    undetermined = answer is None or provided_units < units
    semantic = "incorrect" if wrong else "undetermined" if undetermined else "correct"
    cases_ok = sum(
        c["observed_prediction"] == "correct" and c["required_prediction"] == "correct"
        for c in cases
    )
    end_to_end = bool(structure["ok"] and semantic == "correct" and reference_valid)
    text = (answer or {}).get("answer")
    return {
        "verifier": VERIFIER,
        "issue_present": issue,
        "issue_flag": flag_state,
        "cases": cases,
        "dimensions": {
            "semantic": semantic,
            "prediction_correctness": {
                "correct_units": provided_correct,
                "provided_units": provided,
                "total_units": len(cases) * 2,
            },
            "contract_compliance": structure,
            "reference_integrity": "valid" if reference_valid else "invalid",
            "task_completion": bool(
                isinstance(text, str)
                and text.strip()
                and not (answer or {}).get("needs_clarification")
            ),
            "run_failure": run_failure,
        },
        # v1-comparable unit score: per-case predictions plus the defect flag.
        "score": (cases_ok + (flag_state == "correct")) / (len(cases) + 1),
        "passed": end_to_end,
        "end_to_end": end_to_end,
        "prose_verified": False,
    }


def source_files(task):
    cases = json.dumps([{"id": c["id"], "input": c["input"]} for c in task["cases"]])
    files = {
        "README.md": (
            f"# Public review fixture\nContract: {task['contract']}\nNamed input cases: {cases}\n"
        ),
        IMPLEMENTATION: task["code"],
    }
    return files | dict(task.get("files", {}))


async def measure(kernel, admission_id, task_id, *, corpus=None):
    corpus, lock = corpus or frozen_corpus()
    task = next(t for t in corpus["tasks"] if t["id"] == task_id)
    async with kernel.lock, kernel.db.sessions.begin() as session:
        admission = await row_for(session, kernel, admission_id)
        stored = await artifact(session, kernel, admission)
        require(stored is not None, "oracle_result_required")
        from alive.sources.models import SourceCapture

        capture = await session.get(
            SourceCapture, admission.terms["source"]["resources"]["source_ref"]
        )
        files = {f["path"]: f["content"] for f in capture.content["files"]}
        require(files == source_files(task), "oracle_fixture_source_mismatch")
        body = grade(task, stored["result"]) | {
            "admission_id": admission_id,
            "artifact_sha256": stored["sha256"],
            "source_sha256": digest(admission.terms["source"]),
            "task_id": task_id,
            "family": task["family"],
            "split": task["split"],
            "corpus_sha256": lock["corpus_sha256"],
            "oracle_sha256": lock["oracle_sha256"],
        }
        return await put(session, kernel, MEASURED, admission_id, body, source=ORACLE)
