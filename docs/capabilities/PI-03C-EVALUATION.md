# PI-03C controlled evaluation

This is deterministic validation evaluation, not evidence of LLM reasoning quality. Expected
outcomes were specified as controlled source contents and literal expected classifications in
`tests/test_validation_capabilities.py`. Candidate output never supplies its own gold label.

| Controlled condition | Expected outcome |
| --- | --- |
| Exact file id/hash and in-range quote | Identity and quote match; semantics remain unverified |
| Captured `answer = 1`, finding claims it assigns 99 | Citation can match; independent verification remains false and task outcome unknown |
| Fabricated id/file, empty id, duplicate reference, wrong item digest | Separate missing/unknown/duplicate/hash classifications |
| Changed capture/scope/instance | Refusal before the source can be validated |
| Wrong line range, traversal, changed quote | Invalid locator, scope refusal, or quote mismatch respectively |
| CRLF capture and LF quotation | Match under the explicit newline-only policy |
| Whitespace-changed quotation | Does not match by fuzzy/whitespace similarity |
| Document/browser section or collection text span | Existing captured identity is used |
| Page coordinate on current capture | Named unsupported kind; no invented PDF support |
| Same scalar fields in reordered JSON | Equal under declared normalized-field policy |
| JSON `true` versus `1` | Different; types are not collapsed |
| Duplicate keys, non-finite values, missing fields, truncated field display | Not comparable |
| Forged model validation output / altered semantic status | Cannot impersonate the actual trusted dependency |
| Source withdrawal, cancellation, historical report | New use refuses/cancels; completed retained report remains inspectable |

Three different deterministic graphs are declared in `alive/validation/workflows.py` and
checked-in JSON under `docs/capabilities/workflows/`: repository inspection/reference/locator
validation; document extraction/section validation; and two-source reference branches joined
by controlled comparison. They run through actual registration, scoped source approval,
trusted fixture owner grant, WorkflowRunner, result recording, replay and authenticated
Observatory inspection. These are real **controlled owner-harness** executions, not claims
that a new general live-owner approval route exists. The closed L1 admission profiles are unchanged.

The document graph is deterministic. It does not substitute for the required authorized-Pi
research workflow, whose qualification remains blocked by PR #83's security review and a
separately admitted document-analysis role. No new inference is invoked from this branch.

Qualification results, exact baseline/head, mutation receipts, PostgreSQL/Docker/browser runs,
CI and independent-review status belong in the delivery record. Unrun checks remain explicit.
Timings from unit tests are not deployment throughput benchmarks. Resource ceilings are
manifest-enforced; all three deterministic examples use zero model calls/tokens and no paid
inference. No semantic effectiveness or Level 2 superiority claim is made.
