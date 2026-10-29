# ALIVE-NOTEBOOK-03A-R2 — engineering and experimental-readiness report

Decisions:
**Engineering: READY_FOR_REVIEW. Research: READY_FOR_INDEPENDENT_ANNOTATION.
NOT READY FOR 03B.** No semantic performance is claimed. No model inference
was run.

## Delivery and provenance

- Base: `b9978da6bededa88b41f1b2ae939f80d488e0aec092b1bcd690bac5ad9a4434`
  (`origin/main`, PR #46 merged).
- Branch: `codex/alive-notebook-03a-r2-blind-protocol`.
- v1.4 (`evaluations/notebook03a/`, `scripts/notebook03a*.py`) and v1.5
  (`evaluations/notebook03a_r1/`, `scripts/notebook03a_r1*.py`) preserved
  byte-unchanged; `git diff` on those paths is empty and their freezes plus
  48 tests still pass.
- R2 implementation: `scripts/notebook03a_r2{,_protocol,_shortcut}.py`,
  `tests/test_notebook03a_r2.py` (21 tests), corpus
  `evaluations/notebook03a_r2/` (protocol v1.6, 66 neutral-question cases,
  decontaminated annotation package, sealed-holdout handoff contract),
  docs `ALIVE-NOTEBOOK-03A-R2-{DESIGN,PROTOCOL}.md` (this report is
  `...-REPORT.md`), `ALIVE-NOTEBOOK-03A-R2-NOTEBOOK02-DEPS.md`, validation
  under `docs/validation/alive-notebook-03a-r2/`, CI enforcement in
  `.github/workflows/ci.yml`.
- Commits are separated: (1) protocol/taxonomy amendment + corpus/package/
  specs + design/protocol docs; (2) scoring/controls/runner; (3) tests + CI;
  (4) evidence + this report. Full history preserved; results never
  rewritten to match thresholds.
- Local environment: Windows 11, Python 3.13.3, locked uv dependencies.
  `uv run pytest -q tests/test_notebook03a.py tests/test_notebook03a_r1.py
  tests/test_notebook03a_r2.py`: **69 passed** (30 + 18 + 21).
  `uv run ruff check` + `format --check` (alive/migrations/scripts/tests):
  **pass**. Hosted CI runs the same v1.6 steps after push (evidence pending
  hosted logs; local replay is deterministic).
- 03A-R2 execution: **0 model calls, 0 tokens, USD 0.00**. Core replay
  forbids Meta structured calls and embeddings. No production Core,
  Governor, approval, payment, migration, browser-permission,
  source-document, or archive code changed.

## What changed (v1.5 draft → v1.6 protocol)

- Validated flat threshold contract: every threshold typed, ranged,
  contradiction-checked; unknown keys rejected; zero defaults. The old
  nested file fails the new loader (regression-tested).
- Layered decision: engineering validity / public diagnostic (numbers
  only) / blind readiness / final verdict. Public scope can never yield
  `PROGRESS`; missing holdout, gold, comparators, or citation evidence
  yields `INCONCLUSIVE` naming the gap. D additionally requires D-vs-C
  and D-vs-S margins on both metrics; C is judged against S/A/B0, so
  the two verdicts differ structurally.
- Family-level paired bootstrap (seed 20261029, 1000 resamples, 95%
  intervals) over precomputed flags; 39 families; paired D-vs-S / D-vs-C
  differences; predeclared underpowered rule (forces `INCONCLUSIVE`).
- Shortcut-control-v2.0: honest lexical/surface/inference features,
  dev-tuned, frozen pre-evaluation with version/params/code hash in replay
  output. v1.0 preserved and still replayed for regression.
- Decontaminated annotation package: opaque handles (mapping
  implementer-side only), no family handles, no splits, no gold field
  values, no exact rationale/dev-description strings, generic toy examples,
  self-containment check; leakage audit passes R2 and fails R1 (68
  findings). Residual risk documented: repository access defeats renaming.
- Neutral uniform question on all 66 tasks (transformation recorded with
  affected fingerprints); question-non-predictiveness tested.
- Citation gate (v3): exact spans + full required recall + precision floor
  0.2; failures are misleading advances. Six-scenario tests.
- Adjudication plan mechanism (multi-label acceptance, ambiguity flags,
  predeclared category-accuracy exclusions, disagreement records, 2
  reviewers + adjudicator); sealed-holdout handoff contract
  (`HOLDOUT_PENDING` — no package supplied).

## Replayed baselines (v1.6, gated)

Core A/B/B0 replayed via allowlisted fixture URLs in isolated SQLite;
S (v1.0) and V (v2.0) offline. C/D NOT RUN.

| Arm | Scored | Gated ret. | Gated mis. | Cat acc | Gate pass |
|---|---:|---:|---:|---:|---:|
| A lexical | 50 | 0.000 | 0.240 | 0.100 | n/a |
| B integrity | 50 | 0.000 | 0.000 | 0.100 | n/a |
| B0 abstain | 64 | 0.000 | 0.000 | 0.156 | n/a |
| S surface v1 | 64 | 0.489 | 0.219 | 0.609 | 0.976 |
| V shortcut v2 | 64 | 0.533 | 0.250 | 0.609 | 0.878 |

Stratified gated retention / misleading:

| Stratum | S | V |
|---|---|---|
| authentic (n=12) | 0.00 / 0.42 | 0.00 / 0.33 |
| synthetic-only (n=47) | 0.71 / 0.17 | 0.74 / 0.21 |
| legacy families (n=40) | 0.72 / 0.10 | 0.69 / 0.23 |
| new families (n=24) | 0.06 / 0.42 | 0.25 / 0.29 |
| claim_support (n=14) | 0.56 / 0.00 | 0.56 / 0.14 |

Both shortcut families succeed on familiar templates and collapse on
authentic/new material — reported as separate strata, never as a
flattering combined average. Note S on legacy families alone clears the
absolute gates (0.72/0.10); it still cannot yield `PROGRESS` because the
verdict requires blind scope, a sealed holdout, adjudicated gold, all
comparators, and surface margins. That is the R1 defect, closed.

## Decision outputs (recorded, not claimed)

- Public diagnostic: per-arm numbers above; verdict `INCONCLUSIVE`
  (public scope; holdout pending; gold provisional; C/D unrun).
- Blind scope with no holdout package: `INCONCLUSIVE`, naming the sealed
  package, adjudicated gold, and C/D results as missing.
- The review's heuristic numbers (0.60/0.021) reproduce R1 `PROGRESS`
  under the old function even after hardening its file (file ignored via
  silent defaults); under R2 they yield `INCONCLUSIVE` on public scope
  and `INCONCLUSIVE` without a holdout. The vulnerable path is closed and
  regression-tested.
- Family bootstrap (39 families): V retention interval roughly
  [0.34, 0.74], misleading roughly [0.11, 0.36] — wide, as expected for
  39 correlated families; paired D-vs-S/D-vs-C intervals are empty until
  C/D run. Underpowered rule does not fire (39 ≥ 20 families, 45 ≥ 20
  useful), but intervals remain sensitivity bounds, not inference.

## Validation

Evidence: `docs/validation/alive-notebook-03a-r2/` (validate/submission/
prepare/audit summaries, full `baseline.json`,
`expected-baselines.json`, `decide-public.json`, `decide-blind.json`,
`audit.json`, notebook test logs).

| Check | Result |
|---|---|
| R2 validate (66, PUBLIC_COMPLETE, neutral-uniform) | pass |
| R2 submission (PENDING, HOLDOUT_PENDING) | pass |
| R2 prepare (neutral payloads, 2 access refusals gated) | pass |
| R2 audit-package (clean pass; R1 package fails with 68 findings) | pass |
| R2 baseline + `--check-against` (metrics/strata/decisions) | pass |
| R2 decide public + blind (both INCONCLUSIVE, gaps named) | pass |
| pytest v1.4 + v1.5 + v1.6 (69 tests) | pass |
| v1.4/v1.5 freezes + byte-preservation | pass |
| ruff check + format (repo scope) | pass |
| CI updated (v1.6 steps + preservation) | local pass; hosted logs pending |
| Full backend suite / native flows | unchanged scope; hosted CI pending |

Skipped/deferred: full `pytest -q` backend suite and native flows are not
re-run locally for R2 (no production code touched); hosted CI covers them.
No blind holdout, no independent labels, no semantic runs — all pending by
design.

## Prerequisites before 03B (all incomplete)

Frozen v1.6; representative diagnostic coverage; provisional labels;
S + V controls; citation gate; validated thresholds; contract migration
specified but not executed; governance adapter, model/settings/pricing
freeze, owner approval, cancellation qualification, output adjudication,
sealed holdout, independent panel — all pending. No external inference.
R2 must not be read as permission to run it.

## Reproduction

```powershell
uv sync --locked
uv run python -m scripts.notebook03a_r2 validate
uv run python -m scripts.notebook03a_r2 audit-package
uv run pytest -q tests/test_notebook03a.py tests/test_notebook03a_r1.py tests/test_notebook03a_r2.py
uv run python -m scripts.notebook03a_r2 baseline --check-against docs/validation/alive-notebook-03a-r2/expected-baselines.json --output .alive/03a-r2-replay-review-01.json
uv run python -m scripts.notebook03a_r2 decide --metrics .alive/03a-r2-replay-review-01.json --scope public_diagnostic --output .alive/03a-r2-decide-review-01.json
uv run python -m scripts.notebook03a_r2 score --records .alive/03a-r2-replay-review-01.json --arm V --output .alive/03a-r2-score-review-01.json
uv run ruff check alive migrations scripts tests
uv run ruff format --check alive migrations scripts tests
```

Sealed-package and blind-scope commands are custodian-only. Use unused
output names. Stop after the draft PR; human merge authority only.
Do not begin 03B.
