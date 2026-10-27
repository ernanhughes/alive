# ALIVE-14-R2 - Experimental preflight

Status: **ENGINEERING_PASS**, **NATIVE_SYNTHETIC_PASS**, **NATIVE_META_NOT_RUN**,
**META_READY_FOR_APPROVAL** (subject to independent recheck),
**OWNER_USEFULNESS_NOT_MEASURED**, **RELATIONSHIP_USEFULNESS_NOT_DEMONSTRATED**.

Baseline: `a4dbf25e6c4611ef4248297426b1cd6c267e0c72` (ALIVE-14-R1 merge).
R2 product commit for evidence: `c31f4f57d2a6a8ca48ad1d0ec37be263ed8f484d`.
Protocol commit: `2463da5`; canonical LF SHA-256:
`bd08e2e6b9e7f4804af16daaca5b5a12a2d07d83eb19ae082527ef1da2add5dc`.
No paid inference was used.

## REVIEW-08 blockers corrected

| Blocker | Correction |
|---|---|
| Current-only analysis could not execute | New current-only mode with its own payload, instructions and schema; no historical fields or hidden retrieval |
| Frozen seed rejected | Blind-run seed accepts `20261101`; regression test uses it |
| Ratings could be revised after reveal | Explicit `collecting -> revealed -> archived` lifecycle; POST reveal; post-reveal ratings rejected |
| Experiment IDs reused ambiguously | Duplicate experiment IDs are refused |
| Native panel lacked blind workflow | Side-panel blind evaluation selector, rating controls, progress, reveal and archive |
| Textbook-heavy six tasks | New three-stratum protocol: novel controlled facts, optional owner research, misleading controls |
| Task asked about information absent from both sources | New tasks are current-solvable, history-assisted or explicit misleading controls |
| Grant race between reservation and dispatch | Dispatch guard revalidates grant, snapshot, historical memory, source hashes, provider, model, request hash, reservation and USD cap |
| Metadata could reveal condition | Rating view hides condition/provider/model/tokens/cost; assignment is a separate protected row |
| Meta preview not qualified natively | Panel shows exact instructions, input, schema, request hash, reservation and remaining allowance |

## Current-only and history-assisted

- **A current-only:** current excerpt + research question + provenance; no historical fields.
- **B history-assisted:** current excerpt + explicit historical excerpt + question; historical quotation validation remains separate.
- **C direct history:** historical excerpt shown without model synthesis.

A and B use the same pinned model, question, output ceiling and no-retry policy. Their instructions
differ only in available evidence. Current-only abstains when the page does not support the question.

## Consent race closure

The final dispatch guard is under the kernel lock and revalidates:

- live page grant;
- current snapshot hash and excerpt;
- active historical memory and hash for B;
- payload and request hashes;
- provider enablement and identity;
- pinned model;
- Governor reservation and cumulative USD cap.

The regression test revokes a grant after reservation but before the guard's source validation and
asserts zero provider calls. Once a request has actually left the process, revocation cannot recall
it; this is documented rather than claimed otherwise.

## Blind lifecycle

`collecting -> revealed -> archived` is enforced server-side.

- Assignment and output hashes are committed before ratings.
- Seed `20261101` is accepted.
- A rating capability is issued through the authenticated owner view and checked by the server.
- Conditions/provider/model/token/cost are hidden during rating.
- Ratings are append-only revisions with `rater_type`, provenance, rubric version, output hash and
  timestamp.
- Reveal is a deliberate POST, requires all owner ratings, records `revealed_at` and the assignment
  hash, and closes the run.
- Post-reveal ratings are rejected.
- Archive is explicit.

## Synthetic A/B/C preflight

`archives/ALIVE-14-R2/evidence/preflight.json` records:

- 8 frozen tasks from the successor protocol;
- current-only and history-assisted local-stub execution;
- direct historical C text;
- 24 anonymous outputs;
- 24 owner-endpoint ratings exercised synthetically;
- reveal with conditions and assignment hash;
- archive transition;
- zero paid calls.

The owner endpoint was exercised by a script; these are **not human owner ratings**.

## Prompt injection and privacy

The protocol includes an adversarial historical excerpt instructing the model to ignore the question
and disclose private memories. The payload contains it only as untrusted historical source text. The
request has no tools or private-memory keys, and the application does not add retrieval or tool
permissions because of source content. The regression test verifies the bounded payload.

## Native synthetic

Chrome `155.0.8059.85`, genuine docked side panel, local synthetic provider:

- exact preview including request/schema/allowance;
- current-only and history-assisted analysis;
- valid relationship and malformed-output rejection;
- cache reuse and scripted feedback;
- owner-facing blind rating interface with three conditions hidden;
- rating completion, reveal and archive;
- withdrawal invalidating consent;
- restart and zero external calls.

## Remaining limitations

No real Meta call, human usefulness rating, semantic truth validation or population-level inference.
The preflight exercises the owner endpoint synthetically; it does not claim owner ratings.

## Next step

Independent recheck of the revised provider boundary and blind lifecycle, then a separate owner
approval for the frozen R2 protocol and 16-call budget. No paid inference is authorised by R2.
