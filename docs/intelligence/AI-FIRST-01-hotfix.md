# Post-merge review follow-up: partial results and inference status

Addresses findings 1 and 2 in the [independent review of PR #89](https://github.com/ernanhughes/alive/pull/89#issuecomment-6557594348).
The merged live path is preserved. No new authorization framework, schema migration, provider
client, permission or CI configuration is introduced.

## Partial results survive follow-up refusal

Previously, with an allowance of three calls, the first analysis used two calls. A second
goal's successful interpretation used the third, but refusing its follow-up analysis turned
the entire request into HTTP 409. Its useful interpretation and receipt were hidden.

Now a refused follow-up returns HTTP 200 with the retained exchange and a `followup` outcome:
`analysis_not_authorized`, reason `budget_exhausted`, `consent_required`, or
`authorization_unavailable`. The dashboard keeps the reasoning summary and model receipt
visible and explains that the follow-up was not authorized. The outcome uses an existing event
record. Reading history or repeating the same request never retries that blocked follow-up,
including after revocation or restart. Changed goal text or consent with the same retry key
remains a conflict. Unexpected non-authorization exceptions are not silently converted into success.

## Inference status says what the receipts establish

- **LIVE MODEL:** a validated response and settled Pi run/provider request, HTTP 200, response
  hash, matching requested model, and retained evidence that production network transport was used.
- **TEST MODEL RESPONSE:** validated response through an explicitly injected upstream transport.
- **MODEL RESPONSE:** validated response whose transport/settlement evidence is incomplete or
  unknown. Older receipts have unknown transport; they are not retroactively attested as live.
- **MODEL CALL FAILED / NO MODEL CALL:** existing failure/dispatch distinctions remain.

The transport marker is retained in the existing Pi run JSON. Requested model and provider-observed
model are separate receipt fields. Production network receipts establish completion through the
configured endpoint; they do not independently attest the provider's internal model or semantic truth.

## Focused verification

Twelve focused backend scenarios passed, covering the three-call partial-result reproduction,
revocation between interpretation and result, blocked replay, absent/legacy/ambiguous/hashless/
wrong-model receipts, normal repeated calls, cancellation, dispatch-time revocation and Pi
cancellation immediately after PREPARED. Commands (temporary fast-test default preserved):

```text
uv run pytest -q -o addopts="" tests/test_live_admission.py -k "followup or validated_response"
uv run pytest -q -o addopts="" tests/test_live_admission.py::test_three_goals_one_consent_real_dispatch_path_and_retained_results tests/test_live_admission.py::test_cancellation_does_not_redispatch tests/test_live_admission.py::test_revocation_at_pi_dispatch_fence_blocks_outbound_request tests/test_live_admission.py::test_validated_response_alone_cannot_claim_live_inference[wrong_model] tests/test_pi_gateway.py::test_a_cognition_role_runs_through_pi_end_to_end tests/test_pi_lifecycle.py::test_cancel_after_every_durable_transition_ends_terminal[PREPARED]
npm --prefix dashboard test -- src/admission/live.test.tsx
npm --prefix dashboard run build
```

Seven dashboard tests and the production build passed. Changed Python files passed Ruff and
format checks; `git diff --check` passed. No full suite, broader E2E campaign or CI rerun.

The [live regression ledger](AI-FIRST-01-hotfix-evidence.json) records three real production Pi
calls with `muse-spark-1.3-contributor`, one complete report and one budget-blocked interpretation
returned successfully. Retry and backend restart retained both exchanges; provider requests
stayed **3 → 3**. Source and budget were the previously approved public toy scope. This verifies
the functional fix and production status path; it does not establish broader intelligence quality.

## Next evaluation cycle

The earlier semantic overstatements remain in the original ledger. They are not corrected by
citation checks or by this hotfix. Freeze expected observations before evaluating varied goals:
for the existing buggy mean function, `[2,4]` returns 2 rather than 3; `[0,0]` correctly returns
0; `[-2,-4]` returns -2 rather than -3; `[]` returns 0 even though its mathematical mean is
undefined and the desired empty-input policy needs stating. Mixed-sign zero sums provide another
counterexample to "never correct". Judge unsupported generalizations, not only procedure choice
and citation existence. No new semantic-quality acceptance is claimed here.
