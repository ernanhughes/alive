# ALIVE-05 — Real Browser Experience

ALIVE now offers a read-only documentation companion in Chrome's native side panel.
This milestone tests continuity and feedback-driven reuse on two owner-authorised
public pages. It does not establish adaptation across arbitrary websites, better
task accuracy, or a benefit from predictive representation learning.

## Install and run

Use the current `main` branch after this milestone is accepted. The ALIVE-05 companion is
integrated into mainline alongside ALIVE-04 and the shared browser provenance work.
Install Python 3.13, uv, Node 24+, PostgreSQL with pgvector, and stable Chrome.
The existing [Windows installation](../README.md#run-on-windows) installs locked
dependencies, applies migrations (now through `0006`), and starts local services.
Use an empty local database for an independent reproduction; migrations also
preserve an existing qualified ALIVE database.

1. Copy `.env.example` to ignored `.env`. Configure `ALIVE_DSN` or `DATABASE_URL`
   for your PostgreSQL database and `ALIVE_META_API_KEY` for Meta. Do not commit keys.
2. Run `uv sync --locked`, `npm ci --prefix dashboard`, then `./scripts/dev.ps1`.
   Keep the backend bound to `127.0.0.1`; do not tunnel it publicly.
3. Open `chrome://extensions`, enable Developer mode, choose **Load unpacked**,
   and select the repository's `extension` directory. After updating an existing
   installation, use **Reload** there; MV3 worker code can otherwise remain cached.
4. Open either exact page below and click ALIVE in Chrome's Extensions menu or
   pinned toolbar. The native side panel opens beside the page.
5. Connect using the local token from ignored `.alive/token` (or your configured
   `ALIVE_API_TOKEN`). Save a goal or resume one from the server's saved-goal list.
6. Click **Authorise this page**. Review the excerpt, then **Send selected
   observation** to save it locally. **Send reviewed excerpt to Meta** is a
   separate explicit action, with one bounded call and no retries.
7. Read the note and its limitations. Rate **Useful** or **Needs work** honestly.
   Close Chrome and restart ALIVE. Reopen the page, reconnect/resume the goal,
   authorise the tab again and save its preview. An unchanged excerpt with a
   positively rated matching note selects recall with zero new inference calls.

Authorised pages:

- <https://docs.python.org/3/tutorial/>
- <https://developer.mozilla.org/en-US/docs/Web/JavaScript/Guide>

Subpages, query strings, fragments, account pages and unrelated URLs are excluded
by exact runtime checks. Chrome host permissions are host-level even when a path
appears in the manifest; the manifest declares the two documentation hosts and
the local backend. ALIVE enforces the narrower page and per-tab scope itself.
Installing the extension does not begin observation or send anything to Meta.

## What persists, and what changes

PostgreSQL stores separate goal instructions, consent records, observed excerpts,
model interpretations, usefulness feedback and action decisions. Raw text is
evidence of what was displayed, not verified factual truth. Model notes cite an
exact quote in the reviewed excerpt; failed citations remain failed ledger entries.
Page instructions cannot grant permissions or trigger actions. There are no
write/click tools for these public pages.

The deterministic `explicit-usefulness-exact-excerpt-v1` rule recommends recall
only when URL, goal ID and SHA-256 of the first 3,000 visible characters match a
validated note whose latest rating is useful. Saving a note alone does not change
the recommendation. A changed excerpt, different goal or negative rating selects
fresh analysis. It does not compare the entire page, infer factual correctness,
optimise a reward function, or transfer P2/P3 synthetic rewards to real websites.

ALIVE-06 adds a pre-analysis goal-relevance gate. The companion computes exact
configured content-token overlap between the owner goal and the reviewed excerpt. If
there is no shared term, it records `no_action`, creates no note and makes no Meta
call; the analysis endpoint independently rejects the same state with HTTP 409.
ALIVE-07 moves the language resources into `config/relevance/`, adds English, Chinese
character n-grams and Arabic normalisation, and returns an explicit `uncertain`
decision for unsupported or mixed scripts. A match is necessary but not sufficient
for analysis, and none of these checks is semantic understanding. See the
[ALIVE-07 protocol](ALIVE-07.md).

Consent expires after 30 minutes and is revoked on navigation, tab closure,
explicit Stop or backend restart. Restart preserves goals, notes, feedback and
Governor expenditure, but never replays inference. Form values and hidden/private
elements are excluded. Stop cancels an active call; unknown usage conservatively
consumes its reservation. Each snapshot permits one inference attempt, with a
$0.10 worst-case application ceiling and existing cumulative call/token limits.
This is an estimate-based application control, not a provider billing guarantee.

The integrated implementation serializes revocation with note registration, checks
the grant again immediately before provider inference, and settles a reservation if
a worker is cancelled before it starts. The ALIVE-05 archive records the original
qualified implementation at `0809f37`; its source hashes are intentionally
historical, not rewritten by the later authorization hardening.

## Reproduce qualification

Run `uv run pytest`, `uv run ruff check alive scripts tests migrations`,
`npm test --prefix dashboard`, `npm run build --prefix dashboard` and
`npm run test:e2e --prefix dashboard`. The browser E2E suite uses the local runtime;
run it before paid qualification, since it deliberately exercises Governor settings.

With services running and a fresh `.alive/browser05` directory:

```powershell
uv run python -m scripts.extension_smoke
uv run python -m scripts.browser05 first
# Inspect .alive/browser05/first-note.json before deciding on a useful rating.
uv run python -m scripts.browser05 feedback
./scripts/stop.ps1
./scripts/dev.ps1
uv run python -m scripts.browser05 revisit
uv run python -m scripts.browser05 mdn
```

The `feedback` command deliberately clicks Useful as a **qualification operator**;
this is an engineering intervention, not independent evidence of user satisfaction.
The runner uses isolated persistent stable Chrome, opens its real side panel using
the toolbar CDP command, and attaches to that native target. It does not substitute
a normal browser tab displaying `panel.html`. The local-habitat extension smoke is
an additional regression, not proof of native-panel operation.

Qualification evidence is in [the redacted archive](../archives/ALIVE-05/README.md).
The original first Meta call succeeded while the native runner's message-polling
step failed; its original database records were recovered without replaying the
call. Subsequent native feedback, restart/recall and MDN runs completed. Failed
engineering attempts are documented rather than presented as additional successes.

## Three-minute demonstration

The public page is an explicitly labelled evidence replay with a three-minute
chapter player and original native-panel capture. It serves no backend or model
credentials. Install locally for the live interaction above.

| Time | Show | Evidence |
| --- | --- | --- |
| 0:00–0:30 | Authorised Python page and saved learning goal | Goal and exact URL |
| 0:30–1:00 | Reviewed excerpt and Meta note | Excerpt hash, note ID, usage |
| 1:00–1:30 | The note exists, but fresh analysis is still recommended | Pre-feedback decision |
| 1:30–2:00 | Operator marks the inspected note useful | Persisted feedback ID |
| 2:00–2:30 | Close Chrome, restart backend, authorise again | New consent, same goal/hash |
| 2:30–3:00 | Recall the same note without a new call | Same-state comparison and limits |

Public replay is not a hosted autonomous agent. The live runtime requires local
installation and the owner's credentials. Two documentation pages and one explicit
usefulness intervention do not establish general intelligence or broad usefulness.
