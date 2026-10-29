# ALIVE-EVAL-01 — annotation handoff instructions (for the custodian)

This package hands the R2 annotation materials to an independent
custodian. Nothing here is independent gold; everything here is
implementer-authored and exposed.

## What the custodian receives

- `evaluations/alive-eval-01/annotation_package/` (package v1.7,
  revised from the R2 package: no source hashes or access cues, disputed
  rulings framed as open questions, opaque handles): neutral instruction,
  opaque handles, 66 tasks, generic taxonomy, reviewer template. No gold,
  no mapping.
- `evaluations/notebook03a_r2/handle_mapping.json`: implementer-side
  handle ↔ task/family map. For custodian bookkeeping only — never
  redistribute to annotators.
- `evaluations/notebook03a_r2/adjudication_spec.md` (R2 mechanism) and
  the EVAL-01 amendments record.

## What the custodian must do

1. Recruit two reviewers and one adjudicator with no stake in the
   implementation outcome and no access to the implementation drafts
   during labeling.
2. Copy ONLY the four annotator files to an independently controlled
   machine. Verify the copy contains no `handle_mapping.json`, no
   `sha256`/`access` fields, no task or family IDs, and no split labels
   (run the leakage audit: `alive_eval01` has no package gate, use
   `notebook03a_r2 audit-package --package <copy>` — it must pass).
3. Collect independent labels plus disagreement records per the template.
4. Adjudicate per the plan: multi-label acceptance where justified,
   ambiguity flags, predeclared category-accuracy exclusions, auditable
   final decisions.
5. Author 12 genuinely new sealed tasks (unfamiliar source texts and
   families, never paraphrases of the 66) with the same schema, on the
   custodian machine.
6. Run the custodian evaluator on the custodian machine; share only
   package hashes, case counts, aggregate reports, and the final receipt.
   Log any implementer exposure immediately — exposed material can never
   be used as a blind test afterwards.

## What the custodian must NOT do

- Design labels to match (or beat) any implementation's outputs.
- Reuse public task IDs, family IDs, or source texts in the sealed set.
- Treat structural validation as proof of organizational independence:
  confirm the access boundary with a human reviewer and record how.
- Assert independent review occurred unless reviewers and adjudication
  actually happened; until then the status stays
  `PENDING_INDEPENDENT_LABELING` / `HOLDOUT_PENDING`.
