# ALIVE-TEST-INTEL-01 Report — Intelligent Test Profiling, Classification and Selective Execution

## Status

Implemented on this branch, validated, ready for review. Not merged.

## What was built

| Artifact | Path | Purpose |
| --- | --- | --- |
| Selector | `scripts/test_select.py` | Change-aware test selection (`--mode`, `--base`, `--explain`, `--json`, `--files-only`, `--changed`) |
| Runner | `scripts/test_run.py` | Unified execution + decision receipt + `--dry-run` + `--report` + explicit targets |
| Profiler | `scripts/test_profile.py` | Repeatable timing + `ALIVE-TEST-PROFILE.md` generation |
| Strategy | `docs/testing/ALIVE-TEST-STRATEGY.md` | Tier definitions, selection principles, policy |
| Profile | `docs/testing/ALIVE-TEST-PROFILE.md` | Measured inventory (generated) |
| This report | `docs/testing/ALIVE-TEST-INTEL-01-REPORT.md` | Implementation + qualification evidence |
| Selector tests | `tests/test_test_select.py` | 10 regression tests for conservative fallback behaviour |

No existing tests deleted or weakened. No production behaviour changed.
No new third-party dependencies (stdlib + pytest + git only).

## Design (summary)

- Reverse import index: each `tests/test_*.py` mapped to `alive.*`/`scripts.*`
  modules it imports; one-hop expansion through intra-`alive` imports for
  `affected` mode. `quick` uses basename-token matching to stay in seconds.
- Risk rules for migrations, deploy/Docker, evaluation, safety/auth, claim
  protocol, frontend/extension/site, protocol verifiers.
- Conservative fallback: core files (`app.py`, `config.py`, `db.py`,
  `models.py`, `conftest.py`, `pyproject.toml`, `alembic.ini`), CI workflows,
  unknown file types, or >20 changed files select the full suite in `affected`
  mode; `quick` stays bounded and declares full qualification still required.
- Docs-only changes select the 2-file smoke net.
- Every run prints a decision receipt; non-full modes disclaim equivalence.

## Phase 1 — Audit (measured, this repo)

- 50 `tests/test_*.py` modules (+1 new: `test_test_select.py`), 570 tests
  collected in ~0.6s (`pytest --collect-only`) — measured on base `4b74f3c`;
  after the eval-02 merges now on `origin/main`, collection is 618 tests.
- Default suite is sqlite + mocked providers (`tests/conftest.py`); no
  Docker/Postgres in the default path. Conditional costs: optional real
  Postgres (`test_claim_runtime.py`), subprocess alembic (`test_migrations.py`),
  long mocked sleeps (`test_agents.py`, `test_cognition.py`, `test_living.py`).
- CI: 4 jobs (backend incl. full `pytest -q`; dashboard vitest + node --test;
  first-contact postgres + playwright chrome; notebook hugo + eval chain).
- See `ALIVE-TEST-PROFILE.md` for the ranked slow-test table.

## Phase 8 — Selection correctness (backtesting)

Historical-behaviour probes via `--changed` overrides plus automated tests:

| Probe (changed) | Selected | Expected | Result |
| --- | --- | --- | --- |
| `alive/browser.py` (affected) | 15 files incl. provenance/living/demo | browser-adjacent, no PG rebuild | pass |
| `dashboard/src/App.tsx` | demo/provenance/transport, no migrations | frontend-only | pass |
| `migrations/versions/0007_x.py` | migrations/persistence + docker flag | DB change | pass |
| `scripts/alive_eval01.py` | `test_alive_eval01` (+smoke) | eval integrity | pass |
| `Dockerfile` | config/migrations/transport + docker flag | container | pass |
| `docs/testing/notes.md` | 2-file smoke net | docs-only | pass |
| `some/new/unknown.xyz` | all 51 files (fallback) | unknown -> broad | pass |
| `alive/app.py` (affected) | all 51 files (fallback) | core -> broad | pass |
| `alive/app.py` (quick) | bounded smoke subset | quick stays fast | pass |

`tests/test_test_select.py`: 10/10 pass. No misses found in probes.

## Phase 9 — Benchmarks (measured, single host)

Full suite baseline: 562 passed, 7 skipped, 1 xfailed in 490.97s
(`pytest -q --durations=25`, measured on base `4b74f3c` before `test_test_select.py`
existed; current collection after eval-02 merges is 618 tests — re-run
`test_profile.py` to refresh timings on the new base).
Collection: ~0.6–1.5s for 570–580 tests.

| Workflow | Existing | New | Improvement |
| --- | --- | --- | --- |
| Small backend edit (`alive/browser.py`, quick: 6 files / 38 tests) | 491s (full) | 27.8s, 38 passed | ~17.7x |
| Same change (affected: 15 files / 208 tests) | 491s (full) | 167.3s, 208 passed | ~2.9x |
| Frontend-only change (affected: 5 files / 28 tests, no PG rebuild) | 491s (full) | 13.0s, 28 passed | ~37.8x |
| Database change (affected: 6 files / 47 tests + docker flag) | 491s (full) | 29.2s, 47 passed | ~16.8x |
| Full pytest execution | 491s | unchanged path (`--mode full`) | 1.0x (gate preserved) |
| Docker qualification | unchanged scripts | same scripts via `--mode docker` | 1.0x (gate preserved) |

No figures invented: every number above comes from the runs in this session.
`quick` is bounded but not yet "seconds" for import-heavy modules — the 27.8s
is dominated by `test_living.py`/`test_demo_live_01.py` startup paths, a
candidate for fixture-scope optimization in a follow-up (not applied here).

## CI recommendation (staged, not yet applied)

1. Fast jobs first (lint + quick/affected selection).
2. Affected integration per change impact.
3. FULL (`pytest -q` + verifiers) remains the mandatory pre-merge gate.
4. DOCKER on deployment-sensitive changes + release qualification.
5. Scheduled full/container regressions supplement, never replace, merge gates.
6. Preserve exact commit-SHA attribution; no branch-protection changes proposed.

## Definition of success (self-check)

- [x] Faster dev loop available (`quick` bounded; `affected` selective).
- [x] Explainable selection (`--explain`, reasons in receipt/report).
- [x] High-risk changes trigger stronger testing (fallback + docker flag).
- [x] Any tier runnable explicitly (`test_run.py --mode ...`).
- [x] Pre-merge/deployment gates preserved (full/docker paths unchanged).
- [x] Measured reduction reported (see benchmarks; profile generated).
- [x] Selector has automated regression coverage (10 tests).
- [x] Simple to maintain (3 stdlib scripts + risk table).

## Recommendation

Merge the scripts/docs/tests with existing gates untouched; adopt
`python scripts/test_run.py --mode quick` as the default developer command;
add staged selection to CI as a follow-up without removing any required check.
