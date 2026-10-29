# ALIVE-EVAL-01 — citation-length study and floor recommendation

Measured on the frozen R2 corpus (66 cases) with the frozen S-v1 and V-v2
controls, scored by the frozen v1.6 scorer. No thresholds were changed as
a result of this study.

## Required-evidence distribution

- 103 required spans across 66 cases: min 20 chars, median 72, max 286.
- A whole-source dump of a typical 700–900 char source against a median
  72-char requirement yields precision ~0.08–0.10.

## Observed precision (substantive assertions only)

- S: 40 cited cases; 38 at precision 1.0; 1 below 0.2 (0.09, whole-source
  dump); recall < 1.0 in 0 cases.
- V: 40 cited cases; 30 at precision 1.0; 2 below 0.2 (0.11, 0.38-window);
  recall < 1.0 in 3 cases (windowed cites missing distant required spans).

## Recommendation: keep the 0.2 floor

- The floor rejects whole-source dumps (observed ~0.08–0.11) while
  tolerating windowed localization (~0.38) and exact cites (1.0).
- Raising it (e.g., 0.5) would fail honest windowed citations without
  adding discrimination the distribution supports.
- Lowering or removing it would let dumps pass as fully supported.
- The floor is therefore a dump filter, not a relevance proof. It cannot
  distinguish passage localization from logical entailment, sufficient
  context from padding, or a correct span in the wrong argumentative role.

## What the floor does not do (represented explicitly)

- Exact quotation integrity: enforced by offset validation (fail-closed).
- Relevant passage localization: approximated by the floor; borderline
  cases need human adjudication.
- Passage sufficiency: covered by the full-recall requirement.
- Logical support for the proposed relationship: **requires independent
  human adjudication**. The custodian receipt carries an explicit
  `entailment: requires_human_adjudication` field — no deterministic
  overlap metric may be read as entailment proof, and the verdict never
  treats a citation pass as semantic correctness.
