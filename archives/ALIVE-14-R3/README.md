# ALIVE-14-R3 qualification archive

Status: **ENGINEERING_PASS**, **NATIVE_SYNTHETIC_PASS**,
**EXPERIMENT_PROTOCOL_VALIDATED**, **META_READY_FOR_APPROVAL** (subject to
independent audit and explicit owner approval), **NATIVE_META_NOT_RUN**,
**OWNER_USEFULNESS_NOT_MEASURED**, **RELATIONSHIP_USEFULNESS_NOT_DEMONSTRATED**.

Baseline: `767b2951552a9ee89836040c9bccd52869f4e1af` (ALIVE-14-R2 merge).
No paid inference was performed. No merge or auto-merge was requested.
ALIVE-01 through ALIVE-14-R2 archives are preserved unchanged.

## Frozen identity

- Protocol: `protocol/relationship-experiment-v3.json`
- Protocol SHA-256: `85fe891cee31bf93d178c4cba2102642b8f4b5e666a0ee426186d5735eb5a71b`
- Sealed answer key: `protocol/answer-key-v3.json`
- Answer-key SHA-256: `255e706dd569634d1710a50831f65a6dd6eb7dabc5ee56e1cd763b382554b43d`
- Experiment ID: `alive14-r3-paired-v3`
- Seed: `20261102`
- Tasks: 9; inference calls: 18; retries: 0

## Contents

| Path | Meaning |
|---|---|
| `protocol/relationship-experiment-v3.json` | frozen protocol v3 |
| `protocol/answer-key-v3.json` | sealed reference answers and prohibited claims; not for model requests |
| `evidence/review09-prefix.json` | REVIEW-09 reproduction against merged R2 |
| `evidence/real-run-preview-manifest.json` | exact real-run payload/request hashes and reservations; no calls executed |
| `evidence/approval-request-template.json` | non-approval template; `human_approval=false` |
| `evidence/native-synthetic.json` | native Chrome evidence |
| `evidence/native-r3-blind.png` | genuine docked-panel screenshot |
| `evidence/runs/...` | full synthetic runner evidence: state, outputs, results, analysis, restart, run manifest |
| `validation/backend.txt` | full backend test transcript |
| `validation/research-memory.txt` | focused research-memory transcript |
| `validation/alive14r3-experiment.txt` | runner/protocol test transcript |
| `validation/extension.txt` | extension test transcript |
| `validation/frontend.txt` | frontend test transcript |
| `validation/build.txt` | production build transcript |
| `validation/ruff.txt` | lint/format transcript |
| `validation/native.txt` | native command/result summary |
| `validation/preflight.txt` | synthetic full-run summary |
| `validation/prefix-repro.txt` | pre-fix defect reproduction |
| `validation/real-preview.txt` | real prepare summary |
| `validation/verify-protocol.txt` | R3 hash verification |
| `validation/archive.txt` | this archive verification |
| `manifest.json` | SHA-256 and byte length for every payload except itself |

## What is proven

- The pre-fix event-order leak reconstructed 6/6 conditions; the corrected
  path suppresses treatment-linked output events, randomizes creation order,
  hides output IDs and redacts paired analyses while collecting.
- A and B share one instruction and one schema; only authorised historical
  context differs.
- Valid abstentions with high confidence are accepted and rateable.
- The runner executes every phase with zero cost, gates real execution behind an
  exact approval record, and recovers without replay after restart.
- The v3 protocol is frozen, neutral, salted-committed and sealed before any
  rating.
- The native panel completes rating, reveal, archive and read-only retrieval
  without raw HTTP commands.
- Injection remains source data; the application payload gains no tools or
  private-memory keys.
- No paid calls occurred.

## What is not proven

No real Meta call, human owner usefulness rating, semantic truth verification or
population-level inference. The synthetic ratings are a scripted null pattern
identical for A/B/C by task; they exercise the pipeline and are not evidence
about memory value. Automated PII/secret redaction is not implemented. The
budget is a planning bound, not an authorisation.

A real pilot requires the separate owner approval described in
`docs/ALIVE-14-R3-EXPERIMENT.md` and recorded against
`evidence/real-run-preview-manifest.json`.
