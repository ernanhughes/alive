# Follow-up refusal classification after PR #90

Addresses the [independent review](https://github.com/ernanhughes/alive/pull/90).

Only an explicit list of standing/Governor budget, consent/revocation, expiry and source-operation
refusals is recorded as `analysis_not_authorized`. Other `Refused` categories produce a separate
`admission.live.followup.failed` event and `followup_failed` response carrying their actual
code-owned category, such as `workflow_identity_changed` or `admission_integrity`. Arbitrary
exception text is not echoed. Unexpected non-`Refused` exceptions retain existing error handling.

The useful interpretation, its recommendation and model receipts survive either outcome.
Identical retry/history reads use that retained result without inference. Failed procedures do
not silently acquire permission to retry. No authorization or integrity check is bypassed.

Model availability now depends on model-call outcomes independently of the follow-up procedure.
A successful model interpretation can remain available while its next procedure is blocked or
fails. The dashboard distinguishes "Follow-up failed" from "Follow-up not authorized" and shows
the retained actual reason.

Verification:

```text
uv run pytest -q -o addopts="" tests/test_live_admission.py -k 'internal_followup or followup_budget or followup_revocation'
npm --prefix dashboard test -- src/admission/live.test.tsx
npm --prefix dashboard run build
```

Six focused backend cases passed: budget, mid-request revocation and injected workflow identity,
integrity, Governor configuration and binding failures. The adversarial cases verify the event
type, actual cause, useful retained interpretation, identical replay and exactly one dispatch.
Eight dashboard tests, the production build, changed-file Ruff/format and `git diff --check`
passed. This is offline regression coverage; no new live inference, AI-quality acceptance, full
suite or CI/workflow changes are claimed.

This PR is the bounded repair. Context-aware follow-up, retrieval of earlier model findings,
evidence-based revision and broader live quality evaluation remain the next separate milestone.
