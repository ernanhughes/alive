# L1-02 — Delivery report

Applied on current `main` (`0b752ef`, which contains L1-01). An earlier PR (#81) was merged into
the L1-01 branch after L1-01 had already merged, so it never reached `main`; this branch carries
L1-02 onto `main` for qualification. Status: draft, awaiting independent review.

## Delivered

* Closed admission profile `approved-repository-analysis` (`alive/admission/profiles.py`), separate
  from the unchanged no-inference profile; the review shows the model disclosure.
* Versioned workflow `owner-repository-analysis` v1 (`read → analyze → validate → record`) and the
  Bespoke recipe `approved-repository-analysis`.
* Capabilities `repository.analyze@1.0.0` and `repository.validate_findings@1.0.0` with code-owned,
  fingerprinted implementations in `alive/analysis/`.
* Typed role contract, bounded context builder, citation-existence validation, report composition.
* `GET /api/v1/admissions/{id}/report`; the Admission pane selects the procedure, shows the
  disclosure and renders the report as inert text.
* Benchmark with independent labels, adversarial tests, a complete mutation campaign.
* Documents: architecture, model admission and role contract, evaluation, security decisions, this
  report, review handoff.

No database migration: reviews are stored in the existing `owner_admissions` JSON.

## Verification run

| Check | Result |
| --- | --- |
| `tests/test_repository_analysis.py` (48) + `_units.py` (30), SQLite, fake Pi | 78 passed |
| The 48 end-to-end/adversarial tests against the **real pinned Pi** with the scripted provider | 48 passed |
| The same 48 on **PostgreSQL 16** (disposable instance) | 48 passed |
| PostgreSQL migration-chain suites (capability, source, migrations) | passed |
| Docker image build; `compose.e2e.yaml` (app + PostgreSQL + Playwright, existing journeys) | built; "E2E OK: 6 groups passed" |
| Wide regression: cognition, runner, authority, cancellation, observatory, Pi gateway/egress, intelligence, owner admission, ratchets, bespoke, capability, source | passed |
| Dashboard: unit tests / production build | 112 passed / built |
| Ruff check and format | clean |

The exact-head CI result for the PR is reported on the PR, not here.

## Mutation campaign (complete)

`scripts/l102_mutations.py`: one guard broken at a time. A kill requires a behavioural test failure;
a mismatched pattern or a setup error is `invalid`. 25 single mutants, 3 compound.

| Result | Guards |
| --- | --- |
| killed (21) | dispatch fence (instructions, context digest, source digest); reservation exact context, implementation identity, stage input hash, one model call per stage; disclosure operation at review; disclosure terms equal; Governor request ceiling; picker filter; analyzer bytes equal the capture; analyzer source digest; typed role only inside a stage; Meta provider required; Cognition started; citation quotation, locator and file; captured-file digest; byte ceiling |
| survived alone, redundant (3) | reservation **outbound approval**, **model identity**, **role contract**: each is also enforced by a second layer on the same path (`runner.start`; `current_terms` through `authorized()`) |
| survived, equivalent (1) | `current_terms` re-resolving the disclosure operation: approval operations are immutable and the review step already requires them; withdrawal and expiry are caught by the inspect-operation resolve |
| compound, killed (3) | outbound approval (reservation + `runner.start`), model identity (reservation + `current_terms`), role contract (reservation + `current_terms`) |

Which layer enforces each invariant, as demonstrated:

| Invariant | Enforced by |
| --- | --- |
| Disclosure needs the exact approvals | source operation `repository.analyze` (review); the owner-confirmed Grant; the outbound flag (`runner.start` and the reservation, redundant) |
| Approved provider, model and role | `current_terms` and the reservation together; the dispatch fence for model and role contract |
| Source identity in the prompt | analyzer byte comparison with the capture; the reservation's context rebuild; the fence's source digest |
| Second model call | the reservation (`model_invocation_id is None`); a second call needs a second reservation |
| Fabricated citation shown as verified | the validation checks; nothing is ever labelled verified |

No test attacked `outbound_approved=False` before this campaign; the new outbound-approval test has a
live control run to show the dispatch path it guards is reachable.

## Not done

* **Full-stack browser E2E of the Admission pane.** The existing Playwright journeys run in Docker
  and pass, and the pane has component tests against recorded backend responses, but no browser
  test drives the model-backed flow because the running app has no hook for a scripted provider.
* Linux container run of the analysis suite and the full backend suite at the PR head: left to CI.
* **A paid or live-model experiment** and the second LLM baseline. Evaluation numbers come from
  scripted outputs and show pipeline classification only.
* The three security decisions (remote egress, clear-text retention, deletion) are **open owner
  decisions**; see `L1-02-SECURITY-DECISIONS.md`.
* Latency, token and write measurements.

## Offline demonstration

```bash
uv run python -m alive.admission install
```

registers both profiles on the owner machine. The reproducible offline run, with the real pinned Pi
and a scripted provider:

```bash
ALIVE_TEST_REAL_PI=1 ALIVE_PI_RUNTIME_DIR=<pinned Pi directory> \
  uv run pytest -q tests/test_repository_analysis.py::test_owner_authorized_analysis_runs_end_to_end
```

Drop `ALIVE_TEST_REAL_PI` to use the fake Pi; set `ALIVE_TEST_ANALYSIS_POSTGRES_URL` to run on a
disposable PostgreSQL. A live run needs `ALIVE_META_API_KEY`, `ALIVE_MODEL_TRANSPORT=pi`, Cognition
started with provider `meta` and a capture approved with both operations (see
`L1-02-MODEL-ADMISSION.md`). That path has not been run and is not claimed as qualified.
