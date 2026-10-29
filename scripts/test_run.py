"""ALIVE Test Intelligence — unified test runner (ALIVE-TEST-INTEL-01).

Thin wrapper over scripts/test_select.py. Selects tests for a mode,
runs pytest, prints a testing decision receipt, and optionally writes
a machine-readable report. Never presents a subset as full qualification.

Usage:
    python scripts/test_run.py --mode quick        # default developer command
    python scripts/test_run.py --mode affected --explain
    python scripts/test_run.py --mode full
    python scripts/test_run.py --mode docker --dry-run
    python scripts/test_run.py --mode affected --report receipts/receipt.json
    python scripts/test_run.py --mode quick tests/test_transport.py  # explicit targets
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
import test_select  # noqa: E402

DOCKER_COMMANDS = [
    "docker compose build",
    "docker compose --env-file .env up -d db (wait healthy)",
    "alembic upgrade head (fresh migration check)",
    "python scripts/docker-smoke-test.py",
    "docker compose -f compose.e2e.yaml run --rm e2e (isolated E2E, 6 groups)",
]

NON_PYTEST_FULL = [
    "npm test (dashboard vitest)",
    "node --test tests/extension-*.test.cjs",
    "python scripts/verify_archive.py archives/ALIVE-14-R*",
    "python scripts/verify_alive14_protocol.py (+r2/r3)",
    "hugo --source site + notebook03a/eval01 verify (notebook CI job)",
    "npx playwright test (dashboard/e2e, release-gated)",
]


def build_pytest_cmd(selected: list[str], extra: list[str]) -> list[str]:
    return [sys.executable, "-m", "pytest", "-q", *selected, *extra]


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--mode", choices=test_select.MODES, default="quick")
    parser.add_argument("--base", default="origin/main")
    parser.add_argument("--explain", action="store_true")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--report", default=None, help="write JSON receipt to PATH")
    parser.add_argument("--changed", nargs="*", default=None)
    parser.add_argument("targets", nargs="*", help="explicit pytest targets (override selection)")
    parser.add_argument(
        "--pytest-args", nargs="*", default=[], help="extra args appended to pytest"
    )
    args = parser.parse_args(argv)

    if args.changed is not None:
        changed = sorted(args.changed)
        origins = {c: "override --changed" for c in changed}
    else:
        changed, origins = test_select.changed_files(args.base)

    if args.targets:
        selected = list(args.targets)
        reasons = {t: ["explicit target from command line"] for t in selected}
        meta: dict[str, object] = {"explicit_targets": True}
    else:
        selected, reasons, meta = test_select.select(changed, args.mode, origins)
    _, _, all_tests = test_select.build_indexes()
    not_selected = [t for t in all_tests if t not in set(selected)]

    cmd = build_pytest_cmd(selected, args.pytest_args)
    if args.mode == "docker" and not args.targets:
        print("Docker qualification = pytest subset + container workflow:")
        for step in DOCKER_COMMANDS:
            print(f"  - {step}")

    print(f"\nALIVE test run — mode={args.mode} base={args.base}")
    print(f"Changed: {len(changed)} files; selected {len(selected)}/{len(all_tests)} test files")
    if args.explain:
        for tf in selected:
            print(f"  {tf}")
            for r in reasons.get(tf, []):
                print(f"    - {r}")
    if meta.get("docker_required") and args.mode != "docker":
        print("Deployment-sensitive change: run --mode docker before release qualification.")
    print(f"Command: {' '.join(cmd)}")
    if args.dry_run:
        print("Dry run: not executing.")
        elapsed = 0.0
        code, out_tail = 0, "(dry run)"
    else:
        start = time.monotonic()
        proc = subprocess.run(cmd, cwd=ROOT, capture_output=True, text=True)
        elapsed = time.monotonic() - start
        code = proc.returncode
        sys.stdout.write(proc.stdout[-6000:] if len(proc.stdout) > 6000 else proc.stdout)
        sys.stderr.write(proc.stderr[-3000:] if len(proc.stderr) > 3000 else proc.stderr)
        out_tail = (
            (proc.stdout.strip().splitlines() or [""])[-1][:500] if proc.stdout.strip() else ""
        )

    status = "passed" if code == 0 else ("dry-run" if args.dry_run else "failed")
    receipt = {
        "tool": "ALIVE Test Intelligence",
        "mode": args.mode,
        "status": status,
        "selected": len(selected),
        "not_selected": len(not_selected),
        "elapsed_s": round(elapsed, 1),
        "selection": args.mode.upper(),
        "changed": changed,
        "selected_files": selected,
        "reasons": reasons,
        "meta": meta,
        "pytest_tail": out_tail,
        "disclaimer": (
            "subset selection is not equivalent to a full-suite pass; "
            "full-suite qualification still required before merge"
            if args.mode in ("quick", "affected")
            else "authoritative qualification tier for its scope"
        ),
        "timestamp_utc": datetime.now(timezone.utc).isoformat(),
    }
    if args.mode in ("quick", "affected"):
        receipt["full_suite_still_required"] = True
    if args.report:
        out = Path(args.report)
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(json.dumps(receipt, indent=2), encoding="utf-8")
        print(f"Report written: {out}")

    # Testing decision receipt (illustrative format from ALIVE-TEST-INTEL-01).
    print("\nALIVE Test Intelligence")
    if args.dry_run:
        print("Selected tests listed (not executed)")
    else:
        print(f"Selected tests {status}")
    print(f"Selected # {len(selected)}")
    print(f"Not selected # {len(not_selected)}")
    print(f"Elapsed # {elapsed:.1f}s")
    print(f"Selection: {args.mode.upper()}")
    for tf in selected[:8]:
        print(f"- {tf}")
    if len(selected) > 8:
        print(f"- ... and {len(selected) - 8} more")
    if args.mode in ("quick", "affected"):
        print(
            "Docker qualification not executed"
            if args.mode == "quick"
            else "Docker qualification not executed (run --mode docker if deployment-sensitive)"
        )
        print("Full-suite qualification still required before merge")
    elif args.mode == "full":
        print("Non-pytest gates still required in CI: " + "; ".join(NON_PYTEST_FULL[:3]) + " ...")
    elif args.mode == "docker":
        print("Container workflow: " + "; ".join(DOCKER_COMMANDS[:2]) + " ...")
    return code


if __name__ == "__main__":
    raise SystemExit(main())
