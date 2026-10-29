# ALIVE-NOTEBOOK-03A-R1 — frozen protocol v1.5

Protocol: `evaluations/notebook03a_r1/protocol.json`, version
`notebook03a-v1.5`. v1.4 (`evaluations/notebook03a/`, protocol v1.4, 40 cases)
preserved byte-unchanged as historical evidence. No inference or spending
authorized. Independent holdout: 0 available, PENDING.

## Hypothesis and primary task

A structured semantic qualifier may preserve useful historical evidence and
detect specific corrections while reducing unsupported connections relative to
lexical candidates. It must outperform indiscriminate abstention on useful
findings under identical evidence access — and must not win by matching surface
cues. Untested hypothesis; R1 runs no model.

Each task supplies a question (4 R1 templates, balanced across categories),
exact claim passage(s), bounded source text/hash, and explicit unknown context.
Pair tasks compare two identifiable propositions; claim-support tasks compare
one presented assertion with its passage, including within one source. No
crawling, discovery, retrieval, or model execution in R1.

Schemas exported in `schemas.json`, implemented in
`scripts/notebook03a_r1_protocol.py` (+ v1.4 base). Gold, notes, origins
separate from `tasks.json`. `prepare_payload_r1` whitelists question, task
kind, claim IDs/roles/passages, and full bounded sources; withholds gold,
case/family/split IDs, origins, notes, inferred propositions, supporting-span
hints, **and version/temporal/system context cues** (R1 fix). Full excerpts
identical for all arms. Whitelisted IDs are routing identities, not outcomes.

## Corpus and provenance

66 public draft cases: 16 development (unchanged v1.4), 50 public evaluation
(24 v1.4 + 26 R1). 12 authentic-only, 5 controlled-involved, 49 synthetic-only
sources. 52 pair + 14 claim-support. 45 useful, 10 insufficient, 11
sufficient-non-useful/unknown-sufficient. 39 template families; shared families
83b02e (corroboration ×5), 0b1efb (contradiction ×5), S3+S4 (×2) are declared
non-independent; paraphrases are not independent observations.

| Provisional relation | Total | Dev | Eval |
|---|---:|---:|---:|
| supersession | 9 | 5 | 4 |
| scoped_change | 8 | 2 | 6 |
| corroboration_candidate | 5 | 0 | 5 |
| contradiction_candidate | 5 | 0 | 5 |
| substantive_connection | 9 | 3 | 6 |
| independent_observations | 9 | 1 | 8 |
| unsupported_claim | 9 | 5 | 4 |
| unknown | 12 | 0 | 12 |

Eval origins: synthetic-only 41, authentic-only 5, controlled-only 2,
controlled-pair 1, authentic+controlled 1. Eval questions: generic 34,
conditions 10, replacement 3, headline 3. R1-style (Q1 replacement) and R4-style
(Q2 headline) represented in eval beyond dev-only. Gaps reported: no authentic
corroboration/contradiction/scoped/unsupported in eval (no such ALIVE artifact);
covered by controlled/synthetic, explicitly labeled.

Authentic quotes pinned to Git objects at `a9bcf86...` with full-document
hashes and offsets; controlled quotes verbatim + declared perturbation note;
synthetic explicitly non-historical. `origins.json` + `validate_corpus_r1`
enforce verbatim/offset/hash/gate rules; missing revisions are controlled
`ValueError`s. Family/duplicate-source checks block cross-split leakage;
`template_similarity_report` (Jaccard ≥ 0.55) adds a heuristic diagnostic with
stated limits (misses paraphrase, flags coincidence).

## Independent held-out workflow (unchanged mechanism, clarified limits)

Target 78 (66 public + 12 holdout). Available: 0. Status:
PENDING_INDEPENDENT_LABELING. No independent labels/consensus/agreement
collected or fabricated. Custodian authors/adjudicates `independent_heldout`
tasks on a separately controlled account/machine, retains gold outside
implementer reach, shares hashes/aggregates only, records attestations.
Validator rejects repo-local packages, exposed families/hashes, incomplete
labels, inconsistent hashes, exposure events — structural gates only. Manifests
attest file consistency, **not** OS access or human identity; sibling
dirs/worktrees are not automatically private; human must verify the boundary.
Exposure invalidates blind use. `annotation_package/` (no answers/gold/hints)
is the reviewer-facing material; repo visibility disclosed; Codex never the
independent annotator.

