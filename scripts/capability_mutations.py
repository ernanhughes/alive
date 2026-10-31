"""Replay PI-03A capability-governance mutations in a temporary copy of the repository only.

Each mutant weakens exactly one guard. It is KILLED only if the named behavioural test passes on
the baseline, then fails with a test failure (not a collection, setup or syntax error) on the
mutant. SURVIVED mutants are reported honestly and are never counted as kills.
"""

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
REG = "alive/capabilities/registry.py"
EXE = "alive/capabilities/execution.py"
REPO = "alive/capabilities/repository.py"
BND = "alive/capabilities/bindings.py"
RUN = "alive/workflows/runner.py"
E2E = "tests/test_capability_repository_execution.py::"
CONTRACT = "tests/test_capability_contract_enforcement.py::"
REGISTRY = "tests/test_capability_registry.py"
READER = "tests/test_capability_repository.py::"
TIMEOUT_TEST = CONTRACT + "test_stage_may_not_exceed_the_capability_timeout_or_pin_another_hash"

# id, title, file, guard text (must occur exactly once), weakened text, behavioural test
CASES = [
    (
        # A changed manifest is refused by three independent checks: the identity compare at
        # recheck, the identity compare at the grant check, and the policy hash (which embeds the
        # identity). Removing any one or two is an equivalent mutant (defence in depth), so all
        # three are removed together.
        "C1",
        "changed manifest identity refused at recheck, grant check and policy hash (compound)",
        [REG, REG],
        [
            "if not cap.executable or cap.identity != identity:",
            '            grant["identity"] != expected["identity"]\n'
            '            or grant["policy_sha256"] != expected["policy_sha256"]\n',
        ],
        ["if not cap.executable:", "            False\n"],
        E2E
        + "test_pinned_identity_refuses_a_changed_or_disabled_catalogue_but_history_survives"
        + "[tampered_manifest]",
    ),
    (
        "C2",
        "owner grant must carry the current configuration (policy) hash",
        REG,
        '            or grant["policy_sha256"] != expected["policy_sha256"]\n',
        "",
        E2E + "test_configuration_loosened_after_the_grant_is_not_silently_accepted",
    ),
    (
        "C3",
        "owner grant permissions must equal the declaration",
        REG,
        'if grant["permissions"] != expected["permissions"]:',
        "if False:",
        CONTRACT + "test_grant_cannot_change_permissions_or_widen_limits",
    ),
    (
        "C4",
        "owner grant cannot widen a capability limit",
        REG,
        "if type(value) is not int or not minimum <= value <= ceiling:",
        "if type(value) is not int:",
        CONTRACT + "test_grant_cannot_change_permissions_or_widen_limits",
    ),
    (
        "C5",
        "manifest permissions cannot exceed the implementation ceiling",
        REG,
        "not requested <= impl.permission_ceiling\n",
        "False\n",
        REGISTRY,
    ),
    (
        "C6",
        "deployment configuration cannot widen a manifest limit",
        REG,
        "if not minimum <= value <= effective[field]:",
        "if False:",
        CONTRACT + "test_deployment_configuration_may_narrow_but_never_widen_a_manifest_limit",
    ),
    (
        "C7",
        "unavailable/disabled capability must not resolve an adapter",
        REG,
        '        if not cap.executable:\n            raise ValueError("capability unavailable")',
        '        if False:\n            raise ValueError("capability unavailable")',
        REGISTRY,
    ),
    (
        "C8",
        "stage cannot exceed the capability timeout",
        REG,
        'or stage.limits.timeout_seconds > m["execution"]["timeout_seconds"]',
        "or False",
        TIMEOUT_TEST,
    ),
    (
        "C9",
        "stage-pinned manifest hash must match",
        REG,
        "if requested_hash and requested_hash != cap.manifest_sha256:",
        "if False:",
        TIMEOUT_TEST,
    ),
    (
        "C10",
        "output must match the exact output contract",
        EXE,
        '    validate(result.output, cap.manifest["outputs"])\n',
        "    pass\n",
        CONTRACT + "test_output_outside_the_declared_contract_is_refused",
    ),
    (
        "C11",
        "output size ceiling",
        EXE,
        'require(len(blob) <= grant["limits"]["max_output_bytes"], "capability_output_limit")',
        "pass",
        CONTRACT + "test_output_size_ceiling_and_result_type_are_enforced",
    ),
    (
        "C12",
        "input must match the exact input contract",
        EXE,
        '    validate(context.inputs, manifest["inputs"])\n',
        "    pass\n",
        CONTRACT + "test_input_outside_the_declared_contract_is_refused_before_invocation",
    ),
    (
        "C13",
        "writer permission needed for an artifact",
        EXE,
        'result.artifact is None or grant["permissions"]["persistence"] == "workflow_result"',
        "True",
        CONTRACT + "test_a_capability_without_the_writer_permission_cannot_return_an_artifact",
    ),
    (
        "C14",
        "reader snapshot hash must equal the owner-approved hash",
        REPO,
        'and resources["snapshot_sha256"] == snapshot.sha256,',
        ",",
        READER + "test_reader_requires_exact_owner_scope[hash]",
    ),
    (
        "C15",
        "requested paths must equal the owner-approved paths",
        REPO,
        'and sorted(names) == resources["paths"],',
        ",",
        READER + "test_reader_requires_exact_owner_scope[paths]",
    ),
    (
        "C16",
        "hardlink aliases are refused",
        REPO,
        'require(before.st_nlink == 1, "repository_hardlink_refused")',
        "pass",
        READER + "test_hardlink_cannot_alias_an_unapproved_file",
    ),
    (
        "C17",
        "secret and ignored paths are never opened",
        REPO,
        "if _ignored(name, patterns):",
        "if False:",
        READER + "test_secret_and_ignored_paths_are_never_opened",
    ),
    (
        "C18",
        "binding hash in the owner grant must equal the retained binding",
        BND,
        "grant.capability_binding_sha256 == row.snapshot_sha256",
        "True",
        E2E + "test_execution_is_refused_without_exact_capability_authority[wrong_hash]",
    ),
    (
        "C19",
        "runner requires an executable capability",
        RUN,
        "registry.get(stage.operation, stage.capability_version).executable\n",
        "True\n",
        CONTRACT + "test_runner_checks_the_pinned_version_not_merely_the_latest",
    ),
]


