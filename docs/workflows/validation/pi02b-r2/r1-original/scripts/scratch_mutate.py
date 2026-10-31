import json
import os
import shutil
import subprocess
import sys

ROOT = r"C:\Projects\alive-review-pi02b-r1-scratch"
W = os.path.join(ROOT, "alive", "workflows")
RUNNER, CONTEXT = os.path.join(W, "runner.py"), os.path.join(W, "context.py")
EGRESS = os.path.join(ROOT, "alive", "pi", "egress.py")
SUITES = [
    "tests/test_workflow_authority.py",
    "tests/test_workflow_cancellation.py",
    "tests/test_workflow_execution.py",
    "tests/test_workflow_transactions.py",
]

MUTANTS = [
    (
        "A1 stage claim is not a compare-and-set",
        RUNNER,
        "                    WorkflowStageRun.id == row.id,\n                    WorkflowStageRun.state == states.PENDING,\n",
        "                    WorkflowStageRun.id == row.id,\n",
    ),
    (
        "A2 owner revocation ignored by authority check",
        CONTEXT,
        'require(not revoked and grant.expires_at > now(), "authorization_expired_or_revoked")',
        'require(grant.expires_at > now(), "authorization_expired_or_revoked")',
    ),
    (
        "A3 context withdrawal ignored",
        CONTEXT,
        'require(not withdrawn, "context_withdrawn")',
        'require(True, "context_withdrawn")',
    ),
    (
        "A4 Governor configuration change ignored",
        CONTEXT,
        "control is not None and digest(control.configuration) == grant.configuration_sha256,",
        "control is not None,",
    ),
    (
        "A5 possible provider effect not preserved as UNKNOWN",
        RUNNER,
        "                        if possible:",
        "                        if False:",
    ),
    (
        "A6 cancel request never recorded",
        RUNNER,
        "            execution.cancel_requested = True",
        "            execution.cancel_requested = False",
    ),
    (
        "A7 retained stage result not hash-checked on read",
        RUNNER,
        '        and digest(event.payload["output"]) == stage.output_sha256,\n',
        "",
    ),
    (
        "A8 retained artifact not hash-checked on read",
        RUNNER,
        '            and digest(artifact.content) == output["sha256"]\n',
        "",
    ),
    (
        "A9 egress guard fails open when the host installs none",
        EGRESS,
        "                allowed = False\n                if self.workflow_guard is not None:",
        "                allowed = True\n                if self.workflow_guard is not None:",
    ),
    (
        "A10 model authority: approved model not compared",
        CONTEXT,
        "        and grant.models.get(role) == model\n",
        "",
    ),
    (
        "A11 Pi response linkage not checked before completing the stage",
        RUNNER,
        '        and requests[0].response_sha256 == pi.result_json.get("text_sha256")\n',
        "",
    ),
    (
        "A12 dependency completion not required before a stage starts",
        RUNNER,
        "                all(by_id[name].state == states.COMPLETED for name in stage.depends_on),",
        "                True,",
    ),
    (
        "A13 unclaimed-inquiry requirement dropped",
        RUNNER,
        '                    not inquiry.snapshot\n                    and inquiry.usage.get("calls", 0) == 0\n                    and (self.cognition.worker is None or self.cognition.worker.done()),',
        "                    True,",
    ),
    (
        "A14 execution slot not released on success",
        RUNNER,
        '            run.finished_at, run.terminal_reason = now(), "required_stages_completed"\n            execution.slot = None',
        '            run.finished_at, run.terminal_reason = now(), "required_stages_completed"',
    ),
    (
        "A15 execution deadline not enforced at authority checks",
        RUNNER,
        "            and aware(execution.deadline) > now()\n            and run.status == states.RUNNING,",
        "            and run.status == states.RUNNING,",
    ),
]

results = []
for name, path, old, new in MUTANTS:
    original = open(path, encoding="utf-8", newline="").read()
    text = original.replace("\r\n", "\n")
    if old not in text:
        results.append({"mutation": name, "result": "PATTERN_MISSING"})
        print("PATTERN_MISSING", name, flush=True)
        continue
    nl = "\r\n" if "\r\n" in original else "\n"
    shutil.copy(path, path + ".bak")
    try:
        open(path, "w", encoding="utf-8", newline="").write(
            text.replace(old, new, 1).replace("\n", nl)
        )
        out = subprocess.run(
            [
                sys.executable,
                "-B",
                "-m",
                "pytest",
                "-q",
                "-x",
                "-p",
                "no:cacheprovider",
                "-W",
                "ignore",
                "--tb=line",
                *SUITES,
            ],
            cwd=ROOT,
            env=dict(os.environ, ALIVE_META_API_KEY="", CI="true", PYTHONDONTWRITEBYTECODE="1"),
            capture_output=True,
            text=True,
        )
        failed = [l for l in out.stdout.splitlines() if l.startswith("FAILED")]
        errors = "ERROR at" in out.stdout or "ERROR collecting" in out.stdout
        caught = out.returncode != 0 and bool(failed) and not errors
        results.append(
            {
                "mutation": name,
                "result": "CAUGHT" if caught else "SURVIVED",
                "failed": failed[:2],
                "rc": out.returncode,
                "errors": errors,
            }
        )
        print(
            ("CAUGHT   " if caught else "SURVIVED ") + name,
            (failed[:1] or [""])[0][:140],
            flush=True,
        )
    finally:
        shutil.move(path + ".bak", path)

open(r"C:\Projects\alive-pi02b-r1-evidence\additional-mutations.json", "w").write(
    json.dumps(results, indent=2)
)
print("survivors:", [r["mutation"] for r in results if r["result"] != "CAUGHT"])
