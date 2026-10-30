"""ALIVE-ARCH-01: production-experiment separation.

- Production modules must not import the frozen research package
  (``alive.experiment.*``) or the top-level ``experiments`` harness.
- Only the opt-in app factory (lazy import) and the harness overlay itself
  may reference ``alive.experiment``.
- The default production app must boot without experiment routes/runner.
"""

import ast
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]

# Files allowed to reference alive.experiment (harness + opt-in wiring + tests/scripts).
ALLOWED_PREFIXES = (
    "alive/experiment/",
    "alive/experiment_budget.py",
    "experiments/",
    "tests/",
    "scripts/",
    "archives/",
    "benchmarks/",
    "docs/",
    "evaluations/",
)
ALLOWED_FILES = {
    "alive/app.py",  # lazy, gated import inside create_app(include_experiments=True)
    "alive/governance/pricing.py",  # docstring mentions legacy home only
    "alive/governance/budgets.py",
    "alive/governance/hashing.py",
    "alive/governance/__init__.py",
}


def _imports_experiment_source(path: Path):
    try:
        tree = ast.parse(path.read_text(encoding="utf-8"))
    except (SyntaxError, UnicodeDecodeError):
        return []
    hits = []
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom) and node.module:
            if node.module == "alive.experiment" or node.module.startswith("alive.experiment."):
                hits.append(f"from {node.module} import ... (line {node.lineno})")
        elif isinstance(node, ast.Import):
            for alias in node.names:
                if alias.name == "alive.experiment" or alias.name.startswith("alive.experiment."):
                    hits.append(f"import {alias.name} (line {node.lineno})")
    # Docstrings/comments mentioning the legacy path are not dependencies;
    # only real imports count (handled above). Keep a raw-text guard for the
    # top-level harness package, which must never be imported by production.
    text = path.read_text(encoding="utf-8")
    if "from experiments" in text or "import experiments" in text:
        hits.append("references top-level experiments package")
    return hits


def test_production_does_not_import_research_harness():
    violations = []
    for path in sorted((REPO / "alive").rglob("*.py")):
        rel = path.relative_to(REPO).as_posix()
        if rel.startswith(ALLOWED_PREFIXES) or rel in ALLOWED_FILES:
            continue
        hits = _imports_experiment_source(path)
        if hits:
            violations.append(f"{rel}: {'; '.join(hits)}")
    assert not violations, (
        "ARCH-01 violation: production modules must not import alive.experiment "
        f"or experiments/: {violations}"
    )


def test_default_app_has_no_experiment_endpoints(bare_client):
    assert bare_client.get("/api/v1/experiments").status_code == 404
    assert bare_client.get("/api/v1/experiments/review-pack").status_code == 404
    spec = bare_client.get("/openapi.json").json()
    assert not any(path.startswith("/api/v1/experiments") for path in spec.get("paths", {}))


def test_governance_does_not_depend_on_harness():
    for module in [
        "alive.governance.pricing",
        "alive.governance.budgets",
        "alive.governance.hashing",
    ]:
        path = REPO / (module.replace(".", "/") + ".py")
        hits = _imports_experiment_source(path)
        assert not hits, f"{module} must not import the research harness: {hits}"


def test_governance_parity_with_legacy_helpers():
    from alive.experiment.metrics import price as legacy_price
    from alive.governance.budgets import (
        charged_micro_usd,
        check_spend,
        worst_micro_usd,
    )
    from alive.governance.hashing import file_hash as gov_hash
    from alive.governance.pricing import price as gov_price

    usage = {
        "prompt_tokens": 1000000,
        "completion_tokens": 1000000,
        "prompt_tokens_details": {"cached_tokens": 100000},
    }
    assert gov_price(usage) == legacy_price(usage)
    assert gov_price(None) is None
    assert worst_micro_usd(1000) == (1000 * 17 + 3) // 4
    ledger = [
        {"status": "validated", "usage": usage, "reserved_tokens": 10},
        {"status": "failed", "usage": None, "reserved_tokens": 100},
    ]
    assert charged_micro_usd(ledger) > 0
    checked = check_spend(ledger[:1], 10, cap=10**12)
    assert checked["ceiling_micro_usd"] == 10**12

    from alive.experiment.freeze import file_hash as legacy_hash

    assert gov_hash("pyproject.toml") == legacy_hash("pyproject.toml")
