# ALIVE-NOTEBOOK-03A-R1 — Labeling Instructions (for independent annotators)

You are labeling **research-evidence relationships**, not factual truth.
A label is a reviewable proposal about what the supplied passages justify.

## What you receive (per case)

- 1–2 sources: exact bounded text (quote exactly; do not paraphrase in citations).
- 1–2 claims: exact passages with source offsets.
- A research question (one of four R1 templates; question wording is balanced
  across categories and is **not** a category cue).
- Explicit context fields are withheld from the inference payload; use only the
  supplied text.

## What you must produce (per case, via `annotation_template.json`)

- `relationships`: 1+ accepted categories (narrowest supported; see definitions).
  Multiple categories require `ambiguity_notes`.
- `sufficiency`: `sufficient_for_candidate` / `insufficient` / `unknown`.
- `applicability`: `applicable` / `scoped` / `not_applicable` / `unknown`.
- `decisions`: `use_with_qualification` / `set_aside` / `abstain` (1+).
- `useful_finding`: boolean (would a careful researcher be justified in
  retaining this as a candidate finding with the stated qualification?).
- `required_evidence`: exact spans (source_id/start/end/text) supporting **both**
  the claim and any necessary qualification (e.g., comparator, corpus, scope,
  limitation). Empty only when `sufficiency != sufficient_for_candidate`.
- `rationale`: 1+ sentences citing what the passages do/don't establish.
- `forbidden_conclusions`: 1+ conclusions the evidence does **not** support.
- `superseded_claim_ref` / `replacement_claim_ref`: required for supersession,
  forbidden otherwise. Direction follows explicit replacement language, not
  role labels or dates.
- `ambiguity_notes`: required when multiple relationships accepted or when
  provisional (e.g., universal-headline vs missing-condition framing).

## Rules

1. **Quote exactly.** Every required span must match the source text at the
   given offsets. Invented or shifted spans invalidate the label.
2. **Specific beats residual.** `substantive_connection` is residual; use a more
   specific category whenever its conditions are met.
3. **Dates and vocabulary are insufficient.** A newer date or shared words alone
   never establish supersession, corroboration, or contradiction.
4. **Supersession needs explicit replacement** of a particular proposition/policy.
   Paraphrased retirement counts only if the specific ceiling/policy is retired
   (e.g., S3); a later discussion without replacement is not supersession.
5. **Contradiction needs comparable conditions.** Opposite outcomes under
   different cohorts/protocols/comparators are `scoped_change`, not contradiction.
6. **Corroboration needs independence.** Same-lab repetition or verbatim
   duplication is a `substantive_connection` duplicate, not corroboration.
7. **Independence needs support.** A supported lack of link is
   `independent_observations`; inability to decide is `unknown` (+ abstain).
8. **Headline vs body.** If a presented headline exceeds its supporting passage,
   label `unsupported_claim` + `set_aside` (a useful correction), not abstention
   to hide the problem. If conditions are simply missing, `unknown` + abstain
   may be correct — record the ambiguity and let adjudication decide (U4).
9. **Abstain when unsure.** `unknown` + `insufficient`/`unknown` + `abstain`
   with empty evidence is valid and preferred over guessing.
10. **No composite.** Retention and false-advance are judged separately; do not
    trade one for the other.
11. **Disagree openly.** Record competing readings, reviewer IDs, and
    adjudication status. Unresolved cases stay `pending`, never silently filled.

## Coherence gates (enforced by schema)

- `insufficient`/`unknown` sufficiency ⇒ relationships `["unknown"]`,
  decisions `["abstain"]`, `useful_finding: false`, empty evidence.
- `sufficient_for_candidate` ⇒ non-empty required evidence.
- `useful_finding: true` ⇒ decisions must not be `["abstain"]`.
- External adjudication ⇒ status `adjudicated`, independence
  `external_attested`, author distinct from 2+ reviewers.

## What you must NOT do

- Do not consult model outputs, draft gold labels, or annotation notes.
- Do not invent authentic provenance; synthetic/controlled text is labeled as such.
- Do not treat paraphrases of one source pair as independent observations.
