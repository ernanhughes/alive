# ALIVE-NOTEBOOK-03A-R2 — Labeling Instructions (for independent annotators)

You are labeling **research-evidence relationships**, not factual truth.
A label is a reviewable proposal about what the supplied passages justify.

## What you receive (per case)

- An opaque handle (routing identity only; encodes no outcome).
- A task kind (`pair` or `claim_support`).
- One neutral instruction, identical on every case.
- 1–2 claims: exact passages with source offsets.
- 1–2 sources: exact bounded text and content hashes.

You do **not** receive splits, family links, provenance labels, gold
labels, rationales, or span hints. Judge each case on its own text.

## What you must produce (per case, via `annotation_template.json`)

- `relationships`: 1+ accepted categories (narrowest supported; see definitions).
  Multiple categories require `ambiguity_notes` and mark the case ambiguous.
- `sufficiency`: `sufficient_for_candidate` / `insufficient` / `unknown`.
- `applicability`: `applicable` / `scoped` / `not_applicable` / `unknown`.
- `decisions`: `use_with_qualification` / `set_aside` / `abstain` (1+).
- `useful_finding`: boolean (would a careful researcher be justified in
  retaining this as a candidate finding with the stated qualification?).
- `required_evidence`: exact spans (source_id/start/end/text) supporting
  **both** the claim and any necessary qualification (comparator, corpus,
  scope, limitation). Empty only when `sufficiency != sufficient_for_candidate`.
- `rationale`: 1+ sentences citing what the passages do and do not establish.
- `forbidden_conclusions`: 1+ conclusions the evidence does **not** support.
- `superseded_claim_ref` / `replacement_claim_ref`: required for supersession,
  forbidden otherwise. Direction follows explicit replacement language, not
  role labels or dates.
- `ambiguity_notes`: required when multiple relationships are accepted or
  when the case is a borderline pattern (for example a universal-sounding
  headline over a narrowly qualified body, or a later mention that
  reaffirms without replacing).
- `exclude_from_category_accuracy`: true when the adjudicator judges the
  category genuinely indeterminate; such cases stay in coverage and
  abstention scoring but leave the category-accuracy denominator under the
  predeclared exclusion rule.

## Rules

1. **Quote exactly.** Every required span must match the source text at the
   given offsets. Invented or shifted spans invalidate the label.
2. **Specific beats residual.** The residual connection category is for
   meaningful links no specific category captures; prefer a specific
   category whenever its conditions are met.
3. **Dates and vocabulary are insufficient.** A newer date or shared words
   alone never establish replacement, corroboration, or contradiction.
4. **Replacement needs explicit language** retiring or substituting a
   particular proposition or policy. A paraphrased retirement of a specific
   rule can count; a later discussion without replacement language does not.
   Serialization order and role labels never determine direction.
5. **Contradiction needs comparable conditions.** Opposite outcomes under
   different cohorts, protocols, comparators, or populations are a scoped
   difference, not a contradiction.
6. **Corroboration needs independence.** A restatement from the same origin,
   or a verbatim duplication, is not independent corroboration.
7. **Independence needs support.** A supported lack of link is an
   independent-observations finding; inability to decide is unknown with
   abstention.
8. **Headline versus body.** When a presented assertion exceeds its
   supporting passage, that is a substantive negative finding (set aside),
   not a hidden abstention. When supporting conditions are simply absent,
   abstention with an ambiguity note may be correct; let adjudication decide
   the framing.
9. **Abstain when unsure.** Unknown with insufficient evidence plus abstain
   and empty evidence is valid and preferred over guessing.
10. **No composite.** Retention and false-advance are judged separately.
11. **Disagree openly.** Record competing readings, reviewer IDs, and
    adjudication status. Unresolved cases stay pending, never silently filled.

## Coherence gates (enforced by schema)

- `insufficient`/`unknown` sufficiency implies `["unknown"]` relationships,
  `["abstain"]` decisions, `useful_finding: false`, empty evidence.
- `sufficient_for_candidate` implies non-empty required evidence.
- `useful_finding: true` forbids `["abstain"]` decisions.
- External adjudication implies status `adjudicated`, independence
  `external_attested`, and an author distinct from at least two reviewers.

## What you must NOT do

- Do not consult model outputs, draft labels, or repository annotation files.
- Do not invent authentic provenance for synthetic or controlled text.
- Do not treat similarly worded cases as independent confirmations of each
  other; the scoring side groups related cases into families.
