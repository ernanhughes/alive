# ALIVE-NOTEBOOK-03A-R1 — design (protocol hardening, no inference)

Baseline: `785e1024a22fca0402741b7a2ebad984af7fc10b` (`origin/main`, PR #45 merged).
Branch: `codex/alive-notebook-03a-r1-protocol-hardening`.
Authority: offline experimental validity + dataset hardening only. Zero model
inference; no 03B work; no paid spend; no merge authority.

v1.4 (`evaluations/notebook03a/`, `scripts/notebook03a*.py`) is preserved
byte-unchanged as historical evidence. R1 lives in `evaluations/notebook03a_r1/`
+ `scripts/notebook03a_r1*.py` under protocol `notebook03a-v1.5`.

## Why R1

Independent review showed the v1.4 eval (24 public-evaluation cases, all
synthetic, no supersession/unsupported/substantive in eval) is solvable by
surface cues: a regex/phrase heuristic scores ~20/20 on synthetic templates
and ~0/6 on authentic ALIVE history (adversarial diagnostic, not a fair
baseline). A model could beat always-abstain by matching template vocabulary
without semantic reasoning. R1 keeps the credible v1.4 framework and repairs
coverage, controls, scoring, and protocol so the next experiment can test both
failure modes: hallucinating connections and over-abstaining from useful ones.

## What changes (v1.4 → v1.5)

- **Corpus 40 → 66** (dev 16 unchanged; eval 24 → 50 with 26 new). Eval now
  covers every relationship category, 4 question templates, authentic +
  controlled + synthetic origins, and 39 template families with declared
  non-independence. See M1.
- **New arm S** (surface-cue-v1.0, frozen deterministic regex/overlap control).
  Succeeds on v1.4 synthetic templates, fails on authentic paraphrases. Future
  models must beat S by margin, not just B0. See M2.
- **Scoring v2**: misleading-advance rate, correct non-use rate, false-abstention
  rate, category accuracy with explicit unknown/unknown rule (+ excluding
  variant), sufficiency accuracy, citation precision/recall. Dual pre-registered
  thresholds (retention + false-advance) with INCONCLUSIVE. See M3–M4.
- **Taxonomy adjudication**: provisional dossier + 1 standardized correction
  (7b8653a applicability), 4 ambiguity notes. See M5.
- **Annotation boundary**: reviewer-facing package with no gold/answers;
  custodian holdout workflow unchanged in mechanism, clarified in limits;
  IMPLEMENTER_EXPOSED disclosure. See §7.
- **8 engineering fixes**: actual B output, template-similarity diagnostic,
  goal-text doc, full normalized replay comparison, custodian-limit wording,
  unknown/unknown rule, context-cue removal, Git-error handling. See §8.

```
flowchart LR
    T[R1 tasks: 66 incl. authentic/adversarial] --> V[Deterministic validation + similarity diagnostic]
    O[Pinned Git provenance] --> V
    V --> P[R1 whitelisted payload (no version/temporal/system cues)]
    V --> R[Core A/B replay (actual B) + offline S control]
    R --> S2[R1 scorer: retention + misleading + citation P/R]
    G[Provisional draft annotations + dossier] --> S2
    P --> F[03B governed adapter: NOT IMPLEMENTED]
    E[External custodian sealed tasks/gold] --> X[Independent evaluation: PENDING]
```

## M1 — coverage (26 new eval; dev frozen)

| Eval relation | v1.4 | R1 | Notes |
|---|---:|---:|---|
| supersession | 0 | 4 | 2 authentic (withdrawal, memory_types), 1 paraphrase w/o "replaces", 1 reversed |
| unsupported_claim | 0 | 4 | 2 controlled long (semantic-superiority, owner-superiority), 1 long synthetic, 1 disputed universal-vs-missing |
| substantive_connection | 0 | 6 | 2 authentic shared-limitation, 1 same-lab duplicate, 1 long paraphrase, +2 carried? (dev has 3) |
| scoped_change | 4 | 6 | corpus-number controlled, diff-condition synthetic, reaffirm-continuity + 3 originals |
| corroboration_candidate | 4 | 5 | paraphrase shares family 83b02e (declared non-independent) |
| contradiction_candidate | 4 | 5 | paraphrase shares family 0b1efb (declared non-independent) |
| independent_observations | 4 | 8 | 1 authentic unrelated, word-sense banks, Pine rings, discharge + 4 originals |
| unknown | 8 | 12 | authentic proposal-vs-corpus, missing-condition, long-overlap, date-only + 8 originals |

Kinds (eval): pair 41, claim_support 9. Origins (eval): synthetic-only 41
(34 pair + 7 single), authentic-only 5, controlled-only 2, controlled-pair 1,
authentic+controlled 1. Questions: Q0 generic 34, Q3 conditions 10, Q1
replacement 3, Q2 headline 3 — balanced so question text is not a category cue
(see goal-text behavior). Families: 39 total; shared families 83b02e (5),
0b1efb (5), S3+S4 (2) are declared non-independent paraphrase/template groups;
paraphrases not sharing a family are still disclosed as non-independent in
notes. Gaps reported, not filled with fake authentic evidence: no authentic
corroboration/contradiction/scoped/unsupported in eval (ALIVE history contains
no independent replication experiment, no contradictory measurement pair, no
false-headline artifact); controlled/synthetic cover those cells explicitly.

## M2 — surface-cue control + adversarial cases

`scripts/notebook03a_r1_surface.py` (surface-cue-v1.0, frozen 2026-10-29):
regexes for replaces/independent/3dB/detected-negation/FIFO-LRU/charge/
baseline-omit/calibration/mercury plus token-Jaccard fallback. No task
IDs/families/splits/gold. Patterns derived from v1.4 development templates
only; frozen before R1 holdout evaluation; any change needs a new version +
amendment. Recorded implementation hash in replay output.

Adversarial coverage (each ≥1 case): paraphrase same-meaning (C4/CR1/CT1/S3),
same-vocab different-meaning (CT2 banks, IO2 Pine rings, IO3 discharge),
reversed chronology (S4, dc3d...), newer-without-supersession (SC3 reaffirm,
UN4 date-only, 2 original unknowns), supersession-without-"replaces" (S3),
diff-condition opposites (SC2), same-condition compatibles (corroboration set),
duplicates (93b00a, C3, CR2), unsupported-over-qualified (U1/U2/U3/R4),
long+irrelevant-overlap (U1 934 chars, C4 769/783, U2 721, UN3, SC1 tables).

## M3 — pre-registered success/failure

Per-arm computed (denominators explicit; see `metrics.json` v2 +
`decision_thresholds.json` + scorer):

- useful retention = accepted substantive findings on useful gold / useful gold.
- misleading advances: S/C/D = unsupported substantive judgments / scored;
  A = retain on non-useful-or-insufficient / scored; B/B0 = 0.
- correct non-use = accepted set_aside/abstain on non-useful / non-useful.
- false abstentions = abstain on useful / useful. Category accuracy (incl.
  unknown/unknown; excluding variant reported), sufficiency accuracy,
  unsupported assertions, Wilson illustrative intervals (non-independent).

03B progress over A (lexical), B0 (abstain), S (surface), C (same-evidence
general model) requires **both** retention ≥ 0.5 **and** misleading ≤ 0.10,
**plus** D exceeding S by ≥ 0.10 retention without exceeding S misleading by
> 0.05, on ≥ 30 scored cases; else NO_PROGRESS. Insufficient evidence, unrun
arms, or exposure → INCONCLUSIVE. Thresholds justified against control
performance (S retention ~0.49 R1 overall, ~0.0 authentic; S misleading ~0.22
overall, ~0.42 authentic) and sample (66 cases, 45 useful; authentic n=12 too
small for narrow claims) — frozen before any model result, never tuned to one.

## M4 — citation precision

6 passages > 400 chars (934, 864, 783, 721, 718, 677) with irrelevant
high-overlap distractors. Diagnostic per scored case with required evidence:
recall = required chars covered / required; precision = covered / cited.
Broad full-source citations score high recall but low precision (e.g., C4
recall 1.0 / precision ~0.12). Exact-string agreement never proves entailment;
independent output adjudication remains required. Invented/shifted spans fail
closed in validation (unit-tested).

## M5 — taxonomy (see `adjudication_dossier.md`)

Duplicate vs corroboration (93b00a, C3, CR2 → residual, not corroboration);
shared limitations vs substantive (7e0b9f, C1, C2 → residual continuity);
missing-baseline (ff90be family → unknown; U4 universal → unsupported,
provisional); later-without-replacement (date-only → unknown; SC3 reaffirm →
substantive, provisional); applicability (7b8653a applicable → not_applicable
standardization, provisional). v1.4 gold untouched; v1.5 records corrections +
ambiguity notes; all provisional pending independent adjudication.

## Annotation boundary (§7)

`annotation_package/` (README, instructions, category definitions, 66
passage+question items with opaque handles, reviewer/disagreement/adjudication
template). No model answers, no gold, no span hints. Blind holdout still
requires the custodian's separately controlled 12-case package; repo-local
files are IMPLEMENTER_EXPOSED by construction. Codex is never the independent
annotator.

## Engineering fixes (§8)

1. B records actual qualifier output (outcome/semantic/inference_calls);
   unexpected semantics raise instead of faking abstain.
2. `template_similarity_report` (Jaccard ≥ 0.55 across splits) with documented
   limits (misses paraphrase, flags coincidence; families remain normative).
3. Goal text = question verbatim documented; 4 templates balanced so not a cue;
   still fixed-candidate, not retrieval ranking.
4. `--check-against` compares full normalized metrics+strata+per-case decisions.
5. Custodian manifests attest file consistency/completeness, not OS access or
   identity; sibling dir/worktree ≠ private; human must verify boundary.
6. unknown/unknown counts toward category accuracy; excluding-variant reported;
   neither counts as substantive judgment.
7. R1 payload withholds version/temporal/system context (v1.4 cue correlating
   ALIVE-* vs null); question/claims/sources identical across arms.
8. Missing Git revisions → controlled ValueError, not CalledProcessError.

## 03B prerequisites (all incomplete → NOT_READY)

Frozen v1.5; representative eval coverage (with stated authentic gaps);
provisional (not independent) labels; S baseline + citation + thresholds;
5 Notebook-02 contract issues (separate narrow migration, not claimed here);
outbound preview/authorize/analyze + payload/Governor/cancellation semantics
(unchanged, unqualified for single/dual-source dispatch); exact model/settings/
pricing freeze + owner approval (spend still $0). No external inference.
