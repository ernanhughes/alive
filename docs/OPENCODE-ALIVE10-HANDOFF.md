# OpenCode ALIVE-10 handoff - Native Intelligence Qualification and Recovery

## Repository and commits

| Item | Value |
|---|---|
| Repository | `https://github.com/ernanhughes/alive` |
| Starting `origin/main` | `5ee1031f36aa411e8675f208a794de13c478fea0` (ALIVE-09 merged) |
| Branch | `opencode/alive-10-native-intelligence` |
| Policy/UI/native harness | `77ee709` - corrected v2 policy, panel semantics, native harness |
| Evidence builders | `021462b` - reproducible comparison, controlled evidence and archive scripts |
| Archive/handoff commit | `ca9a9cc` - frozen archive, manifest and handoff |
| PR | [#14](https://github.com/ernanhughes/alive/pull/14); initial head `ca9a9cc`, review-only |

Status names are deliberately separate:

- `ENGINEERING_PASS`
- `NATIVE_SYNTHETIC_PASS`
- `NATIVE_META_NOT_RUN`
- `RESEARCH_ADVANTAGE_NOT_DEMONSTRATED`

## What changed

### Feedback semantics

The panel now says **Useful - this note helped me** and **Not useful - this note did not help me**,
with a separate explanation that repeated unhelpful notes may pause automatic analysis for this goal
and page and that the owner can analyse anyway. Feedback controls are disabled for no-action,
uncertain and fresh-analysis states, and cannot attach to a previous candidate note.

### Independent evidence

Policy `companion-feedback-usefulness-v2` stores evidence by excerpt SHA inside
`goal_id|url|language`. Support is the number of distinct excerpt hashes, not the number of feedback
rows.

| Event | Result |
|---|---|
| three ratings of one unchanged excerpt | one evidence unit; no pause |
| three distinct excerpts | support 3 |
| repeated identical snapshot | no extra support |
| same note same rating | idempotent |
| same note changed rating | one revision |
| different note same excerpt same rating | audit row only; no policy update |
| changed goal/URL/language | separate context |

### Recovery

- Pause threshold remains support >= 3 and useful rate <= 0.20.
- After 3 paused observations, one bounded periodic probe is authorised for the next snapshot.
- The probe still requires grant, reviewed hash and Governor budget.
- Owner correction resets the suppression counter and is recorded.
- A failed Governor check rolls back the reset and correction.
- Exact useful recall remains before adaptive pause.

### Migration

An ALIVE-09 v1 policy row is left in place and a v2 row is created with `migrated_from` metadata.
Existing validated feedback is backfilled into distinct evidence units. No database migration was
added.

## Native qualification

`scripts/native10.py` starts:

- an isolated current-branch backend on a free loopback port;
- a fresh SQLite database after Alembic migration;
- a controlled local page server;
- a local Meta-compatible synthetic HTTP stub;
- system Chrome with a fresh profile and a temporary unpacked extension copy.

The harness writes evidence under `.alive/native10-*`; `scripts/archive10.py` sanitises it into
`archives/ALIVE-10/`.

Actual journey:

1. three distinct observations analysed and rated not useful;
2. first paused observation -> `no_action`;
3. second paused observation -> owner correction -> one analysis;
4. three more paused observations;
5. bounded probe -> analysis -> useful feedback -> support 4, rate 0.25;
6. duplicate analysis -> 409; wrong origin -> 403; modified hash -> 403; budget -> 409;
7. backend restart -> policy v11 persists, notes 5 -> 5, calls 5, stale grant 403.

Provider usage: **5 synthetic calls, 750 tokens, estimated $0.0016875, paid $0.00**.

Chrome version `155.0.8059.85`. The real extension service worker, storage, observer, panel,
backend and SQLite path were exercised. Chrome did **not** produce a docked side-panel target under
`Extensions.triggerAction` in headless or headful runs; the extension page was used. This limitation
is recorded in `native-status.json` and must not be described as a side-panel qualification.

## Comparison

`archives/ALIVE-10/evidence/policy-comparison.json` is a frozen decision-level replay with eight
predeclared labelled observations; no model was called.

| Arm | Calls | Labelled useful | Useful missed | Paused | Probes |
|---|---:|---:|---:|---:|---:|
| Corrected adaptive v2 | 5 | 2 | 2 | 3 | 1 |
| ALIVE-09 v1 | 3 | 0 | 4 | 5 | 0 |
| Simple one-negative | 1 | 0 | 4 | 7 | 0 |
| Constant analyse | 8 | 4 | 0 | 0 | 0 |

The corrected policy recovers where v1 remains paused. It still misses useful analyses that constant
analysis would obtain. No superiority claim is made. Counterfactual cost avoided is an estimate.

## Verification

| Check | Result |
|---|---|
| Backend suite | 133 passed |
| Companion focused | 23 passed |
| Frontend suite | 7 passed |
| Production build | Passed |
| Ruff check/format | Passed |
| Extension JavaScript syntax | Passed |
| Native synthetic journey | Passed |
| Prior archives | All manifests unchanged |

Reproduce:

```powershell
uv run pytest -q
uv run pytest -q tests/test_web_experience.py
uv run python -m scripts.native10
uv run python -m scripts.alive10_evidence
uv run python -m scripts.alive10_compare
uv run python -m scripts.archive10
```

## Meta

No Meta inference was run. The bounded request in
`archives/ALIVE-10/evidence/meta-qualification-status.json` is:

- maximum 8 calls;
- maximum 12,000 tokens;
- maximum estimated $0.10;
- pinned model `muse-spark-1.3`;
- no automatic paid retry;
- isolated database and Chrome profile;
- redacted evidence only.

Owner approval is required separately. Credentials being present is not approval.

## Review focus

1. Confirm repeated identical excerpts cannot inflate support.
2. Confirm revisions replace, rather than add, evidence.
3. Confirm the periodic probe is bounded and still permission/Governor-gated.
4. Confirm owner correction resets the pause only after all checks pass.
5. Confirm exact useful recall precedes adaptive pause.
6. Confirm the panel cannot attach feedback to a previous note.
7. Confirm native evidence is labelled as extension-page, not docked side-panel.
8. Confirm comparison language does not claim adaptive superiority.
9. Confirm previous archives are unchanged.

## Handoff

Codex/Claude should audit the policy migration, evidence-unit semantics, probe authorisation,
panel feedback targeting and native evidence claims. The branch is review-only; do not merge or
enable auto-merge.
