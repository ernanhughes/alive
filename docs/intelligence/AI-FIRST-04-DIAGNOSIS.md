# AI-FIRST-04 diagnosis of the AI-FIRST-03 negative result

Scope: read-only inspection of the retained AI-FIRST-03 evidence
(`evidence/adaptation-live-ledger.json`, `evidence/adaptation-summary.json`, the frozen v1 corpus and
`alive/adaptation/oracle.py`). **No original score, label, corpus or receipt was changed.** Where this
document re-evaluates a retained answer, it uses oracle v2 in a separate, labelled file
([`evidence/ai-first-04-v1-regrade.json`](evidence/ai-first-04-v1-regrade.json), produced by
`scripts/regrade_v1_under_v2.py`). That regrade is supplementary; it is not the original experiment.

## Headline

AI-FIRST-03 reported A 11/12, B 8/12, C 8/12 fully correct on held-out tasks. Re-reading every
non-perfect record shows that the "learned context made the model worse" reading is **not supported
as stated**, and also not refuted:

* Of the 4 B failures and 4 C failures on the held-out panel, **no B failure and only one C failure
  (`numeric-5`) is an observed semantic error.** The others are a defective oracle label, two
  validator rejections of correct answers, one provider truncation, and two answers whose prose was
  right but which omitted the required structured fields.
* The one clear C reasoning error (`numeric-5`) is not separable from run-to-run noise: the
  stateless arm gave the identical error on its repeat (A: 1.0 first run, 0.8 on repeat).
* The stateless model solved every valid held-out task (ceiling), so the panel could not have shown
  an improvement even if lessons helped.

What the data **does** support: context-bearing arms failed *output-contract and validation
reliability* more often than the stateless arm, and the selector supplied lessons from families the
task did not need (the same irrelevant `parsing` lesson was present in both C zero-scores that had
two lessons). Whether that irrelevant context *caused* the omissions is inconclusive: n is tiny and
the third C omission (`state-3`, dev) carried a single, same-family lesson.

## Supplementary v2 regrade (retained answers, not a replacement)

| Panel | Arm | v1 full | v2 semantic correct / incorrect / undetermined | v2 structurally compliant |
| --- | --- | --- | --- | --- |
| held-out (12) | A stateless | 11 | 12 / 0 / 0 | 12 |
| held-out (12) | B history | 8 | 11 / 0 / 1 | 11 |
| held-out (12) | C strategies | 8 | 9 / 1 / 2 | 10 |
| dev (6) | A | 6 | 6 / 0 / 0 | 6 |
| dev (6) | B | 6 | 6 / 0 / 0 | 6 |
| dev (6) | C | 5 | 5 / 0 / 1 | 5 |

