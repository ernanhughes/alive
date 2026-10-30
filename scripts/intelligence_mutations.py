"""Controlled test-only mutation probes. Reports individual killed/surviving mutations."""

import json
import os
import subprocess
import sys

PROBES = {
    "trust": "test_untrusted_observer_self_certification",
    "payload": "test_reward_substitution",
    "frozen": "test_complete_restart_replay_and_read_only_api",
    "update": "test_complete_restart_replay_and_read_only_api",
    "workflow": "test_feedback_revalidates_workflow_before_learning[context]",
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
            f"tests/test_intelligence_durable.py::{test}",
            "--tb=short",
        ]
        baseline = subprocess.run(
            command, capture_output=True, text=True, env=os.environ | {"ALIVE_INT02_MUTATION": ""}
        )
        assert baseline.returncode == 0, baseline.stdout + baseline.stderr
        changed = subprocess.run(
            command,
            capture_output=True,
            text=True,
            env=os.environ | {"ALIVE_INT02_MUTATION": mutation},
        )
        # Only assertion failures count as killed; collection/setup failures are not evidence.
        killed = (
            changed.returncode == 1
            and ("FAILED" in changed.stdout)
            and "ERROR at" not in changed.stdout
        )
        results.append(
            {
                "mutation": mutation,
                "baseline": "PASS",
                "result": "KILLED" if killed else "SURVIVED_OR_INVALID",
                "test": test,
                "exit_code": changed.returncode,
                "receipt": changed.stdout[-2200:],
            }
        )
    print(json.dumps(results, indent=2))
    return 0 if all(r["result"] == "KILLED" for r in results) else 1


if __name__ == "__main__":
    raise SystemExit(main())
