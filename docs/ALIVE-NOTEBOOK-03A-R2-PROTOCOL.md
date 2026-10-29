# ALIVE-NOTEBOOK-03A-R2 — frozen protocol v1.6

Protocol: `evaluations/notebook03a_r2/protocol.json`, version
`notebook03a-v1.6`. v1.4 and v1.5 preserved byte-unchanged as historical
evidence. No inference or spending authorized. Independent holdout:
`HOLDOUT_PENDING` (0 available).

## Hypothesis and primary task

A future structured semantic qualifier may preserve useful historical
evidence and detect specific corrections while reducing unsupported
connections relative to lexical candidates — and must demonstrate this
under a decision procedure that a pattern-matching shortcut cannot pass.
Untested hypothesis; R2 runs no model.

Each task carries one identical neutral instruction; pair tasks compare
two identifiable propositions, claim-support tasks compare one presented
assertion with its passage. No crawling, discovery, retrieval, or model
execution in R2.

Schemas exported in `schemas.json`, implemented in
`scripts/notebook03a_r2_protocol.py` (+ v1.4 base). `prepare_payload`
whitelists question, task kind, claim IDs/roles/passages, and full bounded
sources; withholds gold, IDs, families, splits, origins, notes, span
hints, and context cues. Full excerpts identical for all arms.

## Corpus and provenance

66 public draft cases: 16 development + 50 public diagnostic. v1.6
transformation: all 66 questions replaced by the neutral instruction;
IDs, families, splits, claims, sources, and supporting passages
unchanged; annotations, origins, and notes byte-identical to v1.5.
Origins: 12 authentic-only, 5 controlled-involved, 49 synthetic-only.
39 template families (shared: 83b02e ×5, 0b1efb ×5, S3+S4 ×2).

| Relation (total/dev/eval) | counts |
|---|---|
| supersession | 9 / 5 / 4 | scoped_change | 8 / 2 / 6 |
| corroboration_candidate | 5 / 0 / 5 | contradiction_candidate | 5 / 0 / 5 |
| substantive_connection | 9 / 3 / 6 | independent_observations | 9 / 1 / 8 |
| unsupported_claim | 9 / 5 / 4 | unknown | 12 / 0 / 12 |

Authentic quotes pinned to Git objects at `a9bcf86...`; controlled quotes
verbatim with perturbation notes; synthetic explicitly non-historical.
`validate_corpus_r2` enforces verbatim/offset/hash/gate rules; missing
revisions are controlled errors. Family/duplicate checks block cross-split
leakage; the Jaccard similarity report remains diagnostic-only.

## Decision procedure (validated contract, layered verdicts)

Thresholds (`decision_thresholds.json`, flat, strictly validated — no
defaults, no unknown keys): retention floor 0.5, misleading cap 0.10,
D-over-S retention margin 0.10 / misleading tolerance 0.05, D-over-C
retention margin 0.05 / misleading tolerance 0.05, minima of 30 scored
cases / 20 families / 20 useful cases, citation precision floor 0.2 with
full-recall requirement, 1000 seeded bootstrap resamples at 95% level.

Layers: engineering validity; public diagnostic (numbers only, never a
verdict); blind readiness (scope, sealed holdout, adjudicated gold,
boundary, all comparators A/B0/S/C/D); final verdict. Public scope or any
missing gate yields `INCONCLUSIVE` naming the gap. D `PROGRESS` needs
absolute gates, citation-gate pass rate 1.0, and both D-vs-C and D-vs-S
margins on retention and misleading. C is judged against S/A/B0 with its
own reference. C and D verdicts differ structurally by construction.

## Arms and uncertainty

- A: lexical connection API (pair only). B: integrity qualifier (actual
  output recorded). B0: constant abstain. S: surface-cue-v1.0 (preserved
  regression control). V: shortcut-control-v2.0 (honest honest-baseline
  features, dev-tuned, frozen pre-evaluation). C/D: NOT RUN.
- Family-level paired bootstrap over precomputed flags (seed 20261029):
  per-arm intervals plus paired D-vs-S / D-vs-C differences; raw counts,
  family count, category and authentic/synthetic breakdowns, predeclared
  underpowered warnings. Sensitivity bounds only; no significance or
  generalization claims.

## Citation, annotation, holdout

Substantive findings need exact spans, full required recall, and
precision at/above 0.2; failures count as misleading advances. Relevance
beyond span overlap awaits independent adjudication. Annotation package
uses opaque handles (mapping implementer-side only), no splits/families/
gold; leakage audit gates the package with documented residual risk.
Adjudication supports multi-label acceptance, ambiguity flags, and
predeclared category-accuracy exclusions; two reviewers + adjudicator
required; R2 builds the mechanism only. Holdout contract specifies the
custodian boundary; structural validation only; human verifies access.

## Freeze, amendments, prerequisites

Inputs, annotations, prompts, schemas, metrics, thresholds, contracts,
specs, and tool hashes LF-normalized SHA-256 in `protocol.json`.
Amendments append v1.6 to the v1.1–v1.5 history; v1.4/v1.5 evidence
retained. Baseline expectations stored separately and compared
deterministically (metrics+strata+per-case decisions); never rewritten to
match thresholds.

Before 03B: independent review of v1.6; independent adjudication of the 66
drafts; restricted 12-case sealed package with verified boundary;
Notebook-02 contract migration; reviewed governance adapter; frozen
model/settings/pricing; owner approval of exact payloads/caps; output
adjudication. None authorized by R2. Stop after draft PR; human merge only.
