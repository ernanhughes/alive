# Codex ALIVE-14-R3 handoff

## 1. Repository

- Verified `origin/main`: `767b2951552a9ee89836040c9bcdd52869f4e1af`
  (ALIVE-14-R2 merge).
- Branch: `codex/alive-14-r3-experimental-integrity`.
- Isolated worktree: `C:\Projects\alive-worktrees\alive-14-r3`.
- Protocol freeze commit: `8828302e286d4b7607bc38274a1972c4d4dcd18b`.
- Implementation commit, PR and CI: to be recorded after push. Review-only; no
  merge or auto-merge.
- Prior ALIVE-01-14 archives, including ALIVE-14-R2, are unchanged.
- Paid Meta calls: **0**.

## 2. Statuses

- **ENGINEERING_PASS**
- **NATIVE_SYNTHETIC_PASS**
- **EXPERIMENT_PROTOCOL_VALIDATED**
- **META_READY_FOR_APPROVAL** (subject to independent audit and explicit owner
  approval; not authorisation to run)
- **NATIVE_META_NOT_RUN**
- **OWNER_USEFULNESS_NOT_MEASURED**
- **RELATIONSHIP_USEFULNESS_NOT_DEMONSTRATED**

## 3. REVIEW-09 corrections

| Finding | Correction | Evidence |
|---|---|---|
| Blind conditions recoverable from events, 24/24 | Assignment generated first; outputs created in seeded random order; output/assignment/rating events suppressed until reveal; output IDs removed from create response; paired analyses redacted while collecting | `research_blind.py`, `test_blind_run_does_not_leak_condition_order_or_assignment`, `review09-prefix.json` |
| Valid abstentions rejected | Common paired validator separates schema, provenance, sufficiency and abstention; confidence is not a truth probability | `validate_paired_output`, validator matrix tests |
| No reliable execution harness | Resumable prepare/approve/execute/rate/reveal/analyse/archive coordinator with approval record, restart recovery and durable dispatch markers | `scripts/alive14r3_experiment.py`, `tests/test_alive14r3_experiment.py` |
| A/B different tasks, schemas and instructions | One `PAIRED_INSTRUCTIONS`, one `PairedAnswerOutput`, identical current fields; B adds only the authorised historical keys | `test_paired_conditions_share_instruction_schema_and_isolation` |
| Questions disclosed history | Nine neutral questions; no history/previous/older/prior wording | protocol hash and v3 task audit test |
| Primary usefulness metric undefined | Binary owner-rated supported-usefulness endpoint with explicit thresholds and missing-data rules | protocol v3, `docs/ALIVE-14-R3-EXPERIMENT.md` |
| Assignment hash not reproducible | Salted canonical commitment over stable task/condition/output hashes; opening disclosed only on reveal; verified on reveal and restart | `verify_commitment`, reveal results, runner tests |
| Reveal/rating provenance | Dedicated POST reveal, rating capability, closed status, read-only results GET, post-reveal 409, owner-attestation field distinct from synthetic/scripted provenance | `revealed_results`, blind tests |

## 4. Common A/B contract

Both inference conditions use the same instruction, schema, model pin, research
question, output ceiling and no-retry policy. A has no historical keys. B adds
`historical_memory_id`, `historical_url`, `historical_sha256` and
`historical_excerpt` only. The runner asserts full key parity and byte-identical
instructions/schema before approval.

The request plane exposes a new `analysis_mode="paired"`; R2 current-only and
history-assisted modes remain for compatibility. The paired path is stored as
`research_paired_analysis`.

## 5. Validator behaviour

`validate_paired_output` accepts:

- a supported answer with one or two exact source quotations;
- cross-vocabulary evidence;
- a valid abstention with `sufficient_evidence=false` and a reason, including
  high self-reported confidence.

It rejects:

- non-exact quotations;
- quotations attributed to an unauthorised source;
- a supported answer with no evidence;
- an abstention with no reason;
- malformed schema.

It does not claim semantic truth. `semantic_verification=false` and
`explanation_status=unverified_model_interpretation` are always recorded.

## 6. Runner state machine

