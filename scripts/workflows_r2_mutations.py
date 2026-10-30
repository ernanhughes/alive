"""Replay R1 source mutations in an isolated copy; never rewrite the working source."""

import ast
import json
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
AUDIT = ROOT / "docs/workflows/validation/pi02b-r2/r1-original/scripts"
FENCE = "tests/test_workflow_r2_fence.py::test_dispatch_fence_individual_invariants"
HISTORY = "tests/test_workflow_r2_history.py::"
INVARIANTS = "tests/test_workflow_r2_invariants.py::"
TARGETS = {
    "A1": INVARIANTS + "test_completed_stage_cannot_be_claimed_again_even_by_current_run_owner",
    "A2": FENCE + "[revoke]",
    "A3": FENCE + "[withdraw]",
    "A4": FENCE + "[configuration]",
    "A5": "tests/test_workflow_authority.py::"
    "test_restart_reconciles_ambiguous_stage_without_dispatch",
    "A6": "tests/test_workflow_cancellation.py::"
    "test_explicit_cancel_of_pending_run_closes_its_reservation",
    "A7": HISTORY + "test_historical_artifact_hash_chain_is_enforced[rebuilt_hash]",
    "A8": HISTORY + "test_historical_artifact_hash_chain_is_enforced[artifact]",
    "A9": FENCE + "[missing_guard]",
    "A10": FENCE + "[model]",
    "A11": "tests/test_workflow_authority.py::"
    "test_process_exit_or_incomplete_receipt_cannot_complete_stage[output]",
    "A12": INVARIANTS + "test_control_dependency_blocks_stage_even_without_an_output_reference",
    "A13": INVARIANTS + "test_existing_inquiry_work_cannot_be_transferred_to_workflow[snapshot]",
    "A14": HISTORY + "test_success_releases_slot_for_another_admitted_inquiry",
    "A15": FENCE + "[deadline]",
    "B1": FENCE + "[model]",
    "B2": FENCE + "[context]",
    "B3": FENCE + "[status]",
    "B4": FENCE + "[stage_state]",
    "B5": FENCE + "[stage_link]",
    "C1": FENCE + "[expiry]",
}


def literal_assignment(filename, name, symbols):
    tree = ast.parse((AUDIT / filename).read_text(encoding="utf-8-sig"))
    value = next(
        node.value
        for node in tree.body
        if isinstance(node, ast.Assign)
        and any(isinstance(t, ast.Name) and t.id == name for t in node.targets)
    )
    # Read only static tuple/list/string data; never execute the review scripts.
    assert all(
        isinstance(node, (ast.List, ast.Tuple, ast.Constant, ast.Name, ast.Load))
        for node in ast.walk(value)
    )
    return eval(
        compile(ast.Expression(value), str(AUDIT / filename), "eval"), {"__builtins__": {}}, symbols
    )


def main():
    symbols = {
        "RUNNER": "alive/workflows/runner.py",
        "CONTEXT": "alive/workflows/context.py",
        "EGRESS": "alive/pi/egress.py",
    }
    cases = literal_assignment("scratch_mutate.py", "MUTANTS", symbols)
    cases = [(label.split()[0], path, old, new) for label, path, old, new in cases]
    # R1's first A7 text deletion was syntactically invalid. Use its documented A7v.
    cases[6] = (
        "A7",
        symbols["RUNNER"],
        '        and digest(event.payload["output"]) == stage.output_sha256,\n',
        "        and True,\n",
    )
    cases += [
        (label, symbols["RUNNER"], old, new)
        for label, old, new in literal_assignment("scratch_mutate7.py", "cases", {})
    ]
    cases.append(
        ("C1", symbols["CONTEXT"], "not revoked and grant.expires_at > now()", "not revoked")
    )
    receipts = []
    with tempfile.TemporaryDirectory(prefix="alive-pi02b-r2-mutations-") as directory:
        scratch = Path(directory)
        for name in ("alive", "tests", "scripts", "config", "fixtures", "migrations"):
            shutil.copytree(
                ROOT / name, scratch / name, ignore=shutil.ignore_patterns("__pycache__", "*.pyc")
            )
        for name in ("pyproject.toml", "alembic.ini"):
            shutil.copyfile(ROOT / name, scratch / name)
        env = os.environ | {
            "PYTHONDONTWRITEBYTECODE": "1",
            "CI": "true",
            "ALIVE_META_API_KEY": "",
            "ALIVE_PI_RUNTIME_DIR": str(ROOT / "pi-runtime"),
        }
        for label, path, old, new in cases:
            target = scratch / path
            original = target.read_text(encoding="utf-8")
            assert original.count(old) == 1, (label, "pattern missing or ambiguous")
            command = [
                sys.executable,
                "-B",
                "-m",
                "pytest",
                "-q",
                "-p",
                "no:cacheprovider",
                "--tb=short",
                TARGETS[label],
            ]
            baseline = subprocess.run(command, cwd=scratch, env=env, capture_output=True, text=True)
            assert baseline.returncode == 0, (
                label,
                "BASELINE_FAILED",
                baseline.stdout,
                baseline.stderr,
            )
            try:
                target.write_text(original.replace(old, new, 1), encoding="utf-8")
                changed = subprocess.run(
                    command, cwd=scratch, env=env, capture_output=True, text=True
                )
            finally:
                target.write_text(original, encoding="utf-8")
            killed = (
                changed.returncode == 1
                and "FAILED" in changed.stdout
                and ("AssertionError" in changed.stdout or "E   assert" in changed.stdout)
                and "ERROR at" not in changed.stdout
                and "ERROR collecting" not in changed.stdout
            )
            equivalent = label == "A10" and changed.returncode == 0
            assert killed or equivalent, (
                label,
                "INVALID_OR_SURVIVED",
                changed.stdout,
                changed.stderr,
            )
            receipts.append(
                {
                    "mutation": label,
                    "target": TARGETS[label],
                    "baseline": "PASS",
                    "result": "KILLED" if killed else "REDUNDANT_WITH_B1",
                    "modified_guard": old.strip(),
                    "replacement": new.strip(),
                    "assertion": changed.stdout if killed else None,
                }
            )
            print(json.dumps(receipts[-1]), flush=True)
    print(
        json.dumps(
            {
                "status": "PASS",
                "cases": len(receipts),
                "killed": sum(r["result"] == "KILLED" for r in receipts),
                "redundant": sum(r["result"] != "KILLED" for r in receipts),
            }
        )
    )


if __name__ == "__main__":
    main()
