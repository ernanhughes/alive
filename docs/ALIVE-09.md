# ALIVE-09 - The Living Research Companion

Status: **PASS_WITH_LIMITATIONS** for the engineering connection.

Native Chrome and Meta qualification were not run. The evidence is a controlled companion API
sequence with SQLite persistence and a synthetic provider. No paid inference was made.

## What ALIVE already had

- Persistent goals, exact-page grants, reviewed snapshots, notes, explicit usefulness feedback and
  exact goal/URL/excerpt recall.
- ALIVE-06/07 relevance decisions: `analyse`, `recall`, `no_action` and `uncertain`.
- A deterministic Governor, provider reservations, restart revocation and cancellation.
- ALIVE-08's controlled simulator and its negative primary result.

## The missing connection

The companion's feedback influenced only exact-note recall. There was no persisted decision policy
updated by feedback and consulted by a later nonidentical related decision.

ALIVE-09 adds the smallest bounded connection:

1. Snapshot decisions record the current adaptive policy version and hash.
2. Completed owner feedback updates a context-level useful/not-useful count.
3. A later related snapshot consults the policy before analysis.
4. Three independent ratings in `goal_id | URL | language` with at most 20% useful can suppress
   analysis.
5. The owner can explicitly correct the no-action decision; the correction is persisted and
   bounded by the existing grant and Governor.
6. Useful feedback after correction restores analysis when the useful rate exceeds 20%.
7. Exact validated useful recall takes precedence over adaptive suppression.

## Feedback contract

A completed note feedback event records:

- note and snapshot identity through the existing parent relationship;
- goal ID, URL and language context;
- useful/not-useful rating;
- whether the event was a revision of a prior rating;
- policy version/hash before and after;
- whether the note came from an explicit owner correction;
- timestamp through the existing row and policy history.

Feedback semantics:

- **Same rating repeated:** idempotent; returns the existing row and does not update the policy.
- **Different rating:** revision replaces the prior evidence in the same context and performs one
  policy update. It does not train twice.
- **Factual truth:** not inferred from usefulness. The note's exact quotation validation remains
  separate.
- **No synthetic feedback:** the runtime never creates a rating itself.

## Adaptive policy

Policy ID: `companion-feedback-usefulness-v1`.

- Context: `goal_id|URL|language`.
- Minimum support: **3** completed ratings.
- Maximum useful rate for suppression: **0.20**.
- With insufficient support: retain the default `analyse` recommendation.
- With support >= 3 and useful rate <= 0.20: recommend `no_action`, with
  `no_action_source="feedback_policy"`.
- With support >= 3 and useful rate > 0.20: recommend `analyse`.
- Policy state persists as a `WebExperience` row of kind `policy`; no migration was needed.
- Policy history is bounded to 50 updates.
- Decisions store the policy version/hash and adaptive support/rate.

The policy never grants a permission, expands a page allowlist, bypasses the Governor, chooses a
model, or turns an unsupported action into a permitted one.

## Owner correction

`POST /browser-experience/analyse` accepts `owner_correction=true` for a no-action state.

The correction:

- is explicit;
- requires a currently active exact-page grant;
- still passes the reviewed-hash check and the Governor's call/token/cost checks;
- is restricted to the reviewed snapshot;
- records a `correction` row with prior action, relevance status, adaptive policy and policy hash;
- does not grant broad or permanent permission;
- does not imply that the resulting analysis is useful or factually correct.

Language-uncertain analysis keeps its existing explicit `allow_uncertain_analysis` override and is
also recorded as a correction row.

## Exact recall

Exact recall remains unchanged:

- validated note;
- same goal, URL, excerpt hash and language;
- latest owner rating useful.

A useful exact match is returned even if adaptive feedback would otherwise suppress analysis. A
changed excerpt, different goal or negative/reverted rating prevents exact reuse.

## Controlled evidence

Real companion API, isolated SQLite, synthetic provider:

