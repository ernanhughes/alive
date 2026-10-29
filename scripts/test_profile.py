"""ALIVE Test Intelligence — performance profiler (ALIVE-TEST-INTEL-01).

Repeatable measurement of the pytest suite: collection time, total wall-clock,
slowest tests/modules, plus static inventory of non-pytest qualification steps.
Writes docs/testing/ALIVE-TEST-PROFILE.md.

Usage:
    python scripts/test_profile.py
    python scripts/test_profile.py --output docs/testing/ALIVE-TEST-PROFILE.md
    python scripts/test_profile.py --durations 25 --full-per-file
    python scripts/test_profile.py --skip-pytest   # docs-only regeneration
"""

from __future__ import annotations

import argparse
import re
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_OUTPUT = ROOT / "docs" / "testing" / "ALIVE-TEST-PROFILE.md"

DUR_RE = re.compile(r"^(\d+\.\d+)s\s+\S+\s+(.+)$")


def sh(cmd: list[str], timeout: int = 1200) -> tuple[float, str, int]:
    start = time.monotonic()
    try:
        proc = subprocess.run(cmd, cwd=ROOT, capture_output=True, text=True, timeout=timeout)
        return time.monotonic() - start, proc.stdout + proc.stderr, proc.returncode
    except subprocess.TimeoutExpired as exc:
        out = (
            (exc.stdout or b"").decode(errors="replace")
            if isinstance(exc.stdout, bytes)
            else (exc.stdout or "")
        )
        return time.monotonic() - start, out + "\n[TIMEOUT]", 124


