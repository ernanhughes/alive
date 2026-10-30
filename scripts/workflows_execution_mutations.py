"""Ten opt-in, reversible runtime guard mutations. No application mutation switch."""

import json
import os
import re
import subprocess
import sys

E = "test_workflow_execution.py::"
A = "test_workflow_authority.py::"

PROBES = {
    "dispatch_fence": "test_workflow_cancellation.py::"
    "test_revocation_after_reservation_is_fenced_before_real_pi_upstream",
    "operation": E + "test_admission_is_separate_from_definition_or_bearer[operation]",
    "hash": E + "test_changes_after_admission_fail_closed_and_release_governor[definition]",
    "claim": E + "test_independent_run_claims_execute_once",
    "budget": E + "test_admission_is_separate_from_definition_or_bearer[budget]",
    "admission": A + "test_bad_model_owner_has_no_dispatch_or_reservation",
    "pi_success": A + "test_process_exit_or_incomplete_receipt_cannot_complete_stage[unknown]",
    "ambiguity": A + "test_restart_reconciles_ambiguous_stage_without_dispatch",
    "output": A + "test_declared_output_is_enforced_before_success[extra]",
    "evidence": A + "test_source_authorization_is_checked_before_run_creation",
    "replay": E + "test_deterministic_procedure_records_real_artifact_and_zero_learning",
}


def main():
    results = []
    for mutation, test in PROBES.items():
        command = [
            sys.executable,
            "-B",
            "-m",
            "pytest",
            "-q",
            "-p",
            "no:cacheprovider",
            "-p",
            "tests.workflow_mutations",
            "tests/" + test,
            "--tb=short",
        ]
        baseline = subprocess.run(
            command,
            capture_output=True,
            text=True,
            env=os.environ | {"ALIVE_PI02B_MUTATION": "", "PYTHONDONTWRITEBYTECODE": "1"},
        )
        if baseline.returncode:
            print(baseline.stdout + baseline.stderr, file=sys.stderr)
            raise RuntimeError("Mutation baseline failed: " + mutation)
        changed = subprocess.run(
            command,
            capture_output=True,
            text=True,
            env=os.environ | {"ALIVE_PI02B_MUTATION": mutation, "PYTHONDONTWRITEBYTECODE": "1"},
        )
        killed = (
            changed.returncode == 1
            and "FAILED" in changed.stdout
            and "ERROR at" not in changed.stdout
            and "ERROR collecting" not in changed.stdout
            and (
                "AssertionError" in changed.stdout
                or "DID NOT RAISE" in changed.stdout
                or re.search(r"^E\s+assert\b", changed.stdout, re.M)
            )
        )
        results.append(
            {
                "mutation": mutation,
                "baseline": "PASS",
                "test": test,
                "result": "KILLED" if killed else "SURVIVED_OR_INVALID",
                "exit_code": changed.returncode,
                "failed_assertion": changed.stdout[-3200:],
            }
        )
    print(json.dumps(results, indent=2))
    return 0 if all(row["result"] == "KILLED" for row in results) else 1


if __name__ == "__main__":
    raise SystemExit(main())
