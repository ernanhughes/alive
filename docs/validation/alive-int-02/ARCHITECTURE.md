# INT-02 integration and reuse

Baseline: `07c0c0663b8e5b1b0b77ec7ed9bde0920805bcfa`, fetched 30 October 2026.
PI-01B and PI-02A are present; PI-02B is absent. This implementation uses the
brief's explicit fixture-backed fallback. A workflow reference is real, but its
stage stays PENDING. Neither reasoning nor action execution is manufactured.

| Owner / existing facility | Integration |
| --- | --- |
| `alive.models.Goal`, `Instance` | Goal and instance foreign keys and ownership checks. |
| `alive.workflows.store`, models and spec | Register immutable versioned definitions, open real pending runs, verify stage operation/type, goal, instance, definition and input hashes on assessment and feedback. No scheduler. |
| `alive.intelligence` 01 contracts/engine | Existing structured fixture interpretation and empirical proposal, with a compatible conflicting-feedback replay correction. |
| `alive.living_policy.choose/update` | Unchanged algorithm. Candidate estimates change only after independent accepted feedback; the active policy snapshot remains frozen. |
| `alive.models.Event`, `Kernel.add_event` | Context/outcome custody, withdrawals/corrections and transition audit. Learning, feedback and audit share one transaction. No parallel evidence service. |
| `alive.db.Database` | Five new tables, unique keys, optimistic revision/hash compare-and-swap, rollback and bounded database-conflict retries. These retries never dispatch a model. |
| Existing authenticated app `ready` dependency | Typed allow-listed GET routes for states/chains and episodes. No public feedback, custody or execution write endpoint. |
| `ModelInvocation`, `PiRun`, `PiProviderRequest` | Read-only receipt resolver verifies authoritative request reconstruction, goal/instance/stage, settled status, output receipt consistency, known usage and charged-token agreement. It grants no admission. |

The five tables are states, episodes, feedback, learning updates and measurement
consumption identities. The last stores only identity/hash and a feedback reference,
with database uniqueness on both evidence ID and source/fingerprint/timestamp hash;
it prevents one observation training two decisions under new custody or a renamed
evidence ID. It does not duplicate evidence content. An immutable
episode snapshot contains the distinct proposal and frozen decision, plus the
original evidence and optional previous episode reference. Its stable episode ID
identifies the decision snapshot; a revisit creates another episode. Feedback binds
that exact snapshot and the frozen selected action, even when the candidate proposes
something different. The authorized/executed action columns must remain NULL by a
database check constraint. A fixture observer's reported action is a separate field.

`fixture.start`, `fixture.assessment`, `fixture.independent_outcome` and
`store.accept_feedback` are trusted internal harness interfaces. Only the separately
custodied fixture outcome can train candidate estimates. Model text and public
browser observations cannot assign the reserved custody event source/type. Trusted
Python and database administrators remain inside the trust boundary; source strings
and hashes do not authenticate arbitrary parties.

Identical feedback is idempotent across restart and independent worker locks.
Changed identity/payload, reused custody or another decision is refused. A
correction/revocation appends an independently controlled notice and quarantines
the candidate; it never rewrites old rewards or silently applies inverse updates.
Withdrawal remains visible beside the original snapshot. Rebuilding quarantined
estimates requires a future reviewed operation.

The Pi resolver is a separate inspection seam. The primary lifecycle cannot admit
live results and never claims synthetic receipt tests are real Pi execution.
PI-01B retains only the raw response hash, while cognition stores parsed output;
the resolver validates both records' available structure and receipt linkage, but
cannot reconstruct the original response bytes from parsed JSON. It does not
claim semantic entailment or a complete response-byte equality proof.

Migration `0009` follows actual head `0008`, adds five tables and removes only
those tables on downgrade. Existing migrations and frozen research are unchanged.
ORM history guards plus read-time hashes detect application-level corruption;
they are not tamper-proof against a privileged administrator rewriting all records.

Canonical demo: supply an explicit disposable `DATABASE_URL`, an ephemeral
`ALIVE_API_TOKEN`, and an empty `ALIVE_META_API_KEY`, then run
`python -B -m scripts.intelligence_check`. It migrates that database, constructs
the two episodes, tests concurrent feedback, restarts ALIVE and checks replay.
Never point this integration harness at a production database.

Future live admission belongs in the existing Cognition reservation/settlement
path and PI-02 workflow executor after qualification. Intelligence adds no provider
client, credentials, runner, new operation registration, policy promotion or
execution capability. Live source custody and production feedback authority are
deliberately unavailable.
