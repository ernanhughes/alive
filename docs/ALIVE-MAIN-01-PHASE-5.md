# ALIVE-MAIN-01 — Phase 5 Consolidated Validation

Merged `main`: `4b74f3c6337c5be839a3ef9e6044b409e3ce08f9`
(Merge PR #48 from `feat/alive-docker-01 @ 0182e0b`; merge performed by
repository owner via GitHub at 2026-10-29T09:19:17Z as a regular merge commit.
No force-push, no rewritten history. Agent did not execute the merge.)

Validation was performed from a clean detached worktree at exactly `4b74f3c`
(`alive-main-verify`), with fresh Docker volumes. No paid inference.

## Results

| Check | Result |
| --- | --- |
| Full unit suite `pytest -q` | **562 passed, 7 skipped, 1 xfailed**, exit 0 |
| Dashboard production build (`npm ci` + `tsc -b && vite build`) | **PASS** |
| Docker clean build + launch | **PASS**, both services healthy |
| Alembic migrations on fresh PostgreSQL/pgvector | **PASS**, seed marker created + verified |
| Backend `/api/v1/health` | `ok` |
| Smoke test `scripts/docker-smoke-test.py` | **8/8 PASS** |
| Restart persistence | **PASS** (goals preserved, exactly 1 marker goal, no duplication) |
| Isolated E2E (`compose.e2e.yaml`, `--exit-code-from e2e`) | **6/6 groups PASS**, dev data untouched |
| Playwright `dashboard/e2e/docker.spec.ts` (real Chrome) | **2/2 PASS** |
| Hand-driven browser journey (Memory `postgresql_fts` search) | **PASS**, screenshot `ALIVE-MAIN-01-verify.jpg` |
| Secrets scan (no provider keys in env/layers/commits) | **PASS** |

## Regressions / blockers

None. The merged `main` validates as a whole: application code from PRs
#34–#49 plus the Docker deployment from #48 function together with no new
failures. Known Docker limitations (no managed Chrome, no embedding model,
mock-by-default inference) are unchanged and documented in
`docs/deployment/ALIVE-DOCKER-01-test-report.md`.

## Outstanding items (not blockers)

- `alive-notebook-02-r1` worktree still holds the uncommitted report-stub edit;
  untouched per instructions. Committed full report remains intact in `main`.
- User review stack `alive-review-docker` remains stopped with data preserved.
