# ALIVE-MAIN-01 — Phase 6 Cleanup Manifest (PROPOSAL — DO NOT EXECUTE)

Nothing below has been executed. Each item requires explicit approval.
Rules: verify before removal; never `--force`; never delete a branch merely
because its worktree is removed; never touch volumes; never touch the dirty
`alive-notebook-02-r1` report file or the stopped `alive-review-docker` env.

## Group A — safe branch deletions (proposed, no worktrees, fully in main)

- `codex/consolidate-main-20261028` (stale superseded record)
- `codex/fix-review-probes`
- `codex/i1-a2-qualification`
- `opencode/alive-04-interim`

Verify with `merge-base --is-ancestor` immediately before deleting (already 0).

## Group B — worktree removals (proposed, all CLEAN, branches merged + preserved)

Remove worktree registration only; keep all branches:

- `alive-notebook-01-r1`, `alive-notebook-02`, `alive-notebook-03a`,
  `alive-worktrees/alive-notebook-01`
- `alive-worktrees/alive-10-refinement`, `alive-10-review`, `alive-11`,
  `alive-14`, `alive-14-r1…r5`
- `alive-review-11`, `alive-review-12` (detached review checkpoints)
- `alive-main-verify` (throwaway Phase 5 worktree, detached, no branch)
- `alive-worktrees/alive-docker-01` (feature merged; verify no reliance first —
  its stopped `alive-docker-01_*` containers/volumes are separate from removal)

Precondition for each: `git status --porcelain` still clean, no live agent
process working inside (check before each removal).

## Group C — explicitly EXCLUDED (no action proposed)

- `alive-notebook-02-r1`: dirty report stub — owner decision required
  (restore vs preserve); never auto-cleaned.
- `/r1`, `/rdi`: detached review checkpoints with validation artifacts whose
  qualified set is already committed in `main`. Removal needs explicit approval.
- `alive-review-docker` worktree, containers and volumes: stopped, preserved.
- `C:/Projects/alive` primary checkout (incl. `?? .vscode/` owner tooling).
- opencode session dirs (`Temp/...`, `.local/share/opencode/...`) and
  `nimble-sailor`: possible live agent — verify ownership first, default keep.
- cc-r06 `WS-*` machine workspaces + 14 unmerged `cocoder/improve/WS-*`
  branches: bulk removal only after confirming no active process AND an
  adopt/drop decision on the token-hardening idea. Branches kept regardless
  until that decision.
- Any `docker ... -v` volume deletion: never proposed.

## Execution outcome (2026-10-29, approved Groups A+B)

Group A: 4/4 deleted after ancestor=0 + no-worktree verification —
`codex/consolidate-main-20261028`, `codex/fix-review-probes`,
`codex/i1-a2-qualification`, `opencode/alive-04-interim`.

Group B: 16/17 worktree registrations removed after clean + ancestor=0 +
no-dev-marker verification (branches preserved, incl. `feat/alive-docker-01`).
`alive-notebook-01`: worktree registration removed but its directory remains
on disk — VSCode Python tooling is actively using its `.venv`, so directory
deletion was skipped per safeguards. Owner may delete it manually after
closing the VSCode handle; nothing versioned is at risk (all content in main).

Skipped per Group C (untouched): `alive-notebook-02-r1` (dirty report),
`/r1`, `/rdi`, `alive-review-docker` (+volumes), primary checkout,
opencode/Temp session dirs, all cc-r06 machine workspaces + 14 WS branches.

Post-cleanup: `origin/main` = `4b74f3c` (unchanged); primary checkout
unchanged (eval-01 branch @ a76f23f + `?? .vscode/` only). No volumes touched.

## Execution order (after approval)

A (branches) → B (worktrees, verify-each) → re-run `git worktree list` and
confirm `main` untouched. Then proceed to Phase 7 baseline tag proposal.