def parse_durations(output: str, limit: int) -> list[tuple[float, str]]:
    rows: list[tuple[float, str]] = []
    in_section = False
    for line in output.splitlines():
        if "slowest" in line.lower() and "duration" in line.lower():
            in_section = True
            continue
        if in_section:
            m = DUR_RE.match(line.strip())
            if m:
                rows.append((float(m.group(1)), m.group(2).strip()))
            elif line.strip().startswith("=") or "passed" in line or "failed" in line:
                if rows:
                    break
    rows.sort(reverse=True)
    return rows[:limit]


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", default=str(DEFAULT_OUTPUT))
    parser.add_argument("--durations", type=int, default=25)
    parser.add_argument(
        "--full-per-file",
        action="store_true",
        help="time each test module individually (slow, ~50 runs)",
    )
    parser.add_argument("--skip-pytest", action="store_true")
    parser.add_argument(
        "--import-log",
        default=None,
        help="parse durations/summary from an existing pytest output log "
        "instead of re-running the suite",
    )
    args = parser.parse_args(argv)

    test_files = sorted(p.relative_to(ROOT).as_posix() for p in (ROOT / "tests").glob("test_*.py"))
    n_collect = 0
    collect_s = 0.0
    total_s = 0.0
    summary = ""
    slow: list[tuple[float, str]] = []
    per_file: list[tuple[float, str]] = []

    if args.import_log:
        print(f"Importing measurements from {args.import_log} ...")
        full_out = Path(args.import_log).read_text(encoding="utf-8", errors="replace")
        m = re.search(r"(\d+) tests? collected", full_out)
        if m:
            n_collect = int(m.group(1))
        m = re.search(
            r"(\d+) passed(?:, (\d+) skipped)?(?:, (\d+) xfailed)?.*in ([\d.]+)s", full_out
        )
        if m:
            summary = m.group(0)
            total_s = float(m.group(4))
        collect_s, out, _ = sh(
            [sys.executable, "-m", "pytest", "--collect-only", "-q", "-p", "no:cacheprovider"]
        )
        m2 = re.search(r"(\d+) tests? collected", out)
        if m2 and not n_collect:
            n_collect = int(m2.group(1))
        slow = parse_durations(full_out, args.durations)
        print(f"  imported {len(slow)} slowest rows, wall={total_s:.1f}s")
    elif not args.skip_pytest:
        print("Profiling collection ...")
        collect_s, out, _ = sh(
            [sys.executable, "-m", "pytest", "--collect-only", "-q", "-p", "no:cacheprovider"]
        )
        m = re.search(r"(\d+) tests? collected", out)
        n_collect = int(m.group(1)) if m else 0
        print(f"  collected {n_collect} in {collect_s:.1f}s")
        print("Profiling full pytest run (this takes minutes) ...")
        total_s, full_out, code = sh(
            [
                sys.executable,
                "-m",
                "pytest",
                "-q",
                f"--durations={args.durations}",
                "--durations-min=0.2",
                "-p",
                "no:cacheprovider",
            ]
        )
        slow = parse_durations(full_out, args.durations)
        tail = [ln for ln in full_out.splitlines() if ln.strip()][-5:]
        summary = "\n".join(tail)
        print(f"  exit={code} wall={total_s:.1f}s slowest-rows={len(slow)}")
        if args.full_per_file:
            print("Timing each module individually ...")
            for tf in test_files:
                dt, _, _ = sh([sys.executable, "-m", "pytest", "-q", tf, "-p", "no:cacheprovider"])
                per_file.append((dt, tf))
                print(f"  {dt:7.1f}s {tf}")
            per_file.sort(reverse=True)

    # Static non-pytest inventory (measured separately where noted).
    non_pytest = [
        (
            "verify_archive.py x6 + verify_alive14 x3",
            "CI backend job",
            "not timed here; seconds each",
        ),
        (
            "dashboard: npm test (vitest) + 3x node --test + build",
            "CI dashboard job",
            "not timed here",
        ),
        (
            "first-contact postgresql + playwright chrome install",
            "CI first-contact job",
            "dominated by `playwright install --with-deps chrome` one-off download",
        ),
        ("hugo build + notebook03a/eval01 verify chain", "CI notebook job", "not timed here"),
        ("docker compose build", "docker tier", "cold build minutes; layer-cached rebuild faster"),
        ("alembic upgrade head + postgres health wait", "docker tier", "seconds once image cached"),
        ("scripts/docker-smoke-test.py (8 checks)", "docker tier", "~10-30s against healthy app"),
        ("compose.e2e.yaml isolated E2E (6 groups)", "docker tier", "~1-2 min against healthy app"),
    ]

    lines = [
        "# ALIVE Test Profile (ALIVE-TEST-INTEL-01)",
        "",
        "_Generated by `python scripts/test_profile.py`. Wall-clock measured once on this host; "
        "treat figures as representative, not a fleet average._",
        "",
        "## Summary",
        "",
        f"- Test files: {len(test_files)} (`tests/test_*.py`)",
        f"- Tests collected: {n_collect}",
        f"- Collection time: {collect_s:.1f}s",
        f"- Full pytest wall-clock: {total_s:.1f}s",
        f"- Full run tail: `{summary.splitlines()[-1] if summary else 'n/a'}`",
        "",
        "## Slowest tests (pytest --durations)",
        "",
    ]
    if slow:
        lines.append("| Rank | Duration | Test |")
        lines.append("| --- | --- | --- |")
        for i, (d, name) in enumerate(slow, 1):
            lines.append(f"| {i} | {d:.2f}s | `{name}` |")
        top5 = sum(d for d, _ in slow[:5])
        lines += [
            "",
            f"Top-5 slowest account for ~{top5:.1f}s of the {total_s:.1f}s wall-clock. "
            "Pareto: a small set of integration/regression modules dominates; "
            "the long tail of unit tests is individually cheap.",
            "",
        ]
    else:
        lines += ["(pytest timing skipped with --skip-pytest)", ""]
    if per_file:
        lines += [
            "## Slowest modules (isolated per-file wall-clock)",
            "",
            "| Rank | Wall-clock | Module |",
            "| --- | --- | --- |",
        ]
        for i, (d, name) in enumerate(per_file[:20], 1):
            lines.append(f"| {i} | {d:.1f}s | `{name}` |")
        lines.append("")
    lines += [
        "## Non-pytest qualification inventory (static; timed separately)",
        "",
        "| Step | Job/tier | Cost note |",
        "| --- | --- | --- |",
    ]
    for step, job, note in non_pytest:
        lines.append(f"| {step} | {job} | {note} |")
    lines += [
        "",
        "## Bottleneck read",
        "",
        "- Default suite is sqlite + mocked providers (see `tests/conftest.py`); "
        "no Docker/Postgres in the default path, so the full run is CPU-bound "
        "across many small tests plus a few heavy modules "
        "(`test_research_memory.py`, protocol/safety suites, subprocess-based "
        "`test_migrations.py`).",
        "- Fixture cost is per-test sqlite schema creation (`Base.metadata.create_all` "
        "per test via `client` fixture); candidate optimization: "
        "session/module-scoped immutable fixtures where isolation permits "
        "(not applied in this increment).",
        "- One-off costs (playwright browser install, docker image pull/build, hugo download) must "
        "not be confused with recurring test execution; CI caches and layer reuse cover them.",
        "- Per-test durations above are the authoritative slow-test evidence for this host.",
        "",
    ]
    out = Path(args.output)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text("\n".join(lines), encoding="utf-8")
    print(f"Wrote {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
