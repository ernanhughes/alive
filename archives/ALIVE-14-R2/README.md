# ALIVE-14-R2 qualification archive

Status: **ENGINEERING_PASS**, **NATIVE_SYNTHETIC_PASS**, **NATIVE_META_NOT_RUN**,
**META_READY_FOR_APPROVAL** (subject to independent recheck),
**OWNER_USEFULNESS_NOT_MEASURED**, **RELATIONSHIP_USEFULNESS_NOT_DEMONSTRATED**.

Baseline: `a4dbf25e6c4611ef4248297426b1cd6c267e0c72` (ALIVE-14-R1 merge).
Product source commit: `c31f4f57d2a6a8ca48ad1d0ec37be263ed8f484d`.
Protocol commit: `2463da5`; canonical LF SHA-256:
`bd08e2e6b9e7f4804af16daaca5b5a12a2d07d83eb19ae082527ef1da2add5dc`.
PR: https://github.com/ernanhughes/alive/pull/22 (draft, review-only).
CI: all eight PR checks passed (backend Ubuntu/Windows, dashboard, first-contact PostgreSQL).
No paid inference was performed. No merge or auto-merge was requested.

## Evidence

| File | Meaning |
|---|---|
| `protocol/relationship-experiment-v2.json` | frozen eight-task, three-condition paired experiment protocol; not executed |
| `evidence/preflight.json` | synthetic A/B/C preflight, 24 outputs, owner-endpoint lifecycle, reveal and archive |
| `evidence/native-synthetic.json` | native Chrome current-only, history-assisted and blind-rating journey |
| `evidence/research-relationship.png` | genuine docked-panel capture |
| `validation/*.txt` | full, focused, extension, frontend, build, Ruff, native and preflight transcripts |
| `manifest.json` | SHA-256 and byte length for every payload except itself |

## REVIEW-08 corrections

- Current-only mode implemented without historical fields or hidden retrieval.
- Frozen seed `20261101` accepted.
- Blind lifecycle is `collecting -> revealed -> archived`; reveal is POST; post-reveal ratings rejected.
- Duplicate experiment IDs refused.
- Native panel has an owner-facing blind rating interface.
- Successor protocol includes novel controlled facts, a current-only-solvable control and misleading controls.
- Final dispatch revalidates grant, snapshot, historical memory, hashes, provider, model, reservation and cap.
- Rating view hides condition/provider/model/token/cost; assignment is protected.
- Exact Meta preview includes instructions, input, schema, request hash, reservation and allowance.

## Frozen experiment

- 8 tasks: 4 novel controlled facts, 1 current-only-solvable control, 3 misleading controls.
- Recent owner-approved stratum explicitly not populated.
- Conditions A (current-only), B (history-assisted), C (direct history).
- Seed `20261101`; 16 inference calls; no retries.
- Budget proposal only: $0.035 expected, $0.34 worst case, $0.40 ceiling.
- No paid Meta calls.

## Native synthetic

Chrome `155.0.8059.85`, genuine docked side panel, local synthetic provider:

- exact payload/request preview;
- current-only and history-assisted analyses;
- malformed output rejected;
- cache reuse and scripted feedback;
- anonymous blind evaluation with rating completion, reveal and archive;
- withdrawal invalidating consent; restart; zero external calls.
- 3 synthetic note calls, 0 paid calls.

## Boundaries

No real Meta call or human owner usefulness rating. Quotation provenance is not semantic truth. The
preflight owner ratings are synthetic and must not be reported as human feedback. Budget figures are
planning estimates and require current pricing verification and separate owner approval.
