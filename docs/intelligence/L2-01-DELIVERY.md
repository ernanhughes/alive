# L2-01 — Delivery report

Branch `codex/l2-01-intent-interpretation` (built in an isolated worktree from `main` at `2f27f3a`).
Status: draft, awaiting independent review. **Integration readiness only: no live model has been
run, so nothing here shows that interpretation is good.**

## Delivered

* Versioned interpretation contract, typed interpreter role and context policy
  (`alive/intent/`, [contract](L2-01-INTENT-CONTRACT.md)).
* Bounded context: goal, file names and sizes, trusted catalogue projection; no file content.
* Capabilities `intent.interpret@1.0.0` (one model call) and `intent.validate@1.0.0`, workflow
  `owner-intent-interpretation`, Bespoke recipe and closed admission profile
  `intent-interpretation` with its own source operation `intent.interpret`.
* Deterministic resolution of proposals against the catalogue the model saw, using the unchanged
  selector for eligibility; immutable `intent_recommendations` history (migration `0015`).
* Routes `POST/GET /api/v1/admissions/{id}/recommendation` (compose is deterministic, no model).
* Dashboard: procedure choice, disclosure ("file content: not sent"), recommendation panel that
  separates the owner's words, the model's interpretation and the trusted check, with hand-off to
  the separate review.
* Evaluation harness with three strategies, negative controls and exact ablation costs; isolated
  mutation harness; documents (architecture, contract, evaluation, security, this report).
* One unrelated fix: `tests/test_source_capability_seam.py` enumerated the manifest catalogue
  without PI-03C's four capabilities, so it failed on `main`; they are now listed.

## Verification run

| Check | Result |
| --- | --- |
| L2-01 tests: 41 scenario/adversarial + 5 evaluation, SQLite, fake Pi | 46 passed |
| Same 46 against the **real pinned Pi** with the scripted provider | 46 passed |
| Same 46 on **PostgreSQL 16** | 46 passed |
| PostgreSQL migration-chain suites; `0015` downgrade then upgrade | passed |
| Wide regression: cognition, runner, authority, cancellation, observatory, Pi gateway/egress, destination, L1-01/L1-02, bespoke, ratchets, capability seam, PI-03C validation | 478 passed, 2 skipped (pre-existing skips) |
| Dashboard unit tests / production build | 120 passed / built |
| Docker image build; `compose.e2e.yaml` (app + PostgreSQL + Playwright, existing journeys) | built; "E2E OK: 6 groups passed" |
| Ruff check and format | clean |

The exact-head CI result is reported on the PR, not here.

## Mutation campaign (isolated copies of HEAD; the working tree is never edited)

20 single mutants and 1 compound, `scripts/l201_mutations.py`. A kill needs a behavioural test
failure; pattern mismatches and setup errors count as `invalid` (none occurred).

| Result | Guards |
| --- | --- |
| killed (16) | goal preservation (validator and assembly); no fuzzy id matching; exact version; eligibility authoritative; interpreter recipe not offered (compound of two edits); catalogue the model saw; fence goal, catalogue and instructions/contract; no file content in context; compose artifact integrity; Governor request ceiling; immutable history; model-fit ordering; recommendation grants nothing |
| survived, redundant (2) | adapter catalogue digest; Grant-input catalogue binding. Each is also enforced by the disclosure-equality check and the fence. **Killed together** (compound C01) |
| survived, redundant by accident (1) | compose requiring the interpretation profile: another kind of admission lacks the disclosure fields, so composing fails with a `KeyError` that surfaces as 409. The explicit guard is defence in depth and is not isolated by a test |
| survived, unreachable (1) | compose comparing the artifact's goal with the approved goal: the artifact is digest-protected and its goal derives from the same Grant input, so no test can alter one without the other |

## Not done

* **Live-model evaluation and empirical ablation.** The 3-strategy results are by construction;
  quality of each context condition is unmeasured. See [evaluation](L2-01-EVALUATION.md).
* **Browser E2E of the interpretation flow.** The existing Docker journeys pass; the new panel has
  component tests on responses recorded from the backend, nothing drives it in a real browser.
* **Independent adversarial review**, Linux container run and the full backend suite at the PR head
  (left to CI).
* Sources other than repositories; clear-text retention, encryption and deletion remain owner
  decisions (see `L1-02-SECURITY-DECISIONS.md`).
* No measurement of latency or token use beyond exact request sizes.

## Independent review: what to attack

* Can an interpretation or recommendation start, authorize or widen anything? (no route exists;
  `execution` is fixed; try the API and the stored record.)
* Does file content ever reach the model, the events or the record? (names and sizes only.)
* Can a near-miss recipe id, a wrong version or the interpreter's own recipe become a
  recommendation? Can the model's goal replace the owner's?
* Can the catalogue, goal, model, endpoint or role contract change between review, start,
  reservation and dispatch without refusal? Which layer refuses each?
* Does replay or re-composition ever dispatch a model? Is history rewritten by a recipe change?
* Do the benchmark labels favour the scripted answers? (They were written by the same author.)
