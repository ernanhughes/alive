# ALIVE-ARCH-01 — Production–Experiment Separation

Status: Phase 1 implemented (dependency extraction). Physical relocation deferred.

## Decision

Approve separation, implemented as a dependency-extraction refactor rather than
a simple folder move.

## What changed

- New runtime package `alive/governance/` owns reusable capabilities:
  `pricing.price`, `budgets.settle_control` / `check_spend` /
  `charged_micro_usd` / `worst_micro_usd`, and `hashing.file_hash`.
- Production services (`alive/living.py`, `alive/web_experience.py`,
  `alive/research_relationships.py`, `alive/learning/*`) import from
  `alive.governance`, never from `alive.experiment`.
- `alive/experiment_budget.py` is now a thin experiment-specific overlay that
  delegates spend math to governance. Production must not import it.
- `create_app()` no longer initializes the experiment runner or mounts
  `/api/v1/experiments/*` by default. Opt in with
  `create_app(settings, include_experiments=True)`,
  `Settings.alive_experiments_enabled=True`, or
  `experiments.dev_app.create_experiment_app()`.
- `experiments/` is the canonical home for research harnesses. It may depend
  on ALIVE; ALIVE must never depend on it.
- `tests/test_arch_boundaries.py` enforces the boundary and checks governance
  parity with the legacy helpers.

## What deliberately did not move

`alive/experiment/*.py` (corpus, scoring, metrics, policy, prompts, freeze,
schema, service, api) are byte-identical. `benchmarks/alive03-p1/freeze-*.json`
pins those exact source paths and hashes, and `alive/experiment/service.py`,
`metrics.py`, `freeze.py`, etc. are part of the frozen source set. Editing or
relocating them would invalidate previously qualified artifacts.

A physical move to `experiments/alive03_p1/` requires an explicit,
owner-authorized re-seal that preserves historical freeze JSONs as evidence.
Do not rewrite `benchmarks/`, `archives/ALIVE-03-P1-FULL/`, or
`.alive/` results as part of cleanup.

## Preserved distinctions

- `alive/experiment_approval.py` remains production: owner-authenticated
  campaign registration and approval records are a runtime governance
  capability, not a benchmark fixture.
- `alive/learning/experiment.py` and `history_diagnostic.py` are simulation
  studies; only their shared hashing now comes from governance. The reusable
  learning machinery itself was not moved.

## Verification

- `tests/test_arch_boundaries.py` — no production imports of the harness;
  default app has no experiment routes; governance parity holds.
- Existing suites (`tests/test_experiment03.py`, `tests/test_experiment_budget.py`,
  `tests/test_full_report.py`) run against the opt-in test client.