| Step | Result |
|---|---|
| Three related excerpts | three `analyse` decisions; policy v0 -> v3 |
| Three owner ratings: not useful | context 0 useful / 3 not useful |
| Fourth related excerpt | `no_action` from feedback policy; zero calls |
| Direct analysis without correction | HTTP 409; zero calls |
| Owner correction | correction row; one bounded analysis |
| Feedback: useful | policy v4; context 1 useful / 3 not useful (0.25) |
| Next related excerpt | `analyse`, suppression ended |
| Duplicate feedback | idempotent; no policy update |
| Revised feedback | one replacement update, not a double update |
| Restart | policy v6 persists; fresh grant required; no replay |

The controlled sequence's 5 provider calls include a separate idempotency context. The main
context used four bounded analyses: three initial and one owner-corrected; the suppressed state
used zero.

## Baselines

`evidence/baseline-replay.json` is a decision-level replay, not native evidence:

| Case | Adaptive | Simple one-negative | Frozen / constant |
|---|---|---|---|
| 3 negative, next not useful | no_action | no_action | analyse |
| 3 negative, next useful | no_action unless owner correction | no_action unless owner correction | analyse |
| 1 negative, next not useful | analyse (insufficient support) | no_action (premature) | analyse |
| 3 positive | analyse | analyse | analyse |

The replay makes the trade-off explicit: suppression saves calls when history is right and can
miss a useful analysis when history is wrong. The correction path is therefore part of the feature,
not an optional extra.

This is not a statistically powered outcome study. No claim of improved task quality, Meta
superiority or general browser intelligence is made.

## Relationship to ALIVE-08

ALIVE-08 remains unchanged and negative on its primary comparison. Its post-hoc always-retrieve
diagnostic is not promoted to a preregistered result. ALIVE-09 does not use that diagnostic to claim
a learning advantage; it demonstrates a bounded production feedback-to-decision connection.

## Security

- Exact-page grant, 30-minute expiry, navigation/tab/restart revocation preserved.
- Pre-inference grant recheck preserved.
- Direct analysis of a no-action state is rejected without an explicit correction.
- Revoked grants still return 403 for correction attempts.
- Governor call/token/cost checks still precede inference.
- Interrupted calls settle conservatively; no paid replay.
- No browser-history ingestion, Docker search service, new provider or new permission was added.

## UI

The existing extension side panel now shows:

- the decision policy version and feedback support;
- useful/not-useful counts;
- whether analysis was suppressed by owner feedback;
- an explicit “Analyse anyway (owner correction)” or “Analyse anyway (language override)” action;
- policy version before/after when feedback is saved;
- the existing estimated tokens/cost and Governor-bounded operation.

No second dashboard was created.

## Verification

| Check | Result |
|---|---|
| Backend suite | 127 passed |
| Companion focused | 17 passed |
| Frontend suite | 7 passed |
| Production build | Passed |
| Ruff check/format | Passed |
| Extension JavaScript syntax | Passed |
| Prior archives | All manifests unchanged |

## Reproduction

```powershell
uv run pytest -q tests/test_web_experience.py
uv run python -m scripts.alive09_evidence
uv run pytest -q
uv run ruff check alive migrations scripts tests
npm test --prefix dashboard
npm run build --prefix dashboard
node --check extension/background.js
node --check extension/panel.js
```

## Limitations

- Controlled API and SQLite evidence; no native Chrome or Meta qualification.
- Synthetic provider; no actual model reasoning.
- The minimum support of three ratings is deliberately conservative and may leave the policy
  inactive for a long time.
- The baseline replay is decision-level; it does not prove better task outcomes.
- The context is goal/page/language, not open-ended semantic topic similarity.
- The companion still covers only two exact documentation pages.
- The policy is a small count-based mechanism, not deep reinforcement learning.
- No browser-history ingestion or cross-device inference was implemented.

## Conclusion

The real companion now records a causally linked browser experience, applies a versioned
feedback-driven policy on a later related observation, supports idempotent/revisable feedback,
preserves exact recall, and records bounded owner corrections. That is an engineering connection,
not a general learning or native-browser claim.
