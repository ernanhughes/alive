# OpenCode engineering handoff - ALIVE-04 publication and ALIVE-05 browser continuity

## Phase A - ALIVE-04 interim publication

| Item | Value |
|---|---|
| Repository | `https://github.com/ernanhughes/alive` |
| Source branch | `opencode/alive-04-interim` at `85518350c0e201aabc618881e9b3f864cb688f24` |
| Publication branch | `opencode/alive-04-interim-pr` |
| Publication base | `origin/main` at `3580bdf04d5168afd85cdfae1122843cc9774871` |
| Publication commits | `f773ad0`, `74739c1`, `4eb35ba` |
| PR | [#7](https://github.com/ernanhughes/alive/pull/7) |
| PR head at creation | `4eb35ba1615168f3e9844d88ffaea63479f073db` |
| Changed files | 20 (the reviewed OpenCode files only) |
| State | Open, not merged, no auto-merge |

The publication branch was rebuilt from `origin/main` with only the three reviewed commits. Its
tree is identical to the original local `8551835` tree. The unrelated
`scripts/first_thought.py` commit that appeared on the old local baseline is not part of the PR.
The PR diff is exactly the ALIVE-04 interim work: evaluation integrity, permission/restart
hardening, dashboard provenance, tests, documentation and the controlled evidence archive.

Qualification repeated on the publication branch:

- 86 backend tests passed.
- 10 Living-focused tests passed.
- 5 frontend tests passed.
- Production dashboard build passed.
- Ruff check and format passed.
- Frozen ALIVE-04 replay and prior archives unchanged.

CI results and final PR state are in GitHub. All completed workflow checks passed (backend on
Ubuntu and Windows, dashboard, and first-contact PostgreSQL). The PR was not merged and
auto-merge was not enabled.

## Phase B - ALIVE-05 browser continuity

### Starting state

- Canonical primary worktree: `C:\Projects\alive`, branch `codex/alive-05-browser-experience`,
  at `0809f3788b521328e37d0bb41e87a6aefde76ef3`.
- The primary worktree contains substantial uncommitted ALIVE-05 work: `alive/web_experience.py`,
  `alive/web_models.py`, migration `0006`, extension panel and background changes, tests, scripts
  and `docs/ALIVE-05.md`.
- That worktree and `models.txt` were not edited, copied, reset, cleaned or stashed.
- No remote ALIVE-05 branch or PR exists. The ALIVE-05 implementation is not a safe publication
  baseline.

### Baseline selected

- New branch: `opencode/alive-05-browser-continuity`
- Base: `origin/main` at `3580bdf04d5168afd85cdfae1122843cc9774871`
- Feature commit: `87e913f`
- PR: [#8](https://github.com/ernanhughes/alive/pull/8)
- Initial PR head: `dd05f9667abd35488d815143e7fb76a98433ed18`
- State: open, not merged, no auto-merge

This branch is deliberately independent of the uncommitted ALIVE-05 companion. It does not copy
or duplicate that implementation. It improves the shared managed-Chrome observation path that
ALIVE-05 can adopt when Codex integrates the companion.

### Implementation

- `alive/browser.py` now emits a persisted provenance envelope for every managed-Chrome
  observation:
  - `observation_id` matching the ingested event;
  - `source_kind = managed_chrome_dom`;
  - `trust_level = observed_page_text_not_verified_fact`;
  - `observed_at`, `selector`, `text_sha256`, `text_chars`;
  - `permission_scope`, `permission_origin`, `permission_read_only`.
- `Browsers.observe` rejects a page outside the configured exact-origin allowlist before reading,
  and rejects an origin change during the read. Both denial paths ingest no event.
- The Browser dashboard shows the persisted source, trust, permission origin, read-only status,
  observation time, text hash prefix, character count and selector through a new
  `BrowserProvenance` component.
- No permission expansion, new origin, new selector capability, migration or model call.

### Tests and evidence

| Check | Result |
|---|---|
| Backend suite | 86 passed |
| `tests/test_browser_provenance.py` | 3 passed |
| Browser provenance + Living focused | 10 passed |
| Frontend suite | 6 passed |
| Production build | Passed |
| Ruff check and format | Passed |
| Prior archives | All manifests verified |

New archive: `archives/ALIVE-05-OPENCODE/` with controlled test-harness observation evidence,
validation transcripts and manifest. It is **not** native Chrome or Meta evidence.
`evidence/managed-chrome-observation.json` records an allowed observation and two denied cases
(disallowed origin and origin change during read), both with zero events ingested.

### Read-only findings in the uncommitted ALIVE-05 companion

These were inspected but deliberately **not edited**:

1. The companion already separates goals, grants, snapshots, model notes and explicit feedback,
   with exact URL/goal/excerpt matching and restart grant revocation. That work is substantive
   and should remain Codex's.
2. **Permission race to fix during integration:** `WebCompanion.analyse()` validates the grant,
   commits the reservation, releases the lock and then starts a worker. There is a window where
   `revoke()` can run before `self.worker` is registered, so cancellation may not occur, and
   `execute()` does not recheck grant validity immediately before the provider call. Revalidate
   the grant and register/cancel atomically under the companion lock, and recheck immediately
   before inference.
3. The extension binds consent to a `tab_key` at grant creation, but the snapshot request carries
   only the URL and grant ID. Consider binding the snapshot to the grant/tab identity server-side
   if cross-tab substitution is in scope.
4. The companion's model citation check is a good integrity control; keep it. The model output is
   still an interpretation, not verified fact.
5. No schema or migration change is needed for this branch. Do not duplicate migration `0006`.

### Integration instructions for Codex

1. Review PR #7 first and decide whether to merge or cherry-pick the ALIVE-04 interim commits.
   Do not auto-merge.
2. Review the Phase B PR for the managed-Chrome provenance change. It is independent of the
   uncommitted companion, but it touches `alive/browser.py`, `dashboard/src/main.tsx`,
   `dashboard/src/style.css` and adds `dashboard/src/BrowserProvenance.tsx`.
3. When integrating ALIVE-05, keep the companion's source/trust fields and add the managed-Chrome
   envelope where the shared Browser path is used; do not replace one provenance model with the
   other.
4. Apply the permission-race recommendation above in the companion before any native
   qualification.
5. Preserve the existing negative results and do not reinterpret the companion's exact-match
   reuse as general learning.

## Deferred work

- Native Chrome/Meta ALIVE-05 qualification requires free ports and explicit owner authorization.
  Ports `8000` and `5173` were occupied by the primary worktree.
- No paid inference was run.
- Native visual review of the Browser provenance panel was not performed; the React component
  test and production build passed.
- The uncommitted ALIVE-05 companion remains entirely Codex's to finish and publish.

## Local commits and remotes

| Commit | Purpose |
|---|---|
| `87e913f` | Add managed Chrome observation provenance and origin recheck |
| `dd05f9667abd35488d815143e7fb76a98433ed18` | Controlled archive and initial Phase B handoff |
| final local tip | PR link and CI-status update to this handoff |

The Phase B branch is pushed at `opencode/alive-05-browser-continuity`; PR
[#8](https://github.com/ernanhughes/alive/pull/8) is open and not merged. The remote head matched
the local head at `dd05f9667abd35488d815143e7fb76a98433ed18` before the final handoff-only update.
No force-push, merge, rebase of shared branches or change to `main` was performed.
