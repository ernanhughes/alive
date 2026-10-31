# PI-03A independent-review handoff

> Superseded for the current state by `PI-03A-R2-REVIEW.md`, written after the independent review of
> this document's head (`e0db4ae`) returned REVISE. This file is kept as the original handoff.

Scope: declarative governed capabilities. Stop here; PI-03B/C and any selector need separate
authorization. Nothing is merged automatically.

## What changed

1. Strict `capability/v1` YAML manifests with deterministic hashing (`manifest.py`, spec in
   `PI-03A-MANIFEST-SPEC.md`).
2. One immutable startup catalogue over manifests and a code-owned implementation allowlist
   (`registry.py`, `trusted.py`); `OPERATIONS`/`ADAPTERS` are derived compatibility views.
3. Retained per-definition bindings and per-execution snapshots (migration 0011), so history never
   reads today's catalogue.
4. Authorization as an intersection, rechecked at start, before each stage and at settlement.
5. A real new capability, `repository.inspect@1.0.0`, executed by the existing `WorkflowRunner`.
6. Read-only catalogue API, `python -m alive.capabilities` tooling, and a generic dashboard pane
   with observatory links keyed by retained identity and manifest hash.

## Branch and provenance note

`main` at `ed5b178` already contained a partial PI-03A commit that imported modules never
committed (`bindings`, `execution`, `repository`, the `repository.inspect` manifest and migration
0011), so the package could not be imported. Those files existed only as untracked files in the
`codex/pi-03a-capabilities` worktree; they were copied into this branch and lint-formatted; the only
behavioural change was `validation_status` for retrieval (below). The reviewer should treat the whole of `alive/capabilities/`
as new code under review, not only this branch's diff against `ed5b178`. The other worktree was left untouched.

## Defect found and fixed during this work

`repository.inspect` reported `validation_status="passed"` for a plain retrieval. Retrieval
validates nothing, so it now reports `not_run`; an end-to-end test pins it.

## Evidence (focused, per AGENTS.md)

| Check | Result |
| --- | --- |
| `tests/test_capability_manifests.py`, `test_capability_registry.py`, `test_workflows_spec.py` | 126 passed (before additions) |
| `tests/test_capability_repository.py` (capture and reader) | passed |
| `tests/test_capability_contract_enforcement.py` | passed |
| `tests/test_capability_repository_execution.py` (real runner, hostile fixture) | passed |
| `tests/test_capability_catalog_api.py`, `test_capability_cli.py` | passed |
| `tests/test_workflows_store.py`, `test_workflows_api.py`, `test_workflow_execution.py` | 104 passed |
| Workflow-adjacent regression (authority, cancellation, observatory, r2/r3, transactions, migration) | see "Regression" below; Pi-backed cases not verifiable locally |
| `npm --prefix dashboard test -- src/capabilities/` | 13 passed |
| `npm --prefix dashboard test -- src/workflows/` | 44 passed |
| `npm --prefix dashboard run build` | passed |
| `ruff check` / `ruff format --check` on changed files | clean |

### Mutation campaign (`scripts/capability_mutations.py`, receipts in `validation/mutations.json`)

19 single-guard mutants, run in a temporary copy, each with a passing baseline: **19 killed,
0 survived, 0 invalid.** A kill requires a test failure, not a collection or syntax error.

The first run killed 13 and left 6; each survivor was examined rather than waved through:

- C3, C4, C6, C19 had no direct behavioural test. Tests were added and the mutants are now killed.
- C1 and C2 were *equivalent mutants by redundancy*. A changed manifest is refused by three
  independent checks (identity compare at recheck, identity compare at grant check, and the policy
  hash, which embeds the identity). C1 therefore removes all three together and is killed. C2
  was re-aimed at the policy hash and killed by a new test in which configuration is loosened
  after the grant (the limit comparison cannot catch that, only the policy hash can).

Mutants cover: pinned identity and manifest hash, implementation permission ceiling, grant
permissions and limits, configuration widening, unavailable/disabled refusal, stage timeout and
hash pin, input and output contracts, output size, writer permission, reader hash and path scope,
hardlink and secret handling, retained binding hash and the runner's executable check.
Not mutated: parser rejection rules (covered by their own adversarial tests), trusted
implementation resolution, stage-identity corruption, and the catalogue API.

## Regression

`tests/test_workflow_{authority,cancellation,observatory,observatory_identity,r2_*,r3_guards,
transactions,execution_migration}.py` were run on this branch. 25 tests failed.

- 3 were real regressions from the earlier PI-03A commit and are fixed here:
  `test_control_dependency_blocks_stage_even_without_an_output_reference` and
  `test_real_stage_timeout_keeps_category_effects_and_settlement[deterministic|run_deadline]`.
  They register their own definition and pass its id to `fixture_authorization`, which built the
  capability binding from the default definition (`exact_capability_owner_grant_required`). They
  pass after the fixture was corrected.
- The remaining 22 are timeouts in tests that start the real Pi subprocess. The same files were run
  at the pre-PI-03A commit `c1cdd17` with the same virtualenv: 26 failed and 25 passed there, and
  the 22 failures are common to both. They are therefore environmental on the development host and
  say nothing, good or bad, about the Pi-backed capability path (`cognition.role`). A CI run with a
  working Pi runtime is required before this is accepted. The failing sets differed slightly
  between runs (a few fence cases), consistent with timing sensitivity.

## Not run (and why)

Full backend suite; PostgreSQL (including migration 0011 and a `downgrade`); Docker build;
Playwright browser E2E; Pi, Intelligence and extension regressions; Linux and Windows CI; the
POSIX branch of the repository reader. AGENTS.md reserves these for qualification, and CI should
run them on the PR head. They were not run locally and nothing here claims they pass.

## Decisions requested from the owner

1. How is a repository snapshot approved in production (API, CLI or owner harness)? Until
   decided, `repository.inspect` runs only where the host supplies a registry with snapshots.
2. Whether to keep the PI-02 compatibility adoption path until a stated retirement condition.
3. Whether implementation fingerprints should also cover the transitive import graph.

## Reviewer focus

- `registry.py`: ceiling equality, `check_grant`, `bind` (including the legacy branch).
- `repository.py`: capture bounds, Windows handle check, POSIX branch (unexercised here).
- `bindings.py` and runner changes: retained-identity integrity and fail-closed behaviour.
- Whether any path lets a model, request body or file name influence a capability identity.
