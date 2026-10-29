# ALIVE-NOTEBOOK-03A-R2 — Adjudication Plan (mechanism only, no new labels)

R2 creates the mechanism and materials. No independent labels are collected
in R2; all current labels remain provisional implementer-authored drafts.

## Roles

- **Reviewer 1 / Reviewer 2**: label independently using the annotation
  package; record disagreements in the template; never see each other's
  labels before recording their own.
- **Adjudicator**: resolves every disagreement, confirms or corrects the
  category, sufficiency, applicability, decision, required evidence, and
  ambiguity status; writes the auditable final decision with rationale.
- **Custodian**: holds the sealed tasks and gold outside implementer reach,
  runs validation/scoring, shares hashes and aggregate reports only.

Standard (owner may amend explicitly): two independent reviewers plus one
adjudicator; author distinct from reviewers for `external_attested` status.

## Multiple acceptable labels

Where the evidence genuinely supports more than one reading, the
adjudicator records **all** accepted relationships with `ambiguity_notes`
instead of forcing a single label. Scoring accepts any listed relationship
(`category_ok` = predicted in accepted set).

## Explicit uncertain / ambiguous cases

Cases may be marked ambiguous with `ambiguity_notes` and
`exclude_from_category_accuracy: true`. Excluded cases:

- stay in coverage (exactly one outcome still required);
- stay in retention, misleading, sufficiency, and abstention denominators;
- leave the category-accuracy denominator (both lenient and excluding
  variants) under this predeclared rule only.

Exclusion is an adjudication decision, never an implementer convenience,
and the excluded set is published with the results.

## Disagreement reporting

Every disagreement is recorded with both reviewers' categories, the nature
of the disagreement, and the resolution (`pending` or `adjudicated` with
adjudicator ID). Unresolved cases stay `pending` and are unscored; they
never default to the implementer's draft.

## Auditable final decision

The adjudicated record per handle contains: final relationships,
sufficiency, applicability, decisions, useful flag, required evidence,
forbidden conclusions, ambiguity/exclusion flags, reviewer IDs,
adjudicator ID, and decision rationale. The custodian versions this record
with the sealed inputs; any later change is a new version, never a silent
edit.

## Non-goals for R2

R2 does not choose labels to improve any eventual model score, does not
promote Codex-authored drafts to independent gold, and does not adjudicate
the disputed cases itself. The disputed patterns from R1 review
(duplicates, shared limitations, missing baselines, date-only changes,
historical corrections, independent-observation applicability) are carried
as provisional with pointers, awaiting the independent panel.
