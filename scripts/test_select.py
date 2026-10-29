"""ALIVE Test Intelligence — change-aware test selector (ALIVE-TEST-INTEL-01).

Conservative static selector: maps changed files to pytest test files using
import relationships plus risk-based trigger rules. Never claims full-suite
equivalence for a subset; use --explain to see why each test was selected.

Usage:
    python scripts/test_select.py --mode quick|affected|full|docker [--base origin/main] [--explain]
    python scripts/test_select.py --mode affected --json
    python scripts/test_select.py --mode quick --files-only
"""

from __future__ import annotations

import argparse
import ast
import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TESTS_DIR = ROOT / "tests"
ALIVE_DIR = ROOT / "alive"
SCRIPTS_DIR = ROOT / "scripts"

MODES = ("quick", "affected", "full", "docker")

# Tiny always-run smoke + static safety net. Fast, no services required.
ALWAYS_FILES = [
    "tests/test_transport.py",
    "tests/test_docker_config.py",
]

# High-risk core: any change here widens selection to the full suite.
CORE_BROAD_FILES = {
    "alive/app.py",
    "alive/config.py",
    "alive/db.py",
    "alive/models.py",
    "tests/conftest.py",
    "pyproject.toml",
    "alembic.ini",
}

# Risk trigger: path prefix/substring -> (test file substrings, reason).
RISK_RULES: list[tuple[str, list[str], str]] = [
    (
        "migrations/",
        [
            "test_migrations",
            "test_claim_runtime",
            "test_recovery_budgets",
            "test_history_diagnostic",
            "test_transport",
        ],
        "database migration change requires migration + persistence tests",
    ),
    (
        "alive/models.py",
        ["test_migrations", "test_claim_runtime", "test_transport"],
        "ORM model change requires migration + persistence tests",
    ),
    (
        "alive/db.py",
        ["test_migrations", "test_claim_runtime", "test_transport"],
        "database layer change requires persistence tests",
    ),
    (
        "alive/browser.py",
        ["test_browser_provenance", "test_living", "test_demo_live_01"],
        "browser layer change requires provenance + living tests",
    ),
    (
        "dashboard/",
        ["test_demo_live_01", "test_browser_provenance", "test_transport"],
        "frontend change requires UI smoke + provenance tests (vitest runs in full/docker)",
    ),
    (
        "extension/",
        ["test_browser_provenance", "test_demo_live_01"],
        "extension change requires provenance + demo tests (node --test runs in full/docker)",
    ),
    (
        "site/",
        ["test_notebook_01", "test_notebook03a"],
        "site/notebook change requires notebook tests",
    ),
    (
        "evaluations/",
        [
            "test_alive_eval01",
            "test_relevance_evaluation",
            "test_notebook02",
            "test_notebook03a",
            "test_experiment03",
            "test_experience_lab",
        ],
        "evaluation artifact adjacent change requires eval integrity tests",
    ),
    (
        "scripts/alive_eval01",
        ["test_alive_eval01"],
        "eval scorer change requires eval integrity tests",
    ),
    (
        "scripts/notebook",
        ["test_notebook_01", "test_notebook03a", "test_notebook02", "test_alive_eval01"],
        "notebook script change requires notebook + eval tests",
    ),
    (
        "Dockerfile",
        ["test_docker_config", "test_migrations", "test_transport"],
        "Dockerfile change requires container config + migration qualification (docker tier)",
    ),
    (
        "compose",
        ["test_docker_config", "test_transport"],
        "compose change requires container config qualification (docker tier)",
    ),
    (
        "docker/",
        ["test_docker_config", "test_transport"],
        "container entrypoint change requires config qualification (docker tier)",
    ),
    (
        "uv.lock",
        ["test_docker_config"],
        "dependency lockfile change requires container requalification",
    ),
    (
        "alive/living_policy.py",
        ["test_alive14r5_safety", "test_alive14r4", "test_alive14r5"],
        "safety policy change requires safety regression tests",
    ),
    (
        "alive/living.py",
        ["test_living", "test_alive14r5_safety"],
        "living runtime change requires living + safety tests",
    ),
    (
        "alive/cognition.py",
        ["test_cognition", "test_relevance", "test_agents"],
        "cognition change requires cognition + agent tests",
    ),
    ("alive/agents.py", ["test_agents"], "agent runner change requires agent tests"),
    (
        "alive/memory.py",
        ["test_claim_runtime", "test_recovery_budgets"],
        "memory layer change requires persistence tests",
    ),
    (
        "alive/claim",
        [
            "test_claim_validator_v2",
            "test_claim_comparison",
            "test_claim_review_attacks",
            "test_claim_runtime",
        ],
        "claim protocol change requires claim integrity tests",
    ),
    ("archives/", ["test_alive14r"], "frozen archive adjacent change requires protocol tests"),
    (
        "scripts/verify_alive14",
        ["test_alive14r"],
        "protocol verifier change requires protocol tests",
    ),
    (
        "scripts/verify_archive",
        ["test_alive14r"],
        "archive verifier change requires protocol tests",
    ),
    (
        "scripts/docker-e2e.py",
        ["test_transport", "test_docker_config"],
        "E2E runner change requires smoke + config tests (docker tier)",
    ),
    (
        "scripts/docker-smoke-test.py",
        ["test_transport", "test_docker_config"],
        "smoke runner change requires smoke + config tests (docker tier)",
    ),
    (
        "scripts/first_contact",
        ["test_demo_live_01", "test_browser_provenance"],
        "first-contact change requires demo + provenance tests",
    ),
    (
        "alive/research_memory.py",
        ["test_research_memory"],
        "research memory change requires its regression suite",
    ),
    (
        "alive/experiment",
        ["test_experiment03", "test_experiment_budget", "test_alive14r3_experiment"],
        "experiment change requires experiment + budget tests",
    ),
    ("alive/learning", ["test_learning"], "learning change requires learning tests"),
    (
        "alive/living_api.py",
        ["test_living", "test_transport"],
        "living API change requires living + transport tests",
    ),
    (
        "alive/cognitive_api.py",
        ["test_cognition", "test_transport"],
        "cognitive API change requires cognition + transport tests",
    ),
]