```
prepared -> approved -> executing -> awaiting_ratings
         -> ready_to_reveal -> revealed -> analysed -> archived
blocked (source/consent/provider/protocol failure)
```

Each command is explicit. No phase silently authorises the next.

- `prepare` validates protocol and answer-key hashes, creates an isolated DB,
  seeds exact sources, previews all A/B payloads and records hashes/reservations.
- `approve` requires an exact approval record for real runs. Synthetic approval
  is separate and labelled non-human.
- `execute` re-previews, rechecks hashes, executes exactly once, persists an
  append-only JSONL and recovers validated attempts after restart without replay.
- `rate` uses the native panel or the explicitly synthetic path.
- `reveal` verifies the commitment and closes ratings.
- `analyse` opens the sealed key only after reveal and applies the endpoint.
- `archive` reopens the DB, retrieves read-only results, verifies rating count
  and commitment, then writes a run manifest.

ALIVE revokes live grants on restart. The runner re-activates only grants bound
to the approved immutable snapshots and records `grant_reactivations`. The
approval record is the re-consent for those exact snapshots.

## 7. Frozen v3 protocol

- 9 tasks; 18 inference calls; no retries.
- 3 novel controlled constraints, 1 current-sufficient, 1 irrelevant-history,
  2 misleading-history, 2 abstention, 1 injection control.
- Neutral questions; sealed answer key; no answer-key content in requests.
- Seed `20261102`; seeded task order and within-task shuffle.
- Real prepare: 92,148 reserved tokens; worst case **$0.391635**; protocol
  planning bound **$0.393090**; ceiling **$0.45**.
- Protocol SHA-256: `85fe891cee31bf93d178c4cba2102642b8f4b5e666a0ee426186d5735eb5a71b`
- Answer-key SHA-256: `255e706dd569634d1710a50831f65a6dd6eb7dabc5ee56e1cd763b382554b43d`

## 8. Privacy and injection

Only selected current and historical excerpts are transmitted, with URL and
SHA-256. No hidden retrieval; no unrelated memory. Historical text is untrusted
source data. The payload construction adds no tools or private-memory keys. The
injection control is enforced at the application boundary, not by model refusal.
Automated PII/secret redaction is **not implemented**; the owner must review the
exact preview and may withhold consent or withdraw the memory.

## 9. Native Chrome

Chrome `155.0.8059.85`, genuine docked side panel, isolated backend and fresh
profile:

- current and saved historical sources;
- paired A/B previews and exact consent;
- synthetic A/B execution with a valid abstention card;
- condition-neutral blind cards and progress;
- commitment prefix before rating;
- six ratings through the native UI, reveal, archive;
- read-only results after archive and restart;
- post-reveal rating 409;
- injection containment;
- 4 synthetic note calls, 0 paid calls.

Evidence: `archives/ALIVE-14-R3/evidence/native-synthetic.json`,
`archives/ALIVE-14-R3/evidence/native-r3-blind.png`.

## 10. Validation

- Full backend: 202 passed.
- Focused research memory: 52 passed.
- Runner/protocol: 4 passed.
- Extension: 11 passed.
- Frontend: 7 passed.
- Build: passed.
- Ruff check/format: passed.
- R1/R2 archives and ALIVE-14 reconciliation: passed.
- R3 protocol/answer-key verification: passed.
- Native synthetic: `NATIVE_SYNTHETIC_PASS`.

## 11. Remaining owner approvals

No real Meta execution is authorised. Before a paid pilot:

1. Independently audit prompt parity, blinding, abstention and the runner on a
   fresh database.
2. Verify current Meta pricing and endpoint against the prepared payloads.
3. Approve the exact `real-run-preview-manifest.json` payload hashes, 18 calls,
   92,148 reserved tokens, $0.45 ceiling, no-retry policy, redaction position
   and owner-rating procedure.
4. Provide an approval file with `human_approval=true`, approver identity and
   timestamp.
5. Only then run `execute --mode real` and complete ratings through the native
   panel.

The correct claim remains: the experiment is built, frozen and locally
qualified; whether historical memory improves usefulness is not measured.
