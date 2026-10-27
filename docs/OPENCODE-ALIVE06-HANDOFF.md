# OpenCode ALIVE-06 handoff - Contextual Browser Intelligence

## 1. What the codebase already provided

ALIVE-05 was merged into mainline as PR #9 after this review cycle began. The merged companion
already provided:

- Owner goals, exact-page grants, reviewed snapshots, model notes and explicit usefulness
  feedback.
- Exact goal/URL/excerpt reuse after a positive rating.
- Restart revocation, conservative interrupted-call settlement and a pre-inference grant check.
- Native Chrome side-panel flow for two exact documentation pages.
- A redacted ALIVE-05 qualification archive with two native Meta calls.

The ALIVE-05 integration also added the revocation hardening in PR #9: revocation serializes with
worker registration, a worker rechecks the grant before inference, and pre-start cancellation
settles its reservation.

## 2. What was genuinely missing

The companion could analyse any authorised excerpt even when the owner goal had no relationship to
it. A user could save an unrelated goal, authorise a page, and still spend a model call on an
irrelevant observation. There was no persisted **no action warranted** outcome and no server-side
relevance gate. The panel also did not explain why analysis was or was not appropriate.

## 3. What was implemented

- `goal_relevance(goal, excerpt)` in `alive/web_experience.py`:
  - exact lowercase content-word overlap;
  - explicit `deterministic-goal-excerpt-overlap-v1` policy;
  - matched terms, term counts and an explicit non-semantic basis;
  - no model, embedding or paid call.
- `WebCompanion.decide()` now returns `no_action` when no content term overlaps. It persists the
  decision with the snapshot, creates no note and makes no provider reservation.
- `WebCompanion.analyse()` independently recomputes relevance and returns HTTP 409 for an
  unrelated state. The extension button is disabled too, but the server is authoritative.
- The side panel shows the relevance result, matched terms, basis and no-action explanation.
- Relevant goals continue through the existing recall/analyse policy; feedback still gates reuse.
- The companion panel heading is now “Contextual choice”.

No new model role, embedding model, learner, migration, store, Governor or provider abstraction
was added.

## 4. Files changed

| File | Change |
|---|---|
| `alive/web_experience.py` | Relevance policy, no-action decision, server-side analysis gate |
| `tests/test_web_experience.py` | Relevance, no-action and direct-API-blocking tests |
| `extension/panel.js` | No-action messaging, relevance display, button state |
| `extension/panel.html` | Contextual choice section and relevance styling |
| `docs/ALIVE-05.md` | Documents the ALIVE-06 gate |
| `docs/ALIVE-06.md` | Protocol, demonstration and limits |
| `README.md` | ALIVE-06 product summary |
| `archives/ALIVE-06-CONTEXTUAL-BROWSER/` | Controlled evidence and validation |

## 5. Tests executed

| Command | Result |
|---|---|
| `uv run pytest -q` | **98 passed** |
| `uv run pytest -q tests/test_web_experience.py tests/test_living.py` | **19 passed** |
| `npm test --prefix dashboard` | **7 passed** |
| `npm run build --prefix dashboard` | Passed |
| `uv run ruff check alive migrations scripts tests` | Passed |
| `uv run ruff format --check alive migrations scripts tests` | 86 files formatted |
| Prior archive manifests | All verified unchanged |

## 6. Evidence type and results

`archives/ALIVE-06-CONTEXTUAL-BROWSER/` contains:

- `evidence/contextual-decisions.json` - controlled FastAPI/SQLite journey with a synthetic
  provider.
- `evidence/prior-archive-integrity.json` - ALIVE-02 through ALIVE-05 and interim archives intact.
- `validation/` - backend, focused, frontend, build, Ruff and whitespace transcripts.
- `manifest.json` - SHA-256 and byte count for every payload.

Controlled results:

| Step | Result |
|---|---|
| Relevant Python goal | `analyse`, matched term `python` |
| Bounded synthetic note | validated, 1 synthetic provider call |
| Useful feedback, same excerpt | `recall`, zero new calls |
| Unrelated coolant goal | `no_action`, no matched terms |
| Direct analysis of unrelated state | HTTP 409, no provider call |

**This is simulated controlled evidence, not native Chrome or Meta qualification.** Paid calls: 0.
No raw webpage, profile, token or API key is archived.

## 7. Security and permission checks

- Relevance is computed before provider reservation and enforced again in the analysis endpoint.
- A no-action decision cannot be converted into a model call through the API.
- The existing exact-page grant, 30-minute expiry, navigation/tab revocation and Governor budget
  checks remain in force.
- No origin, selector, operation, budget or model pin was expanded.
- No paid inference was made.
- Prior archives were verified unchanged.

## 8. Known limitations

- Lexical overlap is not semantic relevance. False negatives are possible; the panel tells the
  owner to revise the goal if the page should be analysed.
- Relevance does not establish factual truth. The model note remains an interpretation; its
  evidence quote is checked separately.
- The panel change is covered by backend tests and static review, not a new native side-panel
  Playwright journey.
- Native Chrome and Meta were not rerun for ALIVE-06. Ports `8000` and `5173` remain occupied by
  the primary worktree.
- The exact two-page companion still does not generalise to arbitrary websites.

## 9. Starting and ending commits

- Starting `origin/main`: `7ad0642d457aec7cd196b9f11d6d484a566acdc5` (merge of PR #9).
- Feature commit: `321139d` (add contextual goal relevance and no-action decisions).
- Evidence/handoff commit: `68f3b2c`.
- Branch: `opencode/alive-06-contextual-browser`.

## 10. Branch and PR

- Branch pushed: `opencode/alive-06-contextual-browser`
- PR: [#10](https://github.com/ernanhughes/alive/pull/10)
- Initial PR head: `68f3b2c`; this handoff update is the final docs-only tip.
- PR target: `main`
- State: open, review-only, not auto-merged.

## 11. Integration conflicts

- Built directly on merged mainline ALIVE-05; no dependency on the old uncommitted branch.
- No migration change.
- `alive/web_experience.py` and the extension panel are the only product-code overlap points.
- ALIVE-05's exact-match reuse and feedback semantics are preserved.

## 12. Recommended next step for Codex

1. Review the PR and merge if the lexical relevance policy is acceptable.
2. Run a native Chrome/Meta qualification on free ports with owner authorization if desired; use a
   separate archive and never overwrite ALIVE-05/ALIVE-06 evidence.
3. If semantic relevance is later desired, evaluate it separately against this deterministic
   baseline. Do not present lexical overlap as semantic understanding.