def _run_git(args: list[str]) -> str:
    try:
        out = subprocess.run(["git", *args], cwd=ROOT, capture_output=True, text=True, timeout=30)
        return out.stdout if out.returncode == 0 else ""
    except Exception:
        return ""


def changed_files(base: str) -> tuple[list[str], dict[str, str]]:
    """Return (sorted changed paths posix-relative, {path: origin}).

    Inspects committed range base...HEAD plus staged/unstaged/untracked work.
    Deleted files are included (conservative: dependents still selected).
    """
    found: dict[str, str] = {}
    diff_range = _run_git(["diff", "--name-only", f"{base}...HEAD", "--"])
    for line in diff_range.splitlines():
        p = line.strip()
        if p:
            found.setdefault(p, f"committed diff {base}...HEAD")
    for name, origin in (
        (["diff", "--name-only", "--"], "uncommitted working tree"),
        (["diff", "--name-only", "--cached", "--"], "staged changes"),
    ):
        for line in _run_git(name).splitlines():
            p = line.strip()
            if p:
                found.setdefault(p, origin)
    for line in _run_git(["ls-files", "--others", "--exclude-standard"]).splitlines():
        p = line.strip()
        if p:
            found.setdefault(p, "untracked file")
    return sorted(found), found


def _module_of(path: str) -> str | None:
    p = path.replace("\\", "/")
    if p.startswith("alive/") and p.endswith(".py"):
        return "alive." + p[len("alive/") : -len(".py")].replace("/", ".")
    if p.startswith("scripts/") and p.endswith(".py"):
        stem = p[len("scripts/") : -len(".py")]
        return "scripts." + stem.replace("/", ".")
    return None


def _imports_of(py_file: Path) -> set[str]:
    try:
        tree = ast.parse(py_file.read_text(encoding="utf-8"))
    except Exception:
        return set()
    mods: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for a in node.names:
                mods.add(
                    a.name.split(".")[0] + ("." + a.name.split(".")[1] if "." in a.name else "")
                )
                mods.add(a.name)
        elif isinstance(node, ast.ImportFrom) and node.module:
            mods.add(node.module)
    return mods


def build_indexes() -> tuple[dict[str, set[str]], dict[str, set[str]], list[str]]:
    """Return (test->source modules, source module->tests, all test files)."""
    test_files = sorted(
        str(p.relative_to(ROOT)).replace("\\", "/") for p in TESTS_DIR.glob("test_*.py")
    )
    test_imports: dict[str, set[str]] = {}
    for tf in test_files:
        test_imports[tf] = _imports_of(ROOT / tf)
    # source -> tests (direct import edge)
    source_to_tests: dict[str, set[str]] = {}
    for tf, mods in test_imports.items():
        for m in mods:
            source_to_tests.setdefault(m, set()).add(tf)
    # one-hop expansion: alive module internal imports (bar imports foo).
    # importers_of[foo] = modules that import foo; tests of those importers
    # are indirectly affected by a change to foo.
    importers_of: dict[str, set[str]] = {}
    for py in (
        list(ALIVE_DIR.glob("*.py"))
        + list((ALIVE_DIR / "experiment").glob("*.py"))
        + list((ALIVE_DIR / "learning").glob("*.py"))
    ):
        mod = _module_of(str(py.relative_to(ROOT)).replace("\\", "/"))
        if mod:
            for dep in _imports_of(py):
                importers_of.setdefault(dep, set()).add(mod)
    expanded: dict[str, set[str]] = {k: set(v) for k, v in source_to_tests.items()}
    for changed_mod, importers in importers_of.items():
        for importer in importers:
            for tf in source_to_tests.get(importer, set()):
                expanded.setdefault(changed_mod, set()).add(tf)
    return test_imports, expanded, test_files


