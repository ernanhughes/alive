# L1-02 — Delivery report

Branch `l1-02-governed-analysis`, based on `f7b97a1` (the head of L1-01, PR #80). **Dependent on
L1-01; do not merge ahead of it.** Status: draft, awaiting independent review.

## Delivered

* Closed admission profile `approved-repository-analysis` (`alive/admission/profiles.py`), separate
  from the unchanged no-inference profile; review shows the model disclosure.
* Versioned workflow `owner-repository-analysis` v1 (`read → analyze → validate → record`) and the
  Bespoke recipe `approved-repository-analysis`.
* Capabilities `repository.analyze@1.0.0` and `repository.validate_findings@1.0.0` with code-owned,
  fingerprinted implementations in `alive/analysis/`.
* Typed role contract, bounded context builder, citation-existence validation, report composition.
* `GET /api/v1/admissions/{id}/report`; the existing Admission pane now selects the procedure, shows
  the disclosure, and renders the report as inert text.
* Benchmark with independent labels, adversarial tests, a mutation script.
* Documents: architecture, model admission and role contract, evaluation, this report, review handoff.

No database migration: reviews are stored in the existing `owner_admissions` JSON.

## Verification actually run

| Check | Result |
| --- | --- |
| `tests/test_repository_analysis.py` (37) and `_units.py` (30) | 67 passed |
| Same end-to-end test with the real pinned Pi (`ALIVE_TEST_REAL_PI=1`) | 1 passed |
| Wide regression: cognition, workflow runner/authority/cancellation/observatory, Pi gateway/egress, source seam, intelligence, owner admission | all passed (one skip) |
| Admission, bespoke, capability, gateway ratchet, source and migration suites | passed after the changes below |
| Dashboard: unit tests / production build | 112 passed / built |
| Ruff check and format on `alive`, `tests`, the mutation script | clean |

Changes forced by existing guards, each by design not by waiver: the Meta construction and
credential ratchets (the destination host comes from a new `providers.meta_endpoint_host`; the CLI
does not construct a provider), the manifest-catalogue test (two new identities, no earlier hash
changed) and the Bespoke catalogue count (6 → 7).

## Mutation receipts (partial, stopped at the owner's request)

`scripts/l102_mutations.py` breaks one guard at a time. Results before it was stopped:

| Guard | Result |
| --- | --- |
| Dispatch fence: instructions, context digest, source digest | killed |
| Governor request ceiling at review | killed |
| Analyzer: supplied bytes equal the approved capture | killed |
| Reservation: outbound approval, model identity, role contract, exact context, implementation identity, stage input hash | **survived** |
| Review: disclosure terms equal | **survived** |
| Two mutants | invalid (stale patterns), not counted |
| M15–M23 (analyzer source digest, typed-role gate, Governor start/meta gates, citation checks, byte ceiling) | not run |

The reservation survivors are redundant layers: the same cases are also refused by `runner.start`,
the Grant comparison or the dispatch fence, so a single mutant does not change behaviour. A kill
needs a test that disables the outer layer first; I have not written those. Treat these guards as
**untested in isolation**. (Stopping the campaign left mutant M15 applied in the working tree; it was
found, restored and the suites rerun before commit.)

## Not done

* Browser E2E, Docker build and smoke, Linux container run, full backend suite and Windows/Linux CI
  at the exact head (left to CI).
* PostgreSQL migration checks: not applicable, no schema change; the L1-01 PostgreSQL check was not
  rerun.
* Live-model run and the second LLM baseline.
* The second half of the mutation campaign and the isolating tests above.
* Latency, token and database-write measurements.

## Offline demo

```bash
uv run python -m alive.admission install
```

registers both profiles on the owner machine. The reproducible offline run, with a scripted
provider and a fake Pi, is the end-to-end test; add `ALIVE_TEST_REAL_PI=1` and
`ALIVE_PI_RUNTIME_DIR` to use the pinned Pi:

```bash
uv run pytest -q tests/test_repository_analysis.py::test_owner_authorized_analysis_runs_end_to_end
```

A live run needs `ALIVE_META_API_KEY`, `ALIVE_MODEL_TRANSPORT=pi`, Cognition started with provider
`meta`, a capture approved with both operations (see `L1-02-MODEL-ADMISSION.md`), then the Admission
pane: choose "Analyze with one model call", prepare, approve with the printed local command, start.
That path has **not** been run and is not claimed as qualified.
