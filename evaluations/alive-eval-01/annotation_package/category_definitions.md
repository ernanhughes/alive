# ALIVE-NOTEBOOK-03A-R2 — Category Definitions (normative for annotators)

Toy examples below are abstract and independent of the evaluation corpus.
They illustrate the taxonomy only.

## Relationship (1+; narrowest supported wins)

- **supersession**: A later passage **explicitly replaces** a particular
  earlier proposition or policy (retirement, substitution, fail-closed
  contract change). Requires directed `superseded_claim_ref` to
  `replacement_claim_ref`. A date or rewording alone is insufficient.
  *Toy: "Directive 7 caps flow at 40 units" later followed by "Directive 8
  retires the 40-unit cap and imposes 30 units" — supersession with
  direction 7 to 8. "Directive 7 is discussed again in 2028" alone is not.*
- **contradiction_candidate**: Incompatible propositions under **comparable**
  conditions (same cohort, protocol, comparator, population).
  *Toy: two assays of the same sample type with the same protocol, one
  reporting detection and one non-detection — contradiction candidate.
  Opposite results on different sample types are not.*
- **corroboration_candidate**: Genuinely **independent** additional evidence
  for the same finding under matching conditions (different teams or
  instruments). Same-origin repetition or verbatim duplication is not
  corroboration.
- **scoped_change**: Same entities with **different** conditions,
  comparators, corpora, or scopes. Preserve scope; do not infer
  contradiction or universal gain.
  *Toy: an effect measured against comparator M on one workload and
  against comparator N on another — scoped change, not contradiction.*
- **substantive_connection** (residual): Other meaningful link: shared
  project continuity with an explicit limitation, a duplicate restatement
  requiring anti-double-counting qualification, or a reaffirmed continuity
  without replacement. Use only when no specific category fits.
- **independent_observations**: Adequately supported **lack** of a
  substantive link (different subsystems, word-sense collision, different
  referents, unrelated inquiries). Requires sufficient evidence for the lack.
- **unsupported_claim**: A presented headline or assertion **exceeds** its
  supporting passage (for example a universal claim supported only by a
  single narrow observation, or a superiority claim against a retained
  qualification denying it). A useful correction (`set_aside`), not a
  hidden abstention.
- **unknown**: Epistemic inability to decide (missing baseline or
  conditions, a date-only mention without detail, high-overlap distractors
  without comparable entities). Always with `insufficient`/`unknown` and
  abstention.

## Sufficiency

- `sufficient_for_candidate`: Evidence supports a candidate proposal with
  stated qualifications (still reviewable, not verified truth).
- `insufficient`: Missing conditions or evidence prevent a defensible proposal.
- `unknown`: Cannot determine sufficiency from the supplied text.

## Applicability

- `applicable`: Finding applies as stated (matching conditions).
- `scoped`: Applies only under stated narrower conditions.
- `not_applicable`: No applicable use (independent lack, unsupported headline).
- `unknown`: Cannot determine applicability.

Standardization: all `independent_observations` findings use
`not_applicable`. Cases the adjudicator judges genuinely indeterminate may
set `exclude_from_category_accuracy` and stay in all other denominators.

## Decision

- `use_with_qualification`: Retain with explicit scope or limitation.
- `set_aside`: Do not use; record as a correction or scoped non-use.
- `abstain`: No justified use or non-use; the only decision allowed with
  `unknown`/`insufficient`.

A useful finding can never be rewarded by abstention alone. Non-useful
cases are judged by correct non-use, not by a composite score.
