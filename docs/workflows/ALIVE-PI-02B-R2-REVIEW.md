# PI-02B-R2 independent review handoff

Also read the [integrated-source qualification](ALIVE-PI-02B-R2-INTEGRATION.md).
The branch now includes main's ARCH-01 changes and an opt-in test-fixture ordering
correction; original R2 results below remain historical, with new receipts separate.

Keep PR #69 draft and unmerged. Review delta from
`b2d06caa59c411a87951afc76440a368717e8dfd`; implementation commit is
`a9ec88d1c247f2b692c47f388511660b479c82d5`. Later commits retain qualification,
documentation and a test assertion for the bounded authority category. The final
review head is in the PR body. No independent R2 approval is claimed.

Read [R2 report](ALIVE-PI-02B-R2.md), its mutation matrix and original immutable R1
probes before trusting the test counts. R1 fixes are limited to artifact metadata,
explicit context provenance and small error/validation presentation boundaries.
The runner's state machine, literal adapters, admission, Pi architecture and recovery
policy are unchanged.

Review these concrete cases:

1. Inject failure/cancellation after the record stage but before workflow settlement.
   Artifact GET must remain forensic: explicit FAILED/CANCELLED, completed record stage,
   false `workflow_completed`, no independently verified truth. Repeat for quiescent
   UNKNOWN recovery and normal completion. Hash substitution still returns 404.
2. Trace public `Observation` ingestion to protected owner-event custody. Approve a
   named extension event and exact payload hash with `untrusted_browser` classification.
   It may execute, but must never acquire trusted provenance or semantic verification.
   Missing/wrong source classification, altered bytes, wrong goal and withdrawal refuse.
3. Re-run the R1 A/B mutations through `scripts.workflows_r2_mutations.py`. Check each
   intended assertion, not only process exit. A10 remains redundant for dispatch with
   B1 and is explicitly not a kill. A7 uses the valid A7v syntax. B4 uses a valid FAILED
   stage substitution so teardown errors cannot be counted as detection.
4. Inspect stage re-entry, control-only dependency and existing inquiry ownership tests.
   These are future-regression guards; they do not establish an original public exploit.
5. Inspect error classification at adapter/output/commit boundaries and the durable Pi
   rejection mapping. Ensure UNKNOWN and reserved-resource settlement are preserved
   when failures occur after a possible external effect. Private exception text stays out.
6. Provide uncited model claims through real Pi. Schema/reference checks may pass;
   semantic status stays unverified, independent verification/feedback false, and
   execution completion remains a separate fact. No evidence coverage is inferred.
7. Verify final image bytes against LF Git blobs, not the Windows checkout. Preserve
   the R1 receipt's original CRLF interpretation rather than silently rewriting it.
8. Verify genuine PostgreSQL contender refusal and successor replay. Multiple active
   host processes are forbidden by the production lease; do not describe this as a
   multi-process stage-claim race or distributed worker qualification.

Suggested commands (disposable environments only):

```text
python -B -m pytest -q -p no:cacheprovider tests/test_workflow_r2_history.py tests/test_workflow_r2_fence.py tests/test_workflow_r2_provenance.py tests/test_workflow_r2_invariants.py
python -B -m scripts.workflows_execution_mutations
python -B -m scripts.workflows_r2_mutations
python -B -m scripts.workflows_execute_check
python -B -m scripts.workflows_execute_check --database-url <disposable-postgresql-url> --process-probe
python -B -m pytest -q -p no:cacheprovider
```

No paid inference. For every finding, provide a concrete failing scenario and exact
source location. The raw review scripts remain audit data, not entry points to run
unchanged: they contain the original reviewer's output paths. R2's scratch harness
reads only their static mutation descriptions and never executes them.
