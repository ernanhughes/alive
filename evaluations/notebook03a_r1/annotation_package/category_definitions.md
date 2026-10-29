# ALIVE-NOTEBOOK-03A-R1 — Category Definitions (normative for annotators)

## Relationship (1+; narrowest supported wins)

- **supersession**: A later passage **explicitly replaces** a particular earlier
  policy/proposition (retirement, substitution, fail-closed contract change).
  Requires directed `superseded_claim_ref` → `replacement_claim_ref`. A date or
  rewording alone is insufficient; paraphrased retirement of a specific rule
  counts (S3); reversed serialization does not change direction (S4/dc3d...).
- **contradiction_candidate**: Incompatible propositions under **comparable**
  conditions (same cohort/protocol/comparator/population). Opposite wording
  under different conditions is `scoped_change`.
- **corroboration_candidate**: Genuinely **independent** additional evidence for
  the same finding under matching conditions (different labs/teams). Same-lab
  repetition or verbatim duplication is **not** corroboration (use residual
  `substantive_connection` with duplicate limitation).
- **scoped_change**: Same entities with **different** conditions/comparators/
  corpora/tasks/scopes (FIFO vs LRU, synthetic vs field, 36-memory vs
  18-memory corpora, reaffirmed validity period). Preserve scope; do not infer
  contradiction or universal gain.
- **substantive_connection** (residual): Other meaningful link: shared
  project continuity with explicit limitation (lexical overlap ≠ proof),
  duplicate restatement requiring anti-double-counting, paraphrased
  offline-retrieval equivalence, reaffirmed continuity without replacement.
  Use only when no specific category fits.
- **independent_observations**: Adequately supported **lack** of substantive
  link (different subsystems, word-sense collision, different referents,
  unrelated campaigns). Requires sufficient evidence for the lack.
- **unsupported_claim**: A presented headline/assertion **exceeds** its
  supporting passage (universal batch claim from single-batch sample; semantic
  superiority against retained NOT-DEMONSTRATED qualification). A useful
  correction (`set_aside`), not a hidden abstention.
- **unknown**: Epistemic inability to decide (missing baseline/conditions,
  date-only mention without detail, high-overlap distractors without
  comparable entities). Always with `insufficient`/`unknown` + `abstain`.

## Sufficiency

- `sufficient_for_candidate`: Evidence supports a candidate proposal with stated
  qualifications (still reviewable, not verified truth).
- `insufficient`: Missing conditions/evidence prevent a defensible proposal.
- `unknown`: Cannot determine sufficiency from supplied text.

## Applicability

- `applicable`: Finding applies as stated (matching conditions).
- `scoped`: Applies only under stated narrower conditions.
- `not_applicable`: No applicable use (independent lack, unsupported headline).
- `unknown`: Cannot determine applicability.

Standardization (R1 provisional, pending adjudication): all
`independent_observations` use `not_applicable` (corrected 7b8653a... from
`applicable`); see adjudication dossier.

## Decision

- `use_with_qualification`: Retain with explicit scope/limitation.
- `set_aside`: Do not use; record as correction (unsupported headline,
  independent lack) or scoped non-use.
- `abstain`: No justified use/non-use; only decision allowed with
  `unknown`/`insufficient`.

Useful finding (`useful_finding: true`) means retention is justified; it can
never be rewarded by abstention alone. Non-useful cases are judged by
correct non-use (`set_aside`/`abstain` per gold), not by a composite score.