## Arms and matching conditions

- A: lexical connection API (`deterministic-lexical-connection-v1`) on pairs;
  NOT_APPLICABLE on claim-support.
- B: Notebook-02 integrity qualifier on pairs (actual output recorded:
  outcome/semantic_judgement/inference_calls); NOT_APPLICABLE on claim-support.
- B0: constant-abstain on all authorized tasks (+ refuse on gated).
- S: frozen surface-cue-v1.0 (regex/phrase/overlap, offline, no Core/model);
  genuine executable baseline, not a lookup table.
- C: same-evidence general model, NOT RUN. D: structured procedure, NOT RUN.

All reasoning arms may abstain. Shared definitions/access for C/D; only
procedure differs. Fixture URLs are allowlisted transport in isolated SQLite,
not canonical attribution (pinned Git provenance is). Budgets: ≤2000 chars/
source, ≤4000 total, ≤16000 serialized; ≤8192 input + 800 output tokens
(proposed); max 156 calls (78×2) if holdout completes; spend ceiling USD 1
proposed, authorized 0. C/D compared with A/B only on pair stratum; singles
vs B0/S separately. Full-history access would need a separate protocol.

## Scoring, thresholds, uncertainty

Every task needs exactly one outcome per executed arm; missing/duplicate/
unknown-ref/unjustified-NOT_APPLICABLE fail. Refusals, inapplicables, and
missing/pending labels counted separately. Draft labels provisional.

- Category accuracy = matches / scored **including unknown/unknown**;
  excluding-variant reported; unknown matches never substantive.
- Sufficiency accuracy = matches / scored.
- Correct substantive judgments = proposals with accepted category +
  sufficiency + applicability + decision + full required-evidence coverage +
  directed refs. Precision = accepted / proposed (null if none).
- Useful retention = accepted findings on useful gold / useful gold.
- Misleading advances: S/C/D unsupported judgments / scored; A retains on
  non-useful-or-insufficient / scored; B/B0 0. Rate = advances / scored.
- Correct non-use = accepted set_aside/abstain on non-useful / non-useful.
- False abstentions = abstain on useful / useful. Missed = useful − retained.
- Citation recall/precision = mean required-char coverage / required and /
  cited (exact-span only; broad cites penalized; not entailment).

Pre-registered 03B rule (`decision_thresholds.json`): retention ≥ 0.5 AND
misleading ≤ 0.10 AND D beats S by ≥ 0.10 retention without > 0.05 misleading
excess, ≥ 30 scored; else NO_PROGRESS; insufficient/unrun/exposed →
INCONCLUSIVE. No composite substitution; no tuning to observed model results.
Confusion matrices, per-category/origin/kind strata, paired discordances, and
family clustering reported with denominators. Wilson 95% illustrative only
(non-independent families; no significance/generalization). Citation validity
is an integrity gate, not entailment; free-text scope/limitations need
independent output adjudication. Authorization/citation/consent/budget gates
are hard failures. Model import/execution unavailable; scoring fixtures only
via unit-test flag, never CLI.

## Freeze, amendments, 03B prerequisites

Inputs, annotations, prompts, schemas, metrics, thresholds, and tool hashes
LF-normalized SHA-256 in `protocol.json`. v1.1–v1.4 history in
`amendments.json` + new v1.5 entry; v1.4 evidence retained. Baseline
expectations derived from measured replay stored separately; never rewritten to
hide behavior change. Full normalized comparison (metrics+strata+per-case
decisions) in CI.

Before 03B: independent review of this protocol; adjudicate public labels;
collect restricted 12-case package with verified boundary + attestations;
resolve 5 Notebook-02 contract issues in a narrow migration; add reviewed
single/dual-source governance adapter; freeze model/settings/pricing; owner
approval of exact payloads/caps; qualify cancellation/restart and
citation revalidation. None authorized by R1. Stop after draft PR; human merge
only.