"Undetermined" means the retained evidence shows a structural failure (missing fields or no output),
so the oracle cannot say whether the reasoning was right. B's two reference-validator rejections were
regraded from the **raw validated model output retained on the failed run** (the validator discarded
them; the output exists in the ledger's `workflow_failures`). Under v2 the `errors-4` label defect is
corrected for all three arms. Prose remains unverified.

## Failure categories

**A. Oracle defect (`errors-4`, all arms).** Contract: "Pop last element from a copied list".
Implementation calls `p.pop()` and destroys the caller's list; the v1 reference does the same. v1
executes return values and exception types only, so it derived `issue_present = false` and scored
every arm's correct `issue_present = true` as wrong (0.8 each). Verifier defect, not model reasoning.
Fixed in oracle v2 (observes the input before and after execution); v1 is unchanged.

**B. Missing required structured output.** `ContextualAnswer.predictions` defaults to `[]` and
`issue_present` to `None`: "required by the evaluation contract" lived only in prose instructions
and the goal text. In three C turns the model answered correctly in prose and omitted both.

**C. Historical-reference validation confusion.** `validate_answer` checked `lesson_ids_used`
only against `learned_strategy` item IDs. Condition B supplies `historical_experience` items whose
`id` is the originating lesson row ID, so a model reporting that supplied record as "used" was
rejected with `lesson_not_supplied`, discarding an otherwise valid answer. The type distinction
did not exist in the response schema.

**D. Coarse relevance.** Selection was "intent family tags → latest eligible lesson per family, up
to two". It cannot prefer an older, better-matching lesson, cannot exclude a lesson whose own
`not_when` applies, and fills a second slot with a different family's lesson.

**E. Evaluation ceiling.** A scored 11/11 on valid held-out tasks; there was no headroom.

**F. Inference variability.** `numeric-5` repeats changed A 1.0→0.8, B 0.0→0.8, C 0.8→1.0.

## Per-failure record

"Used" is the model's `lesson_ids_used`, a self-report, not causal evidence. `Ref` is
`review.result_admission_id` in the retained ledger (first 8 chars) and its model invocations.

| Task / arm | Ref | Reasoning wrong? | Structured output invalid? | Reference validation failed? | Context supplied (selected) | Used (self-report) | Attributable to a lesson? |
| --- | --- | --- | --- | --- | --- | --- | --- |
| dev `state-3` C | `a7fb18fc` | No: prose correctly identifies `sorted(set(p))` order defect | **Yes**: no predictions, no `issue_present` | No | 1 lesson: `state` terminal-state guard (same family, off-mechanism) | none | **Inconclusive** |
| held-out `numeric-4` C | `79cd6738` | No: prose "no defect", matches reference | **Yes**: no predictions, no flag | No | 2 lessons: `parsing` split-first-delimiter (**different family**), `numeric` interval bounds | none | **Inconclusive**; irrelevant `parsing` lesson present |
| held-out `defaults-4` C | `f9639f26` | No: prose "no defect", matches reference | **Yes**: no predictions, no flag | No | 2 lessons: `defaults` falsy-vs-absent (**relevant**), same irrelevant `parsing` lesson | none (recalled 1 ID) | **Inconclusive**; irrelevant `parsing` lesson present |
| held-out `numeric-5` C | `3ae64795` | **Yes**: predicted required value 0 for one case | No | No | 1 lesson: `numeric` interval bounds (loosely related) | `b91fdbdd` | **Inconclusive**: the stateless repeat made an error on the same case (`c2`) |
| held-out `numeric-5` B | `44289094` | Unknown | No output (`output_truncated`, provider) | n/a | 1 historical record | n/a | **Inconclusive**: truncation, no usable output |
| held-out `parsing-5` B | `e9dd5add` | **No**: raw output matches reference on every case | No | **Yes**: historical ID reported as strategy | 2 historical records (`defaults`, `parsing`) | `3ce34f5b` (a historical record) | Validator artifact; v2 regrade 1.0 |
| held-out `defaults-5` B | `ef662212` | **No**: raw output matches reference on every case | No | **Yes**: same typing error | 2 historical records (`defaults`, `state`) | `7a35c1ec` (a historical record) | Validator artifact; v2 regrade 1.0 |
| held-out `errors-4` A/B/C | `bd387486`, `7f78b455`, `8ea5ca76` | **No**: all three identify the mutation | No | No | none / 1 historical / 1 strategy | none | **Oracle label defect** (category A) |
| repeat `numeric-5` A | `358024cb` | Yes (one case) | No | No | none | none | Baseline variability |
| repeat `numeric-5` B | `a6be66f0` | No: all four predictions correct | Yes: `issue_present` omitted | No | 1 historical record | none | Inconclusive |

## What this changes about AI-FIRST-04

1. Fix the instrument first (oracle v2), then measure again on **fresh** held-out data. These 36
   AI-FIRST-03 held-out/dev responses have shaped this diagnosis and must not be reused as untouched.
2. Make the structured-output obligation explicit, versioned and identical across arms; measure
   first-pass compliance as its own outcome.
3. Type-aware reference validation: a supplied historical record may be reported as historical
   evidence; a fabricated ID, or a claimed strategy that was never supplied, is still rejected.
4. Replace unconditional family-level selection with mechanism-level applicability, an explicit
   "no lesson" outcome, and evidence-aware demotion.
5. Build tasks with baseline headroom, report by difficulty tier, and keep paired repeats.

## Limits of this diagnosis

* Implementation-agent adjudication, not independent human review.
* Retained single responses; no re-inference was performed for this document.
* Causal claims about lesson influence are deliberately avoided throughout.
