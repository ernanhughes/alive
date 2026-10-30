# Independent candidate review

Reviewed delivery: `3b7f6917c08d02bccd0cfca5e1d2d69547b69d1b` in the clean
`C:/Projects/alive-intelligence-01` worktree. Current main was independently fetched
and is `07c0c0663b8e5b1b0b77ec7ed9bde0920805bcfa`. The 01 implementation/report
were already ported onto that main in `72d9cb8` / `a2b20a3`. Those two commits were
cherry-picked into this fresh delivery branch. Original commits remain intact.

Before integration, reproduced 65 isolated tests, 67 gateway/learning/living/
cognition regressions, the two-episode example, Ruff check and format. The 67-test
run emitted 34 existing Windows Proactor/ZeroMQ selector warnings. No source edits
were made in either original checkout.

Confirmed boundaries from contracts and call sites: the invocation object belongs
to a trusted caller, must enforce the entire StructuredRequest, and owns reservation,
consent, transport, cancellation and settlement. The package checks payload/scope
and response identity but does not authenticate Python objects. The existing gateway
registers only `cognition.role`. Feedback preparation requires an issued proposal,
current independent measurements and exact trusted verifier acceptance; it updates
an immutable empirical policy only after full validation. Shadow predictions have
no active-policy route. The in-memory engine remains limited to 256 issued episodes
and has no cross-process/restart exactly-once guarantee.

Confirmed candidate defect: `evaluate_feedback` treated any subsequent outcome
for a consumed proposal as `duplicate`, including altered content under the same
feedback ID. Reproduction: accept trusted feedback, replace its `result`, submit
again. Original returns duplicate. The compatible integration correction stores
canonical outcome hashes and rejects conflicting replays; the strengthened existing
engine test checks this while retaining the no-second-update expectation. This
defect did not permit a second policy update, but mislabeled conflicting evidence.
Location in the delivered code: `alive/intelligence/engine.py:185` and the replay
guard at line 196. The original guard at the same method had no payload comparison.

The pre-existing `C:/Projects/alive-int-02` worktree had substantial uncommitted
integration work. It was read, never modified. Reviewed source/tests were copied
explicitly into the new worktree for reuse. No previous validation reports or
claimed results were imported as evidence for this delivery.

Additional review of that snapshot found four protections worth tightening:

1. Feedback acceptance revalidated source snapshots but not workflow references.
   `verify_episode` now rechecks the exact run input, immutable definition, pending
   stage and absence of model/Pi linkage on feedback as well as read/assessment.
   Four corruption cases assert no learning. A targeted workflow mutation removes
   this check and must fail its normal regression.
   Location: `alive/intelligence/store.py:126` (`verify_episode`).
2. Independent measurements could share a source ID with conflicting fingerprints.
   This is now refused even when the trusted custody payload contains both.
   Location: `alive/intelligence/store.py:465` (source/fingerprint guard).
3. Receipt inspection accepted any non-NULL usage dictionary. It now requires
   nonnegative integer prompt/completion/total counts, consistent sums and exact
   agreement with the invocation ledger's charged usage and reservation ceiling.
   Location: `alive/intelligence/receipts.py:15` and the settlement guard at line 94.
4. A custody event's unique identity alone does not stop the same measurement
   appearing under a fresh custody event. A transactional identity-only ledger
   now gives evidence IDs and source/fingerprint/timestamp identities one durable
   consumer per instance. Tests attempt both literal and renamed replay across
   different decisions and require rollback of the attempted second update.
   Location: `alive/intelligence/models.py:91` and the inserts in
   `alive/intelligence/store.py:_accept_feedback`.

Cancellation injected after feedback/state preparation rolls back state, learning,
feedback and audit in the same transaction. Public ingestion is the existing closed
browser event/source vocabulary, so it cannot mint fixture custodian or observer
events. There is no new public write path. Hash/citation checks do not prove truth.
These adversarial checks are bounded implementation evidence, not a security proof
or evidence of model intelligence, policy superiority or semantic correctness.
