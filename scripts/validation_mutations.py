"""Targeted PI-03C guards, each tested in a new immutable git archive copy."""

import argparse
import gzip
import hashlib
import io
import json
import os
import subprocess
import sys
import tarfile
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ADAPTER = "alive/validation/adapters.py"
UNIT = "tests/test_validation_capabilities.py::"
MUTANTS = [
    (
        "file-limit",
        ADAPTER,
        'len(items) <= ctx.limits["max_files"]',
        "True",
        UNIT + "test_lowered_repository_file_ceiling_is_enforced_with_a_live_control",
    ),
    (
        "source-scope",
        ADAPTER,
        "and batch.scoped_sha256 == source.scoped_sha256,",
        "and True,",
        UNIT + "test_source_substitution_is_refused_after_successful_control[scoped_sha256]",
    ),
    (
        "item-hash",
        ADAPTER,
        "sha(text) == digest",
        "True",
        UNIT + "test_capture_item_hash_and_bounded_observation_are_not_silently_truncated",
    ),
    (
        "reference-id",
        ADAPTER,
        'if item is None or ref.id != item["id"]',
        "if item is None",
        UNIT + "test_each_reference_failure_is_classified",
    ),
    (
        "locator-range",
        "alive/analysis/validation.py",
        "    if not 1 <= evidence.line_start <= evidence.line_end <= len(lines):",
        "    if False:",
        UNIT + "test_locator_bounds_newlines_exact_quotes_and_unsupported_pages",
    ),
    (
        "quote",
        ADAPTER,
        "if locator.quote and newline(locator.quote) not in selected:",
        "if False:",
        UNIT + "test_locator_bounds_newlines_exact_quotes_and_unsupported_pages",
    ),
    (
        "semantics",
        ADAPTER,
        '"semantic_support": "unverified"',
        '"semantic_support": "verified"',
        UNIT + "test_a_false_claim_with_a_valid_citation_remains_unverified",
    ),
    (
        "trusted-dependency",
        ADAPTER,
        'entry["implementation"] in implementations',
        "True",
        UNIT + "test_composer_and_comparison_refuse_self_certification_with_live_controls",
    ),
    (
        "byte-limit",
        ADAPTER,
        'len(source.blob) <= ctx.limits["max_source_bytes"]',
        "True",
        UNIT + "test_contract_and_source_byte_limits_cannot_be_widened",
    ),
    (
        "implicit-compatibility",
        "alive/capabilities/registry.py",
        'version = "1.0.0"',
        "version = None",
        "tests/test_validation_workflows.py::test_old_implicit_reference_definition_keeps_its_original_implementation",
    ),
]


def run(mutant, baseline, output):
    identifier, relative, old, new, test = mutant
    receipt = {"id": identifier, "baseline": baseline, "test": test, "status": "invalid"}
    with tempfile.TemporaryDirectory(prefix="alive-pi03c-mutation-") as directory:
        archive = subprocess.check_output(["git", "archive", baseline], cwd=ROOT)
        with tarfile.open(fileobj=io.BytesIO(archive)) as tree:
            tree.extractall(directory, filter="data")
        target = Path(directory) / relative
        text = target.read_text(encoding="utf-8")
        if text.count(old) != 1:
            return receipt | {"reason": "mutation pattern did not match exactly once"}
        target.write_text(text.replace(old, new, 1), encoding="utf-8")
        env = os.environ | {"PYTHONPATH": directory}
        for key in (
            "ALIVE_TEST_REAL_PI",
            "ALIVE_TEST_ANALYSIS_POSTGRES_URL",
            "ALIVE_TEST_ANALYSIS_BROWSER",
        ):
            env.pop(key, None)
        command = [sys.executable, "-m", "pytest", "-q", "-x", "-p", "no:cacheprovider", test]
        result = subprocess.run(command, cwd=directory, env=env, capture_output=True, text=True)
        transcript = result.stdout + result.stderr
        logs = output.parent / (output.stem + "-logs")
        logs.mkdir(parents=True, exist_ok=True)
        (logs / (identifier + ".txt.gz")).write_bytes(gzip.compress(transcript.encode(), mtime=0))
        failures = [
            line for line in transcript.splitlines() if line.startswith(("FAILED", "ERROR"))
        ]
        status = (
            "survived"
            if result.returncode == 0
            else "killed"
            if result.returncode == 1
            and failures
            and not any(line.startswith("ERROR") for line in failures)
            and ("AssertionError" in transcript or "Failed: DID NOT RAISE" in transcript)
            else "invalid"
        )
        return receipt | {
            "status": status,
            "returncode": result.returncode,
            "command": command,
            "failure": failures,
            "log": logs.name + "/" + identifier + ".txt.gz",
        }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--baseline", default="HEAD")
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("ids", nargs="*")
    args = parser.parse_args()
    if set(args.ids) - {m[0] for m in MUTANTS}:
        parser.error("unknown mutant id")
    baseline = subprocess.check_output(
        ["git", "rev-parse", args.baseline + "^{commit}"], cwd=ROOT, text=True
    ).strip()
    paths = {ROOT / m[1] for m in MUTANTS}
    before = {str(path): hashlib.sha256(path.read_bytes()).hexdigest() for path in paths}
    args.output.parent.mkdir(parents=True, exist_ok=True)
    receipts = []
    for mutant in MUTANTS:
        if not args.ids or mutant[0] in args.ids:
            receipt = run(mutant, baseline, args.output)
            receipts.append(receipt)
            args.output.write_text(json.dumps(receipts, indent=2) + "\n", encoding="utf-8")
            print(receipt["id"], receipt["status"], flush=True)
    assert before == {str(path): hashlib.sha256(path.read_bytes()).hexdigest() for path in paths}, (
        "production sources changed"
    )


if __name__ == "__main__":
    main()
