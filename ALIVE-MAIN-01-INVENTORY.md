# ALIVE-MAIN-01 — Repository Inventory

Date: 2026-10-29. Base: `origin/main @ 83a8061` (PR #49 merged).
Method: `git fetch origin --prune`, `git worktree list --porcelain`,
`git branch -vv` / `-r`, per-branch `merge-base --is-ancestor`, per-worktree
`git status --porcelain`, `gh pr list` (open + last 60 closed).

## 1. PR inventory

- **Open: 1** — #48 `ALIVE-DOCKER-01` (`feat/alive-docker-01`, draft, head
  `7f4f10b`). No recorded review. Only unmerged workstream.
- **Closed (last 60, i.e. all — repo has 48 closed): all MERGED.**
  Includes #49 (eval-01 trusted custody), #47 (notebook03a-r2),
  #46/#45 (notebook03a-R1/semantic), #44–#40 (notebook-02-R1/02/01-R1/01),
  #39–#37 (demo-live-01 display/R1/capture-v2), #36 (ALIVE-14-R5-R1),
  #35/#34 (intel I1-A2/I1-A). No closed-but-unmerged PR found.

## 2. Remote branches

All 46 remote branches (codex/*, feature/*, fix/*, design/*, opencode/*)
are ancestors of `origin/main` (`merge-base --is-ancestor` = 0, ahead = 0).
No unmerged remote work except `origin/feat/alive-docker-01`
(10 ahead / 10 behind — main moved via #47 + #49 after the Docker base).

## 3. Local-only branches

| Branch | Tip | In main? | Classification |
| --- | --- | --- | --- |
| 14x `cocoder/improve/WS-*` | 1 unpushed commit each, base ~38 behind | NO | NEEDS_REVIEW — machine-generated token-file hardening (`chmod 0o600` + file length check on `alive/config.py` + `tests/test_config_token.py`); identical subject lines, unreviewed, stale base. Evaluate one, adopt or drop as a separate decision. NOT part of consolidation merges. |
| `codex/consolidate-main-20261028` (f6aa86f) | ancestor of main | YES | SAFE_TO_CLEAN (branch ref; superseded record, content already in main) |
| `codex/fix-review-probes`, `codex/i1-a2-qualification`, `opencode/alive-04-interim` | ancestors of main | YES | SAFE_TO_CLEAN (branch refs; no worktrees) |
| `codex/alive-03-p2/p3`, `codex/alive-04`, `codex/alive-10-refinement/review` | ancestors of main | YES | ARCHIVE_PRESERVE (branch refs; have worktrees, see §5) |
| `opencode/alive-10-native-intelligence` (local 2686a80, 5 behind remote tip, both in main) | YES | YES | SAFE_TO_CLEAN after confirming the `.local/share/opencode` worktree owner (may be a live agent session) |

## 4. `origin/main` movement during Docker work

Docker base `b9978da` → now `83a8061` via #47 (notebook03a-r2) and #49
(eval-01). Consequence: `feat/alive-docker-01` must be rebased onto the new
main and requalified (rebuild, migrations, smoke, E2E, browser) before merge.
Tracked as Phase 2.

## 5. Worktrees

| Worktree | State | Classification |
| --- | --- | --- |
| `C:/Projects/alive` (eval-01 branch, merged) | only `?? .vscode/` | ACTIVE_DO_NOT_TOUCH (primary checkout; `.vscode/` is owner tooling, leave alone) |
| `alive-docker-01` (feat, 7f4f10b) | clean | ACTIVE_DO_NOT_TOUCH (PR #48 workstream) |
| `alive-review-docker` (detached 7f4f10b) | — | ACTIVE_DO_NOT_TOUCH (owner review checkout) |
| notebook-01/02/03a, alive-10-refinement/review, alive-11 (=13-reliable), alive-14–r5, review-11/12 | clean | ARCHIVE_PRESERVE branches; worktrees removable ONLY with approval after Phase 5 (all clean, safe candidates) |
| `alive-notebook-02-r1` | **DIRTY**: `M docs/ALIVE-NOTEBOOK-02-R1-REPORT.md` (163-line report replaced by 13-line stub referencing PR #44) | **DO_NOT_TOUCH + decision needed**: committed full report is merged in main; the stub would destroy evidence if committed here. Owner to confirm restore (`git checkout -- …`) — not done unilaterally. |
| `C:/r1` (detached fc9e75f) | untracked `docs/validation/demo-live-01-r1/` | NEEDS_REVIEW: equivalent evidence (25 files) is committed in `origin/main`; likely regenerable. Removal needs approval. |
| `C:/rdi` (detached cef0fb9) | 7 modified PNGs + `result.json` under `docs/validation/` | NEEDS_REVIEW: committed qualified set exists in main; these look like re-rendered artifacts. Removal needs approval. |
| cc-r06-* + nested `.cocoder/WS-*` (~20, detached or cocoder branches) | not dirt-checked (machine workspaces) | NEEDS_REVIEW: verify no live agent owns them, then bulk-clean candidates |
| `Temp/cocoder-baseline-*`, `Temp/opencode/alive14r3-prefix`, `.local/share/opencode/.../nimble-sailor` | — | ACTIVE_DO_NOT_TOUCH until owner confirms no live agent (opencode session dirs) |
| `C:/Projects/alive-notebook-01-r1`, `-02`, `-03a` (root-level) | clean | same as ARCHIVE_PRESERVE group above |

No stashes. No unpushed commits except cocoder WS-* and feat/alive-docker-01.

## 6. Classification summary

- QUALIFIED_FOR_MERGE: #48 only, pending Phase 2 rebase + requalification.
- NEEDS_REVIEW: 14x cocoder WS-* branches; /r1 + /rdi artifacts; cc-r06 machine workspaces.
- BLOCKED: none (no failed-gate work awaiting merge).
- ACTIVE_DO_NOT_TOUCH: C:/Projects/alive, alive-docker-01, alive-review-docker, opencode session dirs, alive-notebook-02-r1 (dirty report).
- ARCHIVE_PRESERVE: all merged codex research branches + their committed evidence.
- SAFE_TO_CLEAN (pending approval): `codex/consolidate-main-20261028`,
  `codex/fix-review-probes`, `codex/i1-a2-qualification`, `opencode/alive-04-interim`
  branch refs (no worktrees, fully in main).

## 7. Merge manifest status (updated post-merge)

MERGED by repository owner (regular merge commit, exact approved head
`0182e0b`): `4b74f3c` (Merge PR #48). Agent performed no merge. Phase 5
validates the merged `main`; see `ALIVE-MAIN-01-PHASE-5.md`. Original proposal
below is retained for the record:

1. ~~Rebase `feat/alive-docker-01`...~~ done pre-merge; requalified; merged.
2. Nothing else — every other branch was already in `main`.
3. Explicitly NOT merged: cocoder WS-* (unreviewed machine candidates).
