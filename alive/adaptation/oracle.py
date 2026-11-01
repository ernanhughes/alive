"""Trusted owner-local fixture oracle. Never accepts model patches or an API success flag."""

import json
import os
import subprocess
import sys
from pathlib import Path

from alive.adaptation.service import MEASURED, ORACLE, put
from alive.admission.service import row_for
from alive.continuity.service import artifact
from alive.workflows.context import digest, require

CORPUS = Path(__file__).resolve().parents[2] / "docs/intelligence/adaptation-corpus.json"
MANIFEST = CORPUS.with_name("adaptation-corpus-lock.json")
RUNNER = """
import json,sys
data=json.load(sys.stdin)
ns={}
exec(data['code'],ns)
out=[]
for case in data['cases']:
    try: out.append({'id':case['id'],'value':ns['solve'](case['input'])})
    except Exception as error: out.append({'id':case['id'],'error':type(error).__name__})
print(json.dumps(out,allow_nan=False))
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


def execute(code, cases):
    env = {
        k: v for k, v in os.environ.items() if k.upper() in ("SYSTEMROOT", "WINDIR", "TEMP", "TMP")
    }
    result = subprocess.run(
        [sys.executable, "-I", "-c", RUNNER],
        input=json.dumps({"code": code, "cases": cases}),
        text=True,
        capture_output=True,
        timeout=5,
        env=env,
        check=True,
    )
    return json.loads(result.stdout)


def predicted(text):
    if text.startswith("ERROR:"):
        return {"error": text[6:]}
    try:
        return {"value": json.loads(text)}
    except (ValueError, TypeError):
        return {"invalid": text}


def same(a, b):
    # JSON booleans are not numbers; numeric 2 and 2.0 represent the same value.
    if isinstance(a, bool) != isinstance(b, bool):
        return False
    if isinstance(a, dict) and isinstance(b, dict):
        return a.keys() == b.keys() and all(same(a[k], b[k]) for k in a)
    if isinstance(a, list) and isinstance(b, list):
        return len(a) == len(b) and all(same(x, y) for x, y in zip(a, b, strict=True))
    return a == b


def grade(task, answer):
    actual = execute(task["code"], task["cases"])
    required = execute(task["reference"], task["cases"])
    predictions = {p["case_id"]: p for p in (answer or {}).get("predictions", [])}
    cases = []
    for observed, target in zip(actual, required, strict=True):
        ref = observed.pop("id")
        target.pop("id")
        p = predictions.get(ref)
        ok = (
            bool(p)
            and same(predicted(p["observed"]), observed)
            and same(predicted(p["required"]), target)
        )
        cases.append({"id": ref, "actual": observed, "required": target, "passed": ok})
    issue = any(not same(c["actual"], c["required"]) for c in cases)
    issue_correct = (answer or {}).get("issue_present") is issue
    score = (sum(c["passed"] for c in cases) + issue_correct) / (len(cases) + 1)
    return {
        "score": score,
        "passed": score == 1,
        "issue_present": issue,
        "issue_correct": issue_correct,
        "cases": cases,
        "prose_verified": False,
        "verifier": "frozen-executable-fixture/v1",
    }


async def measure(kernel, admission_id, task_id):
    corpus, lock = frozen_corpus()
    task = next(t for t in corpus["tasks"] if t["id"] == task_id)
    async with kernel.lock, kernel.db.sessions.begin() as session:
        admission = await row_for(session, kernel, admission_id)
        stored = await artifact(session, kernel, admission)
        require(stored is not None, "oracle_result_required")
        # Bind actual source bytes, not just a task ID supplied by a caller.
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


def source_files(task):
    cases = json.dumps(task["cases"], ensure_ascii=False)
    return {
        "README.md": (
            f"# Public review fixture\nContract: {task['contract']}\nNamed input cases: {cases}\n"
        ),
        "implementation.py": task["code"],
    }
