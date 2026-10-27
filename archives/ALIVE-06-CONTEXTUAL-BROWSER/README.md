# ALIVE-06 contextual browser evidence

This archive records the ALIVE-06 contextual relevance gate for the mainline ALIVE-05 browser
companion. It is **controlled test-harness evidence**, not native Chrome or Meta qualification.

## Provenance

| Item | Value |
|---|---|
| Repository | `https://github.com/ernanhughes/alive` |
| Base | `origin/main` at `7ad0642d457aec7cd196b9f11d6d484a566acdc5` (includes merged ALIVE-05) |
| Branch | `opencode/alive-06-contextual-browser` |
| Evidence kind | Controlled FastAPI/SQLite test harness |
| Native Chrome | **No** |
| Meta inference | **No** |
| Paid calls | **0** |

## What changed

Before this milestone, the companion could analyse any authorised excerpt even when the owner's
goal had no relationship to it. ALIVE-06 adds a deterministic, server-enforced goal-relevance
gate:

- Content-word overlap between the owner goal and the reviewed excerpt is computed locally.
- No semantic model, embedding or paid inference is used for relevance.
- If no content term overlaps, the decision is `no_action`.
- A `no_action` decision creates no note, no provider reservation and no Meta call.
- Direct calls to the analysis endpoint are rejected with `409` for the same state.
- The side panel explains the match terms, the basis and why no action was taken.
- Relevant observations still use the existing exact goal/URL/excerpt reuse policy; rating a note
  useful remains the only way to enable recall.

The matcher is deliberately simple and transparent. It is not semantic understanding and can
produce false negatives; the panel tells the owner to revise the goal if the page should be
analysed.

## Evidence

`evidence/contextual-decisions.json` records the controlled journey:

| Step | Result |
|---|---|
| Goal: “Help me decide where to start learning Python” | Relevant (`python` matched) |
| Reviewed Python excerpt | `analyse` decision |
| Synthetic provider | 1 call, 150 simulated tokens |
| Useful feedback | Validated note rated useful |
| Same goal/URL/excerpt again | `recall`, zero new calls |
| Goal: “Check coolant temperature” | `no_action`, zero shared terms |
| Direct analysis of unrelated state | HTTP 409, no provider call |

The page text is synthetic test text. The provider is a local function returning a fixed note.
No raw webpage, personal browsing data, API key or native Chrome profile is included.

## Verification

| Check | Result | Transcript |
|---|---|---|
| Backend suite | 98 passed | `validation/backend.txt` |
| Web companion + Living focused | 19 passed | `validation/web-living-focused.txt` |
| Frontend suite | 7 passed | `validation/frontend-tests.txt` |
| Production dashboard build | Passed | `validation/frontend-build.txt` |
| Ruff check and format | Passed | `validation/ruff.txt` |
| Whitespace diff | Clean | `validation/whitespace.txt` |
| Prior archives | Manifests verified | `evidence/prior-archive-integrity.json` |

## Limits

- No native Chrome side-panel run and no Meta inference in this archive.
- The extension panel change is covered by backend tests and static review, not a new Playwright
  native-panel test.
- Deterministic lexical overlap is not semantic relevance; false negatives are possible.
- Relevance does not verify factual truth. The note remains a model interpretation.
- The existing ALIVE-05 archive remains unchanged and describes the earlier implementation.
- Two documentation pages and exact-match reuse do not establish general web intelligence.
