# ALIVE-NOTEBOOK-03A-R1 — Label Adjudication Dossier (provisional)

**All labels remain `implementer_authored` drafts. No independent adjudication
collected. Corrections are versioned in v1.5; v1.4 gold preserved byte-unchanged
under `evaluations/notebook03a/`. Final labels stay provisional until the
external custodian adjudicates.**

## D1 — Duplicates vs substantive connection vs corroboration

### Case `93b00a8b5a248a32` (dev, auth-duplicate)
- Passages: s0 = s1 = `General semantic or owner-usefulness superiority: **NOT DEMONSTRATED**.`
  (docs/ALIVE-13.md @283, same document, same offsets).
- Competing readings: (a) `corroboration_candidate` (two matching excerpts);
  (b) `substantive_connection` duplicate; (c) `independent_observations` (no link).
- Recommended (v1.4 → v1.5 unchanged): `substantive_connection` /
  `sufficient_for_candidate` / `applicable` / `use_with_qualification` /
  useful. Rationale: identical same-document restatement is a duplicate
  continuity link requiring anti-double-counting qualification, not independent
  corroboration (which needs genuinely additional independent evidence).
- New R1 analogues `C3` (Haven same-lab paraphrase), `CR2` (Pine same-lab memo):
  same ruling, `substantive_connection` + `applicable`. Surface heuristic fails
  these by predicting `corroboration_candidate` on independent-3dB cues.

### Cases `C3` / `CR2` (R1 eval, synthetic duplicates)
- Same-lab repetition with matching conditions. Not corroboration. Provisional;
  needs independent adjudication to confirm duplicate-vs-corroboration boundary.

## D2 — Shared limitations vs substantive connection

### Case `7e0b9fd2496cb390` (dev, auth-limitations)
- s0: `This is not evidence of semantic paraphrase ...` (ALIVE-13); s1: rank-1/MRR
  gain with `This is not evidence of semantic superiority.` (ALIVE-14).
- Competing: (a) `independent_observations` (different milestones); (b)
  `substantive_connection` (common scoped limitation).
- Recommended (unchanged): `substantive_connection` / `scoped`. Both passages
  explicitly withhold semantic superiority for lexical retrieval — a meaningful
  project-continuity link, not external corroboration, not independence.

### Cases `C1` (candidate-vs-explanation), `C2` (ranker-limits vs remains-lexical)
- Same ruling: shared explicit denial of semantic capability across milestones.
  `substantive_connection` / `scoped`. Surface cue predicts `independent` or
  `unknown` here and misses all useful findings on the authentic stratum.

## D3 — Missing-baseline: unsupported_claim vs unknown/insufficient

### Family `ff90be42f143c52e` (4 eval synthetics: 21ac0b, 56ad77, 6b9785, ac11a2)
- Passage pattern: `The X bulletin states the repair improved performance, but
  omits the baseline and test conditions.` No universal headline; single
  uncharacterized observation.
- Ruling (unchanged): `unknown` / `insufficient` / `abstain` / non-useful.
  Missing conditions prevent any defensible relationship assessment.

### Case `U4` (R1 eval, `fe099cd6f4689060`)
- Headline `The Lyra repair universally improves performance` + body omitting
  baseline/conditions.
- Competing: (a) `unsupported_claim` + `set_aside` (universal exceeds body);
  (b) `unknown` + `abstain` (missing conditions).
- Recommended (provisional): `unsupported_claim` (universal quantifier converts
  missing-condition into overclaim). `ambiguity_notes` records the dispute.
  Independent adjudication must decide universal-headline vs missing-condition
  framing before semantic deployment. Either way the system must not use the
  earlier evidence without qualification.

## D4 — Later publications without explicit replacement

### Cases `d733952487197795`, `e3a56c3973946019` (eval, synthetic date-only)
- 2028 discussion without replacement vs 2023 validity period.
- Ruling (unchanged): `unknown` / `insufficient` / `abstain`. Later date alone
  proves neither replacement nor independence; `ambiguity_notes` notes a
  continuity link may be plausible.

### Case `SC3` (R1 eval, Haven reaffirmation with explicit validity restatement)
- s1 adds `without any replacement statement; the 2023 validity period is
  reaffirmed`.
- Ruling (provisional): `substantive_connection` / `scoped` (continuity link,
  not supersession, not independence). Distinguishes reaffirmation from bare
  date-only mention (`UN4` stays `unknown`). Needs adjudication.

### Authentic supersession controls `S1` (withdrawal), `S2` (memory_types)
- Explicit replacement language (`carries its own memory_id ... explicit
  researchId` replacing last-saved targeting; `replaces that contract with`
  fail-closed selector). Ruled `supersession` with directed refs. Paraphrased
  retirement without the word "replaces" (`S3` Haven policy B retires 40-unit
  ceiling) also ruled `supersession`; reversed serialization (`S4`) keeps
  direction by explicit language, not roles/dates.

## D5 — Independent-observations applicability

### Case `7b86535f5f25b31a` (dev, auth-r3: ALIVE-11 spend vs ALIVE-14 no-ratings)
- v1.4: `independent_observations` / `applicable` / `set_aside` / non-useful.
- All other `independent_observations` (5f8934, 9a4ea2, b3a677, 5aae89 + 8 R1
  eval) use `not_applicable`.
- R1 correction (v1.5): `applicable` → `not_applicable` with `ambiguity_notes`.
  Rationale: standardize non-use semantics (no applicable use of the earlier
  source for the later question); `applicable` implied a usable link the
  rationale explicitly denies. Historical v1.4 label preserved under
  `evaluations/notebook03a/`; R1 gold carries the correction as provisional.

## Version record

- v1.4 gold: unchanged, byte-identical under `evaluations/notebook03a/`.
- v1.5 gold (`evaluations/notebook03a_r1/`): 66 cases (40 carried + 26 new),
  1 applicability correction above, 3 provisional ambiguity notes
  (`U4`, `SC3`, `UN4`, plus `UN1` proposal-fulfillment).
- All 66 remain `draft` / `implementer_authored` / `NOT_INDEPENDENTLY_ADJUDICATED`.