def run(command, scratch, env):
    return subprocess.run(command, cwd=scratch, env=env, capture_output=True, text=True)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--only", nargs="*", help="mutant ids, for example C1 C10")
    parser.add_argument(
        "--output", type=Path, default=ROOT / "docs/capabilities/validation/mutations.json"
    )
    parser.add_argument(
        "--merge", action="store_true", help="replace only the selected receipts in --output"
    )
    args = parser.parse_args()
    selected = [c for c in CASES if not args.only or c[0] in args.only]
    if not selected:
        parser.error("unknown or empty mutation selection")
    receipts, baselines = [], {}
    kept = []
    if args.merge and args.output.exists():
        kept = [
            r
            for r in json.loads(args.output.read_text(encoding="utf-8"))["mutants"]
            if r["id"] not in {c[0] for c in selected}
        ]
    with tempfile.TemporaryDirectory(prefix="alive-capability-mutations-") as directory:
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
            "ALIVE_EMBEDDING_ENABLED": "false",
            "ALIVE_PI_RUNTIME_DIR": str(ROOT / "pi-runtime"),
        }
        for key, title, path, before, after, test in selected:
            # A compound mutant supplies parallel lists; a simple one a single file and guard.
            paths, befores, afters = (
                (path, before, after) if isinstance(path, list) else ([path], [before], [after])
            )
            targets = [scratch / p for p in paths]
            originals = {t: t.read_text(encoding="utf-8") for t in targets}
            for t, b in zip(targets, befores, strict=True):
                assert originals[t].count(b) == 1, (key, "pattern missing or ambiguous")
            original = originals[targets[0]]
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
                baseline = run(command, scratch, env)
                assert baseline.returncode == 0, (key, "BASELINE_FAILED", baseline.stdout)
                baselines[test] = "PASS"
            try:
                for t, b, a in zip(targets, befores, afters, strict=True):
                    t.write_text(t.read_text(encoding="utf-8").replace(b, a, 1), encoding="utf-8")
                changed = run(command, scratch, env)
            finally:
                for t, text in originals.items():
                    t.write_text(text, encoding="utf-8")
            out = changed.stdout
            valid = (
                changed.returncode == 1
                and "FAILED " in out
                and "ERROR at" not in out
                and "ERROR collecting" not in out
                and "SyntaxError" not in out
            )
            result = "KILLED" if valid else "SURVIVED" if changed.returncode == 0 else "INVALID"
            receipts.append(
                {
                    "id": key,
                    "mutation": title,
                    "files": paths,
                    "target": test,
                    "baseline": "PASS",
                    "result": result,
                    "modified_guards": [b.strip() for b in befores],
                    "replacements": [a.strip() for a in afters],
                    "assertion": out[-1500:],
                    "returncode": changed.returncode,
                    "source_sha256": hashlib.sha256(original.encode()).hexdigest(),
                }
            )
            args.output.parent.mkdir(parents=True, exist_ok=True)
            order = {c[0]: i for i, c in enumerate(CASES)}
            merged = sorted([*kept, *receipts], key=lambda r: order[r["id"]])
            args.output.write_text(
                json.dumps({"mutants": merged}, indent=2) + "\n", encoding="utf-8"
            )
            print(f"{key} {result}: {test}", flush=True)
    everything = [*kept, *receipts]
    counts = {
        r: sum(x["result"] == r for x in everything) for r in ("KILLED", "SURVIVED", "INVALID")
    }
    print(counts, flush=True)
    sys.exit(1 if counts["INVALID"] else 0)


if __name__ == "__main__":
    main()
