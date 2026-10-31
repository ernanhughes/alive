"""Replay the 14 load-bearing/pinned observatory mutations in temporary copies only."""

import argparse
import hashlib
import json
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CASES = [
    (
        "O1",
        "O1 Pi run must belong to this instance",
        "        and pi.instance_id == kernel.instance_id\n",
        "",
        "tests/test_workflow_observatory_identity.py::test_b_identity_attacks_are_refused_server_side[pi_other_instance]",
    ),
    (
        "O2",
        "O2 Pi run reservation must equal the invocation",
        "        and pi.reservation_ref == call.id\n",
        "",
        "tests/test_workflow_observatory_identity.py::test_b_identity_attacks_are_refused_server_side[pi_pointer_from_other_run]",
    ),
    (
        "O3",
        "O3 invocation must name this run",
        '        and call.input_json.get("workflow_run_id") == run.id\n',
        "",
        "tests/test_workflow_observatory_identity.py::test_b_identity_attacks_are_refused_server_side[invocation_wrong_run]",
    ),
    (
        "O4",
        "O4 invocation must belong to the run's investigation",
        "        and call.investigation_id == run.investigation_id\n",
        "",
        "tests/test_workflow_observatory_identity.py::test_b_identity_attacks_are_refused_server_side[invocation_wrong_investigation]",
    ),
    (
        "O5",
        "O5 invocation must name this stage attempt",
        '        and call.input_json.get("workflow_stage_id") == stage.id\n',
        "",
        "tests/test_workflow_observatory.py::test_actual_pi_receipt_binding_and_deterministic_history",
    ),
    (
        "O6",
        "O6 Pi operation must equal the stage operation",
        "        and pi.operation == stage.operation\n",
        "",
        "tests/test_workflow_observatory_identity.py::test_b_identity_attacks_are_refused_server_side[pi_wrong_operation]",
    ),
    (
        "O9",
        "O9 Pi events scoped to attached Pi runs",
        "                            Event.correlation_id.in_(by_pi),\n",
        "                            Event.correlation_id.is_not(None),\n",
        "tests/test_workflow_observatory_identity.py::test_c_timeline_pagination_and_run_isolation",
    ),
    (
        "O11",
        "O11 stage result event must match recorded hash",
        '                        require(stage.output_ref == "event:" + event.id '
        "and valid_output)\n",
        "                        pass\n",
        "tests/test_workflow_observatory.py::test_corrupt_or_foreign_history_refused[result_hash]",
    ),
    (
        "O12",
        "O12 run must belong to this instance",
        "    require(run is not None and run.instance_id == kernel.instance_id)\n",
        "    require(run is not None)\n",
        "tests/test_workflow_observatory.py::test_corrupt_or_foreign_history_refused[owner]",
    ),
    (
        "O13",
        "O13 stored definition hash recomputed",
        "        and hash_of_stored(definition.definition_json) == run.definition_sha256\n",
        "",
        "tests/test_workflow_observatory_identity.py::test_b_identity_attacks_are_refused_server_side[definition_json_altered]",
    ),
    (
        "O15",
        "O15 cursor is exclusive (no duplicate)",
        "                    Event.sequence_number > after,\n",
        "                    Event.sequence_number >= after,\n",
        "tests/test_workflow_observatory.py::test_timeline_bounded_ordered_payload_redacted_and_no_effect",
    ),
    (
        "O16",
        "O16 page fetches one extra row",
        "                .limit(limit + 1)\n",
        "                .limit(limit)\n",
        "tests/test_workflow_observatory.py::test_timeline_bounded_ordered_payload_redacted_and_no_effect",
    ),
    (
        "O17",
        "O17 has_more reported",
        '"has_more": len(rows) > limit,',
        '"has_more": False,',
        "tests/test_workflow_observatory.py::test_timeline_bounded_ordered_payload_redacted_and_no_effect",
    ),
    (
        "O18",
        "O18 complete_transition_history honest",
        '"complete_transition_history": False,',
        '"complete_transition_history": True,',
        "tests/test_workflow_observatory.py::test_timeline_bounded_ordered_payload_redacted_and_no_effect",
    ),
]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--only", nargs="*")
    args = parser.parse_args()
    selected = [case for case in CASES if not args.only or case[0] in args.only]
    if not selected or args.only and set(args.only) - {c[0] for c in CASES}:
        parser.error("unknown or empty mutation selection")
    receipts, baselines = [], {}
    with tempfile.TemporaryDirectory(prefix="alive-observatory-mutations-") as directory:
        scratch = Path(directory)
        for name in ("alive", "tests", "scripts", "config", "fixtures", "migrations"):
            shutil.copytree(
                ROOT / name, scratch / name, ignore=shutil.ignore_patterns("__pycache__", "*.pyc")
            )
        for name in ("pyproject.toml", "alembic.ini"):
            shutil.copyfile(ROOT / name, scratch / name)
        target = scratch / "alive/workflows/observatory.py"
        original = target.read_text(encoding="utf-8")
        env = os.environ | {
            "PYTHONDONTWRITEBYTECODE": "1",
            "CI": "true",
            "ALIVE_META_API_KEY": "",
            "ALIVE_EMBEDDING_ENABLED": "false",
            "ALIVE_PI_RUNTIME_DIR": str(ROOT / "pi-runtime"),
        }
        for key, title, before, after, test in selected:
            assert original.count(before) == 1, (key, "pattern missing or ambiguous")
            command = [
                sys.executable,
                "-B",
                "-m",
                "pytest",
                "-q",
                "-p",
                "no:cacheprovider",
                "--tb=short",
                test,
            ]
            if test not in baselines:
                baseline = subprocess.run(
                    command, cwd=scratch, env=env, capture_output=True, text=True
                )
                assert baseline.returncode == 0, (
                    key,
                    "BASELINE_FAILED",
                    baseline.stdout,
                    baseline.stderr,
                )
                baselines[test] = "PASS"
            try:
                target.write_text(original.replace(before, after, 1), encoding="utf-8")
                changed = subprocess.run(
                    command, cwd=scratch, env=env, capture_output=True, text=True
                )
            finally:
                target.write_text(original, encoding="utf-8")
            killed = (
                changed.returncode == 1
                and "FAILED " + test in changed.stdout
                and ("AssertionError" in changed.stdout or "\nE   assert" in changed.stdout)
                and "ERROR at" not in changed.stdout
                and "ERROR collecting" not in changed.stdout
            )
            result = "KILLED" if killed else "SURVIVED" if changed.returncode == 0 else "INVALID"
            receipt = {
                "id": key,
                "mutation": title,
                "target": test,
                "baseline": "PASS",
                "result": result,
                "modified_guard": before.strip(),
                "replacement": after.strip(),
                "assertion": changed.stdout,
                "stderr": changed.stderr,
                "returncode": changed.returncode,
            }
            receipts.append(receipt)
            args.output.parent.mkdir(parents=True, exist_ok=True)
            args.output.write_text(
                json.dumps(
                    {
                        "source_sha256": hashlib.sha256(original.encode()).hexdigest(),
                        "mutants": receipts,
                    },
                    indent=2,
                )
                + "\n",
                encoding="utf-8",
            )
            print(f"{key} {result}: {test}", flush=True)
            assert killed, (key, result, changed.stdout, changed.stderr)
    print(f"PASS: {len(receipts)} killed; no invalid executions", flush=True)


if __name__ == "__main__":
    main()
