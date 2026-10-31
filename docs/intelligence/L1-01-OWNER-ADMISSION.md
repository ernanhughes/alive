# L1-01 — Live owner admission

Status: implementation complete for review. No automatic merge. No model call, no paid inference.

## What it adds

A real, owner-approved source can now reach the existing workflow runner without a laboratory
fixture grant. The closed profile `approved-repository-inspection` runs `repository.inspect@1.1.0`
over exactly the files of one PI-03B source approval and reads nothing else.

```
dashboard / API            owner machine (OS user)            runner
prepare review  ───────▶   inspect review
(no authority)             approve --confirm-sha256 <digest>
                           (CLI only; principal must equal
                            the source approver)
start (API, digest) ◀──────────────────────────────────────▶  publish identical Grant
                                                              → existing WorkflowRunner
```

1. `POST /api/v1/admissions` prepares an immutable `owner-admission/v1` review: source inventory
   and digests, goal, recipe hash, workflow definition hash, capability binding, the exact proposed
   `Grant`, limits and expiry. `review_sha256` is the digest of those terms. It grants nothing.
2. `python -m alive.admission approve <id> --confirm-sha256 <digest>` is the only approval path.
   The API has no approve route. The digest must match and the local principal
   (`owner-cli:<os user>`) must equal the principal that approved the source.
3. `POST /api/v1/admissions/{id}/start` with the same digest publishes the Grant, reserves the
   Governor budget through `Cognition.admit_owner_workflow`, and calls the unchanged runner. A retry
   returns recorded history; it never redispatches.

## Trust boundaries

* Every gate (`prepare`, `approve`, `start`, and each stage through `workflows.context.authorized`)
  re-resolves policy, instance, expiry, goal, Governor configuration, recipe hash, definition,
  binding, deployment policy and `custody.resolve` for the source approval.
* A Grant carrying `admission_ref` or provenance `admission-owner` is only valid if its event is the
  admission's recorded `authorization_ref`, byte-identical to the reviewed terms, and the approval
  receipt is an `admission-owner` event with the exact payload. A hand-published Grant cannot stand
  in for it.
* `/api/v1/events` accepts only browser event types from `extension`/`user`; it cannot write
  `admission-owner` or `workflow-owner` events.
* Terms and receipts are immutable (ORM guards) and rows are never deleted.
* The Governor ceiling is shared with the attention auction (`investigation_reservation`). Owner
  admission refuses while autonomy is running or another inquiry is non-terminal.

## Limits of this milestone

* Capture and reference identity do not establish semantic truth. `semantic_status` is `unverified`.
* No inference: `max_model_calls = max_output_tokens = 0`, no outbound access, 30 s ceiling,
  at most 20 files and 32 KiB.
* Model-assisted analysis, evidence validation and result review belong to L1-02 and later.
* PDF capture stays unavailable (PI-03B).

## Verification recorded for this branch

* `tests/test_owner_admission.py`: 28 tests, including forged Grants, forged approval receipts,
  event-ingest forgery, wrong digest and principal, revoked/expired/withdrawn/changed prerequisites,
  cross-instance substitution, SQL tampering and cancellation during a read.
* Guard mutants killed by that file: digest and principal confirmation, start digest check, approval
  receipt requirement, `verify_grant` hook, authorization identity, receipt source.
* Migration `0014` (head after `0013`) upgraded, downgraded and re-upgraded on disposable
  PostgreSQL 16; the PostgreSQL migration-chain tests pass there.
* Dashboard: 108 unit tests and the production build pass; the admission pane has recorded-response
  tests.
* Not run here: browser E2E, Docker image build, Linux container pass, full backend suite.
