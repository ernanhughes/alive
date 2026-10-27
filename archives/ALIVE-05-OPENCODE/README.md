# ALIVE-05 OpenCode browser continuity evidence

This archive records the OpenCode Phase B improvement for managed Chrome observation
provenance. It is **controlled test-harness evidence**, not native Chrome or Meta qualification.

The substantive ALIVE-05 documentation companion remains uncommitted in the owner's primary
worktree. This branch does not copy, modify or claim that work. It improves a shared, committed
browser layer that ALIVE-05 can adopt or reconcile.

## Provenance

| Item | Value |
|---|---|
| Repository | `https://github.com/ernanhughes/alive` |
| Base | `origin/main` at `3580bdf04d5168afd85cdfae1122843cc9774871` |
| Branch | `opencode/alive-05-browser-continuity` |
| Implementation commit | `87e913f` |
| Evidence kind | Controlled test-harness observation |
| Native Chrome | **No** |
| Meta inference | **No** |
| Paid calls | **0** |

## What changed

Managed Chrome observations now persist an explicit provenance envelope:

- `observation_id` - the same identifier as the ingested event;
- `source_kind = managed_chrome_dom`;
- `trust_level = observed_page_text_not_verified_fact`;
- `observed_at` - observation completion timestamp;
- `text_sha256` and `text_chars`;
- `selector`;
- `permission_scope`, `permission_origin` and `permission_read_only`.

The reader also rejects a page outside the exact-origin allowlist before reading, and rejects an
origin change during the read. The dashboard Browser tab renders the persisted fields instead of
presenting unlabelled text.

## Evidence

`evidence/managed-chrome-observation.json` was generated with a synthetic page adapter. It
contains:

- an allowed observation with query and fragment removed;
- a denied observation for a page outside the allowlist, with zero events ingested;
- a denied observation where the page changed origin during the read, with zero events ingested.

Both denial paths are checked by `tests/test_browser_provenance.py`. The observation text is
synthetic ("A green light appeared in the habitat.") and is not a real webpage excerpt.

`evidence/prior-archive-integrity.json` confirms that all previously committed qualification
archives still match their manifests.

## Verification

| Check | Result | Transcript |
|---|---|---|
| Backend suite | 86 passed | `validation/backend.txt` |
| Browser provenance + Living focused | 10 passed | `validation/browser-provenance-focused.txt` |
| Frontend suite | 6 passed | `validation/frontend-tests.txt` |
| Production dashboard build | Passed | `validation/frontend-build.txt` |
| Ruff check and format | Passed | `validation/ruff.txt` |
| Whitespace diff | Clean | `validation/whitespace.txt` |
| Prior archives | All manifests verified | `evidence/prior-archive-integrity.json` |

## Limits

- This is **not** native Chrome or extension qualification. No Playwright/Chrome session was
  launched, and no Meta call was made.
- The new provenance describes the managed-Chrome DOM path, not the uncommitted extension side
  panel or its page-snapshot flow.
- The dashboard change is covered by a React component test and production build, not a new
  native screenshot.
- Observation text remains evidence of what was displayed, not verified factual truth. The
  `trust_level` field says so explicitly.
- ALIVE-05's uncommitted permission-race finding is recorded in the handoff; it was not edited in
  Codex's worktree.

## Reproduction

```powershell
uv run pytest -q tests/test_browser_provenance.py
npm test --prefix dashboard
npm run build --prefix dashboard
```
