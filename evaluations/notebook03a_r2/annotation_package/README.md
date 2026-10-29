# ALIVE-NOTEBOOK-03A-R2 — Independent Annotation Package

**Status: `READY_FOR_INDEPENDENT_ANNOTATION`. No independent labels collected.**
**Boundary: IMPLEMENTER_EXPOSED unless a sealed holdout is used. No blindness
claimed for this package.**

This package is for use by independent annotators working outside the
implementer's access boundary. It contains **no model answers, no draft gold
labels, no supporting-span hints, no task IDs, no family IDs, no splits, and
no identity mapping**.

## Contents

- `labeling_instructions.md` — task, workflow, abstention and disagreement rules.
- `category_definitions.md` — normative category/sufficiency/applicability/decision definitions with generic toy examples.
- `tasks_for_annotation.json` — opaque handles + neutral question + claim spans + source passages only.
- `annotation_template.json` — reviewer fields, ambiguity options, disagreement recording, adjudication status.

## Disclosure (read before use)

- Handles are opaque randoms (`r2-blind-handle:<salt>:<id>` truncated). The
  `handle_mapping.json` file lives implementer-side in
  `evaluations/notebook03a_r2/` and **must not** accompany this package, be
  sent to annotators, or be stored on the annotation machine.
- All 66 cases remain visible in the repository under their public IDs. An
  annotator with repository access can re-identify cases by text search.
  Renaming cannot guarantee blinding then; genuine blinding needs the sealed
  holdout boundary (`holdout_contract.md`), not field hygiene alone.
- A separate `leakage_audit` (CLI `audit-package`) verifies this package is
  structurally self-contained and free of known answer leaks. The audit
  cannot prove human blinding.
- **The implementer (Codex) is not an independent annotator** and must not
  self-attest independence. Two independent reviewers plus an adjudication
  procedure are required before final evaluation (see `adjudication_spec.md`).

## How to use

1. Custodian copies only the four files above to the annotation machine
   (never `handle_mapping.json`, never repository gold files).
2. Two reviewers label independently per `labeling_instructions.md`.
3. Adjudicator resolves disagreements per `adjudication_spec.md`.
4. Custodian returns only the adjudicated labels through the sealed-holdout
   flow; any implementer exposure event invalidates blind use.