def classify_changed(changed: list[str]) -> dict[str, str]:
    """Map each changed path to a category label for fallback decisions."""
    cats: dict[str, str] = {}
    for p in changed:
        q = p.replace("\\", "/")
        if q.startswith("docs/") or q.endswith(".md") or q.startswith("site/"):
            cats[p] = "docs"
        elif q.startswith("dashboard/") or q.startswith("extension/"):
            cats[p] = "frontend"
        elif q.startswith("migrations/") or q == "alembic.ini":
            cats[p] = "migration"
        elif (
            q in ("Dockerfile",)
            or "compose" in q
            or q.startswith("docker/")
            or q in ("uv.lock", "dashboard/package-lock.json")
        ):
            cats[p] = "deploy"
        elif q.startswith("evaluations/") or "eval" in q or q.startswith("scripts/notebook"):
            cats[p] = "evaluation"
        elif q.startswith("tests/"):
            cats[p] = "test"
        elif q.startswith("alive/") or q.startswith("scripts/"):
            cats[p] = "backend"
        elif q.startswith(".github/"):
            cats[p] = "ci"
        else:
            cats[p] = "unknown"
    return cats


def select(
    changed: list[str], mode: str, origins: dict[str, str] | None = None
) -> tuple[list[str], dict[str, list[str]], dict[str, object]]:
    """Select test files for mode. Returns (selected, reasons, meta)."""
    origins = origins or {}
    _, source_to_tests, all_tests = build_indexes()
    all_set = set(all_tests)
    selected: set[str] = set()
    reasons: dict[str, list[str]] = {}

    def add(tf: str, reason: str) -> None:
        if tf in all_set:
            selected.add(tf)
            reasons.setdefault(tf, [])
            if reason not in reasons[tf]:
                reasons[tf].append(reason)

    meta: dict[str, object] = {"fallback_full": False, "docker_required": False}
    cats = classify_changed(changed)
    changed_mods = {c: _module_of(c) for c in changed}

    # Docs-only fast path (unless executable docs/scripts changed).
    non_docs = [c for c in changed if cats.get(c) != "docs"]
    if changed and not non_docs:
        for tf in ALWAYS_FILES:
            add(tf, "always-run smoke/config safety net (docs-only change)")
        meta["note"] = "documentation-only change: minimal smoke selection"
        return sorted(selected), reasons, meta

    if mode == "full":
        for tf in all_tests:
            add(tf, "full mode: comprehensive qualification")
        return sorted(selected), reasons, meta

    # Import-based mapping (direct + one-hop importers).
    # Affected/docker use the full graph; quick stays bounded to
    # basename-token matches so the loop stays in seconds.
    if mode == "quick":
        for c in changed:
            mod = changed_mods.get(c)
            if mod:
                leaf = mod.split(".")[-1]
                stop = {"alive", "test", "api", "app", "r1", "r2", "v2"}
                tokens = {t for t in leaf.split("_") if len(t) > 2 and t not in stop}
                for tf in all_tests:
                    stem = Path(tf).stem[len("test_") :]
                    if leaf in stem or any(t in stem for t in tokens):
                        add(tf, f"quick: name-matched test for changed module {mod} (via {c})")
    else:
        for c in changed:
            mod = changed_mods.get(c)
            if mod and mod in source_to_tests:
                for tf in source_to_tests[mod]:
                    add(tf, f"imports changed module {mod} (via {c})")

    # Risk rules.
    for c in changed:
        q = c.replace("\\", "/")
        for prefix, patterns, reason in RISK_RULES:
            if q == prefix or q.startswith(prefix) or prefix in q:
                for pat in patterns:
                    for tf in all_tests:
                        if pat in tf:
                            add(tf, f"{reason} [{c}]")

    # Changed test files select themselves.
    for c in changed:
        q = c.replace("\\", "/")
        if q in all_set:
            add(q, "test file itself changed")

    # Conservative fallback triggers.
    unknown = [c for c in changed if cats.get(c) == "unknown"]
    core_hit = [c for c in changed if c.replace("\\", "/") in CORE_BROAD_FILES]
    deploy_hit = [c for c in changed if cats.get(c) == "deploy"]
    migration_hit = [c for c in changed if cats.get(c) == "migration"]
    ci_hit = [c for c in changed if cats.get(c) == "ci"]
    if deploy_hit:
        meta["docker_required"] = True
    if unknown or core_hit or ci_hit or len(changed) > 20 or not changed:
        meta["fallback_full"] = True
        if mode == "affected":
            for tf in all_tests:
                if tf not in selected:
                    add(
                        tf,
                        "conservative fallback: core/CI/unknown/broad change selects full suite"
                        + (
                            f" (trigger: {', '.join((unknown + core_hit + ci_hit)[:3])})"
                            if (unknown + core_hit + ci_hit)
                            else ""
                        ),
                    )
        elif mode == "quick":
            # quick stays bounded but records that full is still required.
            for tf in ALWAYS_FILES:
                add(tf, "always-run smoke/config safety net")
            meta["note"] = (
                "broad change detected; quick selection is bounded smoke only, "
                "full qualification still required"
            )
            return sorted(selected), reasons, meta

    if mode == "quick":
        # Bounded: always set + directly mapped (cap to keep feedback in seconds).
        quick = set(ALWAYS_FILES) & all_set
        mapped = [t for t in selected if t not in quick]
        # Prefer smallest meaningful slice: keep all direct import hits but cap risk-rule
        # expansion to files already mapped or ALWAYS to avoid minutes-long quick runs.
        for tf in ALWAYS_FILES:
            add(tf, "always-run smoke/config safety net")
        selected_q = set(quick) | set(mapped)
        # If nothing mapped, still return smoke net.
        selected = selected_q or (set(ALWAYS_FILES) & all_set)
        reasons = {k: v for k, v in reasons.items() if k in selected}
        if migration_hit or deploy_hit:
            meta["docker_required"] = True
    elif mode == "docker":
        for tf in ALWAYS_FILES:
            add(tf, "docker tier includes smoke/config safety net")
        for pat in (
            "test_migrations",
            "test_transport",
            "test_docker_config",
            "test_browser_provenance",
            "test_demo_live_01",
        ):
            for tf in all_tests:
                if pat in tf:
                    add(tf, "docker tier: deployment-relevant qualification subset")
        meta["docker_required"] = True
        meta["note"] = (
            "docker mode selects container-relevant pytest subset; full docker "
            "qualification also runs compose build + smoke/E2E scripts via test_run.py"
        )
    else:  # affected (non-fallback path)
        for tf in ALWAYS_FILES:
            add(tf, "always-run smoke/config safety net")
        if not selected:
            for tf in ALWAYS_FILES:
                add(tf, "no mapping found: conservative smoke net (widen to full if high-risk)")
            meta["note"] = "no module mapping; ran smoke net only — run --mode full before merge"

    if migration_hit or deploy_hit:
        meta["docker_required"] = True
    return sorted(selected), reasons, meta


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--mode", choices=MODES, default="affected")
    parser.add_argument("--base", default="origin/main")
    parser.add_argument("--explain", action="store_true")
    parser.add_argument("--json", action="store_true")
    parser.add_argument("--files-only", action="store_true")
    parser.add_argument(
        "--changed", nargs="*", default=None, help="override detected changed files (for testing)"
    )
    args = parser.parse_args(argv)

    if args.changed is not None:
        changed = sorted(args.changed)
        origins = {c: "override --changed" for c in changed}
    else:
        changed, origins = changed_files(args.base)
    selected, reasons, meta = select(changed, args.mode, origins)
    _, _, all_tests = build_indexes()

    if args.json:
        print(
            json.dumps(
                {
                    "mode": args.mode,
                    "base": args.base,
                    "changed": changed,
                    "origins": {c: origins.get(c, "") for c in changed},
                    "selected": selected,
                    "reasons": reasons,
                    "not_selected": [t for t in all_tests if t not in set(selected)],
                    "meta": meta,
                    "disclaimer": (
                        "subset selection, not equivalent to full-suite pass; "
                        "run --mode full before merge"
                    ),
                },
                indent=2,
            )
        )
        return 0
    if args.files_only:
        for tf in selected:
            print(tf)
        return 0
    print(f"ALIVE test selector — mode={args.mode} base={args.base}")
    print(f"Changed files ({len(changed)}):")
    for c in changed[:30]:
        print(f"  {c}  [{origins.get(c, '')}]")
    if len(changed) > 30:
        print(f"  ... and {len(changed) - 30} more")
    if not changed:
        print("  (no changes detected vs base; quick smoke net selected)")
    print(f"\nSelected {len(selected)}/{len(all_tests)} test files:")
    for tf in selected:
        print(f"  {tf}")
        if args.explain:
            for r in reasons.get(tf, []):
                print(f"    - {r}")
    if meta.get("fallback_full"):
        print("\nConservative fallback active: broader/full selection (see reasons).")
    if meta.get("docker_required"):
        print(
            "Deployment-sensitive change: docker qualification recommended "
            "(test_run.py --mode docker)."
        )
    if args.mode != "full":
        print("NOTE: subset selection is not a full-suite pass; run --mode full before merge.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
