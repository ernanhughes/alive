# AI-FIRST-04 predeclared protocol

Written and committed **before any development or held-out inference**. A two-task training pilot
preceded this protocol to prove the plumbing. It produced zero lessons (one provider
`output_truncated`, one extraction answered without `lesson_proposal`), which led to a clearer
extraction instruction and the counted-retry rule above. The pilot ledger is retained as evidence. Anything not listed here as planned is reported as exploratory. This protocol is not
edited after the development phase starts; a deviation is recorded in the results report, not here.

## Question and hypothesis

Can ALIVE improve future decisions by selectively applying independently evaluated experience, and
avoid the harm that unconditional context caused in AI-FIRST-03?
*Hypothesis (to test, not assume):* mechanism-level, outcome-aware selection (arm D) yields higher
end-to-end task success than automatically supplied experience (arm C), and not lower than the
stateless baseline (arm A). Three outcomes are acceptable and will be reported as they fall:
positive adaptation (D > A), reduced negative transfer (D materially closer to A than C is), or no
demonstrated improvement.

## Model and transport

`meta/muse-spark-1.3-contributor` through the existing production path
Cognition → ModelGateway → Pi → Meta (`https://api.meta.ai/v1/chat/completions`; recorded transport
model `muse-spark-1.3-contributor`). One pinned model, one role contract, one output ceiling for every
arm. No local substitute, no second model, no model judge, no automatic retry. The provider reports
no observed internal model identity; only the requested identity and transport are evidenced.

## Frozen artifacts

`docs/intelligence/selective-corpus-v2.json` (54 tasks: 18 train, 12 dev, 24 held-out; 42
defective and 12 correct implementations; each case has a hand-written expected outcome), its audit
and `selective-corpus-v2-lock.json` (corpus, oracle v2, audit, contextual and intent role-contract
hashes, seed 4401). The fresh held-out set shares no task, function name or answer with
AI-FIRST-03. Tiers (`standard`/`hard`) and gold `mechanisms` were assigned at authorship, before any
inference, and are used only for analysis, never shown to the model.

## Arms (same source, goal text, model, settings and output contract per matched task)

| Arm | `strategy_mode` | Experience supplied |
| --- | --- | --- |
| A | stateless | none |
| B | contextual | owner-approved historical assessment/outcome excerpts (AI-FIRST-03 behaviour) |
| C | learned | AI-FIRST-03 family-latest strategy selection (preserved control) |
| D | selective | new mechanism-level selector; may supply lessons or none (treatment) |

Every turn is a separate conversation of one intent call and one reasoning call. D adds **no**
model call: applicability is decided deterministically from model-supplied mechanism tags and
measured outcomes, so D's call count equals C's. Arm order per task is shuffled with seed 4401.

## Phases and sizes

1. **Training** (18 tasks, arm A, then one lesson-extraction turn each): independently measured
   experiences and owner-approved public lessons. 54 calls. If an extraction turn yields no valid
   lesson proposal (truncation, omitted field), one counted extraction retry is allowed per task:
   this prepares learned state and is not an evaluated arm (≤18 extra calls, always reported).
2. **Development** (12 tasks, arms A and D, paired): calibrates baseline difficulty and gives each
   supplied lesson paired outcomes (gain/loss against A) that may demote or support it. 48 calls.
   Dev arms B and C are not run (budget). **The policy is then frozen**; its digest is asserted
   unchanged before every later turn.
3. **Held-out** (24 tasks, arms A–D, 192 calls): report-only. Held-out outcomes never create
   experiences, applications or lessons.
4. **Repeats** (`num-06`, `sta-06`, `def-08`, `err-09`, all arms, 32 calls): run-to-run variability.
5. **Relevance/quantity ablation** (6 dev tasks × 4 forced lesson sets, 48 calls): none (the dev
   A run), 1 relevant, 1 irrelevant, 1 relevant + 2 irrelevant, 3 irrelevant. Relevance is fixed by
   corpus gold mechanisms of the originating training task, never by model outcome.
6. **Positive-transfer lesson ablation** (≤4 held-out tasks where A failed and D passed with a
   lesson; with and without that lesson, 2 repetitions each, ≤32 calls).

Total ≈ 400 calls against the Governor's 500-call / 2,000,000-token experiment ceiling. Envelope for
this study: 560 provider requests and 8,000,000 conservative units; the existing Governor and
standing-consent limits still enforce. Currency cost is unknown and will not be estimated.

## Metrics

**Primary:** independently verified **end-to-end** task success on the 24 fresh held-out tasks:
compliant structured output, every per-case prediction and the defect flag correct, no
reference-integrity failure. Secondary: semantic correctness (tri-state), contract compliance,
reference failures, grounding, positive/negative transfer vs A, selection precision/recall and
no-lesson correctness against gold mechanisms, calls and tokens per correct task, median invocation
latency, context bytes. Each failure is reported with its actual cause.

## Analysis plan

Paired per-task wins/losses/ties for D vs A, D vs C, D vs B, and C vs A, plus the full per-task table.
Exact two-sided McNemar (binomial on discordant pairs) for binary end-to-end results, reported with
the discordant counts and no claim of significance without them. The 24 tasks are related (shared
mechanisms), so p-values are descriptive. Results are also split by tier and by whether a gold
relevant lesson existed. Repeats are reported separately and never pooled into the primary count.

## Pre-declared interpretation

Outcome A (positive adaptation) requires D to beat A with discordant pairs favouring D and the
positive cases surviving the lesson ablation. Outcome B (reduced negative transfer) requires D to
lose to A on strictly fewer tasks than C does. Anything else is Outcome C. A ceiling in arm A is
reported as such; the corpus is not changed after the first held-out call.

## Known limits (declared in advance)

Programmatic audit of the fixtures, not independent human adjudication; implementation-agent
authored tasks; one model; small, related Python fixtures; prose unverified by the oracle; first-pass
results only (no repair/retry); AI-FIRST-03 evidence was used to design the experiment, so none of its
held-out tasks are reused.

## Amendment 1 (before any held-out or calibration call)

The development phase finished with **arm A solving 12/12 development tasks (all six "hard" ones)**
and arm D matching it (lessons supplied on 7 tasks, none on 5; no paired gain or loss). The corpus
therefore had no headroom, the AI-FIRST-03 ceiling problem again. Before opening held-out, and
without using any held-out outcome (none exists):

* 18 computation-heavy tasks (`extreme` tier) are **added unconditionally**: 6 `calibration` tasks
  (arm A only, report-only, never used for lessons or held-out claims) and 12 more held-out tasks.
  Held-out becomes 36 tasks (15 correct implementations in the corpus overall). The 54 original tasks
  are unchanged. Nothing is selected or dropped by outcome.
* Their expected values come from an **independent third implementation** (a differently formulated
  `spec`), not from hand typing; the audit requires implementation, reference and spec to agree as the
  label demands. Three held-out `extreme` tasks are correct implementations.
* Budget is re-planned under the Governor's 500-call experiment ceiling: ~111 calls already spent in
  training and development, calibration 12, held-out 288, repeats (`num-06`, `def-08`, `err-09`)
  24, ablation (4 development tasks) 32, positive-transfer ablation (<=3 tasks) 24. Dev arms B/C stay
  unrun.
* If arm A also solves the calibration tasks, that is reported as a ceiling and held-out proceeds
  as locked; no further tasks are authored.

The primary metric, arms, selector, analysis plan and interpretation rules above are unchanged.
