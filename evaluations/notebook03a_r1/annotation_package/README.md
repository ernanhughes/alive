# ALIVE-NOTEBOOK-03A-R1 — Independent Annotation Package

**Status: `READY_FOR_INDEPENDENT_ANNOTATION`. No independent labels collected.**
**Boundary: IMPLEMENTER_EXPOSED. No blindness claimed.**

This package is for use by independent annotators working outside the
implementer's access boundary (separate account/machine the 03B implementer
cannot access). It contains **no model answers, no draft gold labels, no
supporting-span hints, and no task IDs/families/splits that encode outcomes**.

## Contents

- `labeling_instructions.md` — task, workflow, abstention and disagreement rules.
- `category_definitions.md` — normative category/sufficiency/applicability/decision definitions.
- `tasks_for_annotation.json` — source passages + research question + claim spans only.
  No gold relationships, no rationale, no required-evidence hints.
- `annotation_template.json` — reviewer fields, ambiguity options, disagreement and
  adjudication status schema (to be filled by annotators + adjudicator).
- `README` (this file) — boundary and disclosure.

## Disclosure (read before use)

- All R1 public tasks, draft implementer labels, and baseline outputs are in
  `evaluations/notebook03a_r1/` and are **visible to anyone with repo access**,
  including any Codex session. Placing this package in another directory does
  **not** make it hidden.
- A genuinely blind held-out set requires the custodian workflow in the frozen
  protocol: the custodian authors/adjudicates 12 `independent_heldout` cases on
  an independently controlled machine, retains `tasks.json` + `annotations.json`
  outside the implementer's reach, and shares only hashes/aggregate reports.
  `submission --package` validates structure/hash/completeness, **not** OS
  permissions or human identity. A human reviewer must verify the
  separate-account boundary.
- Until that custodian package exists with `external_attested` adjudicated
  labels (2 distinct reviewers + author, per schema), all R1 labels remain
  **provisional implementer-authored drafts** (`IMPLEMENTER_EXPOSED; NOT BLIND`).
- **The implementer (Codex) is not the independent annotator** and must not
  self-attest independence.

## How to use

1. Custodian copies `tasks_for_annotation.json` + `annotation_template.json` to
   the restricted machine (no `annotations.json`, no `origins.json` gold notes).
2. Two reviewers label independently using `category_definitions.md`; record
   disagreements in the template.
3. Adjudicator resolves to `adjudicated` + `external_attested` with rationale
   and required exact evidence spans.
4. Custodian runs `submission --package <restricted-dir>` on the restricted
   machine and shares only the manifest hashes + aggregate report.
5. Any implementer exposure event invalidates blind use for subsequent tuning;
   log it in `independent_submission.json`.
