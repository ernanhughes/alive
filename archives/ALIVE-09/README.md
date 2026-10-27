# ALIVE-09 - The Living Research Companion

Status: **PASS_WITH_LIMITATIONS** (engineering connection); native Chrome/Meta qualification blocked.

This archive records the real browser companion's feedback-to-policy loop. It is controlled API
evidence with a synthetic provider, not native Chrome or Meta evidence. No paid inference was run.

## Provenance

| Item | Value |
|---|---|
| Repository | `https://github.com/ernanhughes/alive` |
| Base | `origin/main` at `0ff4748d2186c7344d635fffaba25f159589fb71` (ALIVE-08 merged) |
| Branch | `opencode/alive-09-living-research-companion` |
| Policy | `companion-feedback-usefulness-v1` |
| Context | `goal_id | URL | language` |
| Minimum feedback support | 3 |
| Maximum useful rate for suppression | 0.20 |
| Native Chrome | **No** |
| Meta inference | **No** |
| Paid calls | **0** |

## What was connected

The companion already persisted goals, grants, snapshots, notes, explicit feedback and exact-match
recall. ALIVE-09 connects completed usefulness feedback to a persisted, versioned decision policy:

1. The snapshot decision records the policy version/hash and the adaptive recommendation.
2. Three completed owner ratings in the same goal/page/language context can suppress future
   analysis when the observed useful rate is at most 0.20.
3. A later snapshot consults that policy and returns `no_action` with
   `no_action_source="feedback_policy"` instead of creating a note or provider reservation.
4. The owner can explicitly correct the decision. The correction is persisted, requires a live
   exact-page grant, and does not create broad permission.
5. Useful feedback after a correction changes the context counts. When the useful rate rises above
   0.20, analysis is recommended again.
6. Feedback duplicate/revision semantics are idempotent at the policy layer:
   - same rating again: existing feedback returned, no new update;
   - different rating: revision replaces the prior evidence, one policy update.

The previous exact-note recall remains authoritative for validated, positively rated exact
matches. A feedback policy cannot suppress an exact useful recall.

## Controlled evidence

`evidence/controlled-loop.json` uses the real companion API and SQLite persistence with a synthetic
provider:

| Step | Decision | Policy | Calls |
|---|---|---:|---:|
| Three related excerpts | analyse | v0 -> v3 | 3 |
| Three owner ratings: not useful | policy updated | v3 | 0 |
| Fourth related excerpt | **no_action (feedback policy)** | v3 | 0 |
| Direct analysis without correction | HTTP 409 | v3 | 0 |
| Owner correction + analysis | analyse | v3 | 1 |
| Feedback: useful | policy updated | v4 | 0 |
| Next related excerpt | analyse | v4 | 0 |

The policy context before correction was `0 useful / 3 not useful` (rate 0.0). After the useful
correction it was `1 useful / 3 not useful` (rate 0.25), so suppression ended.

`evidence/restart-proof.json` reopens the real companion against the same SQLite database. The
policy version persists, the next decision still consults support 4, the pre-restart grant is
rejected with HTTP 403, and the stored note count is unchanged (5 before and after). No inference
is replayed.

`evidence/baseline-replay.json` is a controlled policy replay, not native evidence:

| Case | ALIVE adaptive | Simple one-negative | Frozen / constant |
|---|---|---|---|
| 3 negative, next not useful | no_action | no_action | analyse |
| 3 negative, next useful | no_action unless owner correction | no_action unless owner correction | analyse |
| 1 negative, next not useful | analyse (insufficient support) | no_action (premature) | analyse |
| 3 positive | analyse | analyse | analyse |

This comparison shows the trade-off: suppression can save a call when history is right, but can
miss useful analysis when history is wrong. The owner correction path is required and is recorded.

## Feedback and policy contract

- Feedback is owner-rated usefulness, not factual truth.
- The model note's exact quotation check remains separate.
- The policy uses integer counts, not a hidden reward score.
- No model call occurs on a suppressed decision.
- A correction is evidence that the owner disputed the prior decision; it is not automatically a
  positive usefulness rating.
- Policy history is bounded to 50 updates; each update records feedback ID, context, version and
  revision status.
- Decisions store pre-feedback policy version/hash and adaptive recommendation.

## Verification

| Check | Result |
|---|---|
| Backend suite | 127 passed |
| Companion focused tests | 17 passed |
| Frontend suite | 7 passed |
| Production build | Passed |
| Ruff check/format | Passed |
| Extension JavaScript syntax | Passed |
| Prior archives | All manifests unchanged |

## Native qualification

Not run. Ports `8000` and `5173` were occupied by the primary worktree. No process was stopped, no
native Chrome session was opened against it, and no Meta call was made.

## Limits

- Controlled API evidence, not native Chrome.
- Synthetic provider; no actual Meta inference.
- Minimum support 3 is deliberately conservative and may leave the policy inactive for a long
  time; one useful correction can end suppression.
- The baseline replay is decision-level, not a broad outcome study.
- No statistical claim of improved task quality is made.
- The browser companion still covers only two exact documentation pages.
- No browser-history ingestion, Docker search service or cross-device collection was added.
- ALIVE-08 remains a separate negative primary result; its post-hoc always-retrieve diagnostic is
  not a preregistered finding and is not altered here.
