# ALIVE-11 — Native intelligence qualification plan

Status: **PREPARATION ONLY — not implemented or qualified**. ALIVE-10 acceptance
and integration must occur first. Planning baseline is PR #14 plus its closeout
correction, not an assertion that ALIVE-11 is already on main.

## Gates

1. Owner accepts ALIVE-10 and merges PR #14.
2. Record the actual integrated main commit; create an isolated ALIVE-11 worktree.
3. Freeze the native protocol and pass synthetic preflight on that source.
4. Present the final provider/scenario/budget details and obtain separate explicit
   approval before paid inference. Prior broad spending consent is not substituted
   for this handoff's stage-specific gate.
5. Review ALIVE-11 evidence before any ALIVE-12 implementation.

No real model request was sent to prepare this document. The ALIVE-11 archive
currently records preparation status only, with zero executed calls/tokens/cost.

## Environment and authority

Use a fresh Chrome profile, free loopback backend/page ports and a new database.
SQLite is sufficient for the native controller journey; keep the existing
PostgreSQL CI regression and explicitly distinguish its coverage. Migrate the new
database; verify its path, served source commit and policy v2 before testing.

Use the shipped extension when possible. If free-port controlled pages require a
test copy, record the exact config/manifest patch and all source hashes. Restrict
it to the isolated backend and controlled page origin. Never broaden the shipped
extension or observe account pages, arbitrary websites or browser history.

The actual goal, reviewed excerpt/hash, exact-page grant, expiration, Governor,
reservations, structured provider request, feedback and persistent policy must be
used. No fixture may replace the production decision function or Governor.

Strip inherited provider URL/key aliases and unrelated role overrides from the
child environment. Synthetic preflight must point both base and explicit completion
URLs to its local stub and use a synthetic key. Real qualification uses only the
intended Meta endpoint and a locally supplied key; never log the key or copy the
owner's normal database/profile into the isolated environment.

## Proposed Meta configuration and ceiling

Read-only configuration inspection on 2026-10-27 found:

| Item | Value |
| --- | --- |
| Companion request model | `muse-spark-1.3` (pinned in companion source) |
| Provider origin | `https://api.meta.ai` |
| Explicit completion URL override | None configured |
| Provider credential | Configured locally; not printed or copied here |
| Current provider timeout | 30 seconds |
| Current default output limit | 1,536 tokens |
| Proposed qualification output limit | At most 512 completion tokens per request, validated in preflight |
| Paid completion requests | At most 8, including failures; 5 planned core calls |
| Aggregate charged-token ceiling | 12,000, including conservative unknown-usage reservations |
| Aggregate estimated spending ceiling | $0.10; stop at any ceiling |
| Automatic retries | Zero |

The existing application price formula uses $1.25/M uncached input, $0.15/M cached
input and $4.25/M output. These are code estimates, not a fresh provider price quote.
At the highest of those rates, 12,000 tokens imply at most $0.051 under that formula.
Historical ALIVE-05's two calls suggest roughly $0.013 for five comparable calls,
but this is a projection from different inputs, not a guarantee. Verify published
pricing/model availability and the isolated configuration before requesting approval.
If rates change, revise the proposal before execution.

Use the existing accounting mechanism with campaign-level call/token/estimated-cost
checks across restart. The current per-note $0.10 check alone is not an eight-call
campaign ceiling. Reserve before dispatch, include failures, and stop if the next
reservation cannot fit. Short reviewed excerpts and output bounds must fit the
actual reservation formula; reduce scope rather than bypass the 12,000-token limit.
Never reset expenditure or replay unknown completions after restart.

## Frozen core journey

Use genuinely distinct controlled research observations with clear source/version
identities, not arbitrary suffixes appended to one unchanged excerpt.

1. Establish a persistent goal, authorise the controlled page, review the first
   excerpt and verify its hash. Meta call 1 produces a structured evidence-linked note.
2. Repeat on distinct excerpts 2 and 3: Meta calls 2 and 3.
3. Exercise negative feedback as explicitly labelled qualification-operator
   interventions; verify three distinct evidence units. These scripted ratings are
   controller tests, not independent measurements of model usefulness.
4. Review a related fourth observation: pause with no provider reservation or call.
5. Use explicit correction on a further reviewed snapshot: Meta call 4. Keep its
   usefulness unassessed unless an owner actually rates it; do not invent a rating.
6. Observe three paused situations after the correction reset. Old paused snapshots
   must remain ineligible without correction, even when the probe threshold is reached.
7. Designate one fresh snapshot for the periodic probe: Meta call 5. A labelled useful
   operator intervention should restore eligibility at support 4/rate 0.25. Record
   eligibility as distinct from dispatch, and verify the one-attempt constraint.
8. Revisit an exact positively rated excerpt: recall with zero new calls. Observe
   another related excerpt and show the new policy consulted before an outcome.
9. Restart the backend and Chrome. Verify identical policy/notes/settled usage,
   revoked prior grants, no inference replay and explicit reauthorisation.
10. Verify expired/revoked grant, changed hash, wrong origin, duplicate analysis,
    missing correction and exhausted budget reject without unauthorised inference.

The remaining three proposed calls are a ceiling for separately declared diagnostics,
not automatic retries or permission to select a favourable output. Preserve all
malformed results, quote failures, provider errors and timeouts. Stop and report an
incomplete qualification when needed. Real owner usefulness assessments, if collected,
must be recorded separately from scripted branch-coverage interventions.

## Docked side-panel acceptance

Investigate action registration readiness, active tab/window selection, Chrome
version, real user gestures and headful versus headless behaviour. Enumerate native
targets and verify the actual docked panel; do not infer it from extension-page load.
Do not redesign the extension merely to make automation pass.

Manual fallback: in the isolated profile load the recorded extension copy, open the
controlled page, click ALIVE's toolbar entry, capture the full browser with panel
docked beside that page, connect to the isolated backend and execute the reviewed
journey. Capture consent, feedback, paused/probe states, correction and restart.
Record operator actions, screenshots, backend events, hashes and remaining automation
limits. If it cannot be demonstrated, mark docked presentation NOT_QUALIFIED.

## Evidence and evaluation

Archive a versioned protocol before execution, exact source/config hashes, source
and excerpt fingerprints, decisions before outcomes, note/citation validation,
explicit feedback provenance, policy revisions, grants/revocation, corrections,
actual provider usage, latency, failures and restart continuity.

Keep native synthetic, native Meta, controlled API, frozen decision replay and
estimated counterfactual results separate. A constant analyse-when-authorised
baseline faces the same declared observations and information. Report useful
opportunities missed; fewer calls alone is not a quality gain. Do not charge a
simulated baseline with invented measured usage. Freeze a separate paired paid
comparison only if its extra calls fit an explicitly approved protocol and ceiling.

Public evidence excludes credentials, profiles and raw unrelated browsing. Retain
local full usage and original failures; export bounded controlled excerpts or hashes
and clearly labelled interpretations. Hash all archive payloads. If a protocol
changes after results, preserve the original and version the correction.
