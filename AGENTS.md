# Working on ALIVE

## Default to fast, targeted verification

Do not run the full backend suite after every edit. A one-line change does not
justify an automatic full-suite run or waiting for every CI job to finish.
Choose checks by affected behavior, not by running every available test.

During normal development:

1. Run the smallest relevant test file or exact pytest node / Vitest test.
2. Run formatting/lint checks only for changed files.
3. For dashboard code, run the production build once when the change is ready.
4. Stop after those checks pass. Broaden only for a failure, a concrete uncovered
   interaction, an explicit request, or a milestone's stated acceptance criteria.
5. For documentation-only edits, use `git diff --check`; do not run application tests.

Do not repeat successful checks when no relevant code has changed. Test-status
updates and PR-description edits do not require another test run.

## Fast commands

Run from the repository root unless stated otherwise. Select files that exist
on the current branch. These are starting points, not a mandatory checklist.

| Change | First check |
| --- | --- |
| Python formatting/lint | `uv run ruff check <changed-python-files>` and `uv run ruff format --check <changed-python-files>` |
| One Python behavior | `uv run pytest -q tests/test_file.py::test_name` |
| Memory/search | `uv run pytest -q tests/test_meta_memory.py` |
| Workflow definition parsing | `uv run pytest -q tests/test_workflows_spec.py` |
| Dashboard API client | `npm --prefix dashboard test -- src/api.test.ts` |
| Dashboard component | `npm --prefix dashboard test -- src/Component.test.tsx` (use the actual file) |
| Workflow dashboard | `npm --prefix dashboard test -- src/workflows/` |
| All dashboard unit tests | `npm --prefix dashboard test` (normally seconds; this is not browser E2E) |
| Dashboard build/type check | `npm --prefix dashboard run build` |
| Extension change | `node --test tests/<affected-extension-suite>.test.cjs` |
| Documentation only | `git diff --check` |

Prefer an existing installed environment and locked dependencies. Do not reinstall
everything to run an already available focused check.

## Integration checks are a separate tier

Real Pi subprocesses, API/database fixtures, browser E2E, PostgreSQL, Docker,
restart/recovery and mutation campaigns can take substantially longer than unit
tests. Run the specific scenario needed for the change, once it is ready.

Examples for branches containing the observatory:

- Backend read projections: `uv run pytest -q tests/test_workflow_observatory.py`.
  This includes real Pi coverage and is an integration check, not a pure unit test.
- A single browser scenario, from `dashboard`:
  `npx playwright test e2e/workflows.spec.ts -g "replay to end"`.
  Use an explicitly disposable, seeded test runtime and the required environment.
- Mutation replay: select the relevant mutant IDs when the script supports it.
  Do not run every historical campaign for an unrelated UI edit.

Do not invoke all browser E2E specs, all Pi suites, or a Docker build as the
default response to a small change. Do not add dependencies or change timeouts,
polling thresholds, skips or assertions just to make verification faster.

## Full-suite / CI qualification

Bare `uv run pytest -q` (no selector) is the full backend suite. It is a slow
qualification step, not the development loop. Run it locally only when explicitly
requested or when a concrete cross-cutting risk requires it. When full CI is
already required, let CI run the full suite instead of duplicating it locally.

- Start final-head qualification after code and review evidence are ready.
- Do not push repeated commits solely to record CI status: each push can start
  another full run. Put CI updates in the PR description instead.
- Keep routine changes reviewable immediately: report focused checks and link
  pending CI rather than holding every response until long jobs finish.
- If the user explicitly requires green full CI before final acceptance, keep
  that qualification pending until the actual runs pass; do not call it complete.
- Do not cancel or restart a job merely because it is slow. Elapsed time and an
  unavailable in-progress log do not establish a stall. Check actual progress
  before intervening, and disclose any cancellation or rerun.
- Keep unrelated fixes separate from the active PR and preserve owner edits.

## Isolate test configuration

`Settings(_env_file=None)` still reads process environment variables. Tests that
assert a fallback must explicitly establish its precondition. For example,
`test_hybrid_fallback_is_explicit` must disable embeddings for that test rather
than assuming the developer has no local model installed. Preserve its fallback
assertions; do not change production search behavior to satisfy the test.

Use disposable workspaces/databases and scripted providers for integration
checks. Do not use paid inference for verification.

When creating a worktree from a base that predates this file, carry this testing
policy into the task's instructions so the fast development loop remains the
default. Do not silently add it to an already-qualified PR and restart its CI.
