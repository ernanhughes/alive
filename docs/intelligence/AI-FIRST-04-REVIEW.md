# AI-FIRST-04 review guide and results

**Bottom line, stated plainly.** Selective adaptation **did not demonstrate an improvement over the
stateless model and did not reduce regressions by the protocol's own test.** On 36 fresh held-out
tasks the stateless baseline (A) solved 33, history (B) 31, AI-FIRST-03 family-latest lessons (C) 30
and the new selector (D) 31. D lost to A on 4 tasks and beat it on 2 (exact McNemar p = 0.69); C lost
to A on 4 and beat it on 1. The pre-declared "reduced negative transfer" outcome required D to lose to A on
*strictly fewer* tasks than C: 4 vs 4, so the result is **Outcome C, no demonstrated improvement**.
The stateless model was already at ceiling on every development and calibration task (18/18), so
this corpus could not have shown a large gain even if lessons help. Everything below is a first-pass
result on small, related Python fixtures with one model. It is not a population claim.

What *is* supported: every D loss against A was a **structural omission, not a reasoning error**
(the answer omitted the required per-case predictions and `issue_present`); D made **no** wrong
prediction on 36 tasks (C made 3, A made 1); D supplied roughly half as many context bytes as C,
had 2.3× C's lesson precision against independently assigned gold mechanisms (0.42 vs 0.19) and
better recall; the new contract eliminated the AI-FIRST-03 reference-validation losses (0 in this run);
and persistence/replay held (247 exchanges re-read and re-submitted, zero provider requests).
What is **not** supported: that lessons improve reasoning, that the selector reliably chooses
no lesson (it did so correctly on only 3 of 13 tasks lacking a relevant lesson), or that any lesson's
causal influence has been shown.

Design: [AI-FIRST-04.md](AI-FIRST-04.md). Protocol (predeclared, one amendment):
[AI-FIRST-04-PROTOCOL.md](AI-FIRST-04-PROTOCOL.md). Diagnosis of AI-FIRST-03:
[AI-FIRST-04-DIAGNOSIS.md](AI-FIRST-04-DIAGNOSIS.md). Raw evidence:
[evidence/selective-*](evidence/selective-evidence-manifest.json).

## 1. Integration and base

`main` (89e3822, tree d5ca9a6…) lacked `alive/adaptation/` because PR #94 merged into
`codex/integrate-contextual-92`. The six approved AI-FIRST-03 commits were cherry-picked onto main as
draft PR [#95](https://github.com/ernanhughes/alive/pull/95); the resulting tree
`e7219960ca9d030635fed8d6901261369b1a8f4d` is byte-identical to approved `2fc4c06`. 46 focused
tests passed on it. This PR is stacked on that branch (base `ai-first-03-integration-main`,
`659945f`); retarget to `main` after #95 merges. Not merged by me.

## 2. Production files changed (vs #95)

`alive/adaptation/{oracle_v2,selection}.py` (new), `alive/adaptation/{contracts,service}.py`,
`alive/continuity/{contracts,adapters,service}.py`, `alive/intent/contracts.py`,
`alive/admission/{contracts,live}.py`, `alive/capabilities/trusted.py` (custody list), dashboard
`LivePane.tsx`. Reused unchanged: Cognition, ModelGateway/Pi, Governor, standing consent, source
custody, existing lesson event chain, `adaptation.experience`, the AI-FIRST-03 `selected()` as arm C.
No new gateway, memory store, vector index, trained selector or policy hierarchy.

## 3. Oracle v2 and the fixtures

`frozen-executable-fixture/v2` observes return value or exception type and the input before/after
execution (nested), reports semantics tri-state (correct / incorrect / undetermined) apart from contract
compliance, reference integrity and grounding, and refuses a fixture whose reference disagrees with its
expectation. v1 is byte-identical and pinned by a test. Regrading the retained AI-FIRST-03 answers
under v2 (supplementary file, originals untouched) corrects the `errors-4` label for all arms and
shows B's two validator rejections were factually correct answers.

Corpus: 72 tasks (18 train, 12 dev, 6 calibration, 36 held-out; 57 defective, 15 correct
implementations; tiers standard/hard/extreme). Each case has an expected outcome; original 54 were
hand-written, the 18 `extreme` tasks derive theirs from an independent third implementation. The audit
confirms implementation, reference and expectation agree as each label requires, determinism, no leaky
vocabulary or comments, and held-out↔training mechanism coverage. **This is a programmatic audit by the
implementation agent, not independent human adjudication.**

## 4. Response-contract changes

Contract v2 (versioned, identical for every arm): typed references; explicit review obligation
(one prediction per README case + `issue_present`); `contract_compliance` and `reference_integrity`
recorded structurally; an extraction instruction that says an extraction is not a review. Real
supplied items of the wrong type are normalized and never credited as strategy use; fabricated IDs
still refuse the turn. No repair/retry. Held-out reference-integrity failures: 0 in every arm
(AI-FIRST-03: 2 in B).

## 5. Selector and no-lesson behaviour

See [AI-FIRST-04.md](AI-FIRST-04.md#the-selector). Live result: D supplied a lesson on 28 of 36
held-out turns and none on 8 (`no_applicable_lesson`). The live intent call names 3–4 mechanisms per
task from the contract text; overlap with a lesson's declared mechanisms is easy to satisfy, so
the selector is **more targeted than C but not conservative**.

| Selection vs gold mechanisms (held-out) | B history | C family-latest | D selective |
| --- | --- | --- | --- |
| Lessons supplied (36 turns) | 63 | 65 | **36** |
| Precision (supplied that were gold-relevant) | 0.175 | 0.185 | **0.417** |
| Recall (23 tasks had a relevant lesson available) | 9/23 | 10/23 | **15/23** |
| Correctly supplied none (13 tasks without a relevant lesson) | 0/13 | 0/13 | 3/13 |
| Median context bytes | 1706 | 2257 | **1133** |

## 6. Held-out results (36 tasks, first pass)

| | A stateless | B history | C family-latest | D selective |
| --- | --- | --- | --- | --- |
| **End-to-end success (primary)** | **33** | 31 | 30 | 31 |
| Semantic correct / incorrect / undetermined | 33 / 1 / 2 | 31 / 0 / 5 | 30 / 3 / 3 | 31 / **0** / 5 |
| Contract-compliant (structure) | 34 | 31 | 33 | 31 |
| Run failures (no validated answer) | 0 | 1 | 0 | 0 |
| Reference failures / normalized | 0 / 0 | 0 / 0 | 0 / 0 | 0 / 0 |
| Provider requests · measured tokens | 72 · 228,489 | 71 · 248,114 | 72 · 253,552 | 72 · 242,703 |
| Tokens per correct task | 6,924 | 8,004 | 8,452 | 7,829 |
| Median invocation latency (ms) | 7,819 | 7,994 | 8,293 | 8,356 |

By tier (A/B/C/D): standard 9/9, 9/9, 8/9, 7/9 · hard 14/15, 14/15, 12/15, 14/15 · extreme 10/12,
8/12, 10/12, 10/12. By label: defective 24, 22, 21, 24 of 27 · correct implementations 9, 9, 9, 7 of 9.

| Paired (end-to-end) | wins | losses | both pass | both fail | exact p (descriptive) |
| --- | --- | --- | --- | --- | --- |
| D vs A | 2 (`sta-07`, `def-11`) | 4 (`par-06`, `err-11`, `aut-09`, `par-09`) | 29 | 1 | 0.69 |
| D vs C | 3 (`sta-07`, `def-08`, `sta-11`) | 2 (`err-11`, `aut-09`) | 28 | 3 | 1.0 |
| D vs B | 4 | 4 | 27 | 1 | 1.0 |
| C vs A | 1 (`def-11`) | 4 (`par-06`, `def-08`, `sta-11`, `par-09`) | 29 | 2 | 0.375 |
| B vs A | 1 (`sta-07`) | 3 (`aut-08`, `sta-11`, `err-12`) | 30 | 2 | 0.625 |

**Negative transfer.** Every D loss to A (`par-06`, `err-11`, `aut-09`, `par-09`) omitted the required
predictions and `issue_present`; none had a wrong prediction. `err-11` and `aut-09` are correct
implementations. Structural completeness by lesson presence (descriptive, confounded by task): D with
no lesson 8/8, one lesson 16/20, two lessons 7/8; A (never a lesson) 34/36; B 31/36. This reproduces,
under a clearer contract, the AI-FIRST-03 pattern that context-bearing turns omit structured fields more
often, and it is the dominant remaining failure. Whether the context *causes* it is **not established**.
**Positive transfer.** `sta-07` and `def-11` (D passed, A failed). Lesson ablation (2 repetitions each):
`def-11` passed 2/2 *with* and 2/2 *without* the lesson, so A's failure there was run-to-run noise;
`sta-07` passed 1/2 with and 0/2 without: suggestive, far too small to call causal.
**Variability** (3 tasks × 4 arms repeated): A, B and D reproduced on all three; C changed on two
(`def-08` fail→pass, `err-09` pass→fail). **Relevance/quantity ablation** (4 dev tasks × {none,
1 relevant, 1 irrelevant, 1 relevant + 2 irrelevant, 3 irrelevant}): 15/16 forced-lesson turns passed
(baseline 4/4); the single failure was a structural omission with three lessons. At ceiling this cannot
separate "wrong context" from "more context"; it is **inconclusive**.

### Full paired table (A/B/C/D end-to-end; 1 = success)

| Task | tier / label | A | B | C | D | D received | Explanation of differences |
| --- | --- | --- | --- | --- | --- | --- | --- |
| aut-06 | hard/defective | 1 | 1 | 1 | 1 | e09ae02b | all arms ok |
| aut-07 | hard/defective | 1 | 1 | 1 | 1 | none | all arms ok |
| aut-08 | hard/defective | 1 | 0 | 1 | 1 | 2a189e1e | B: omitted predictions c1,c2,c3,c4,c5 + issue flag |
| aut-09 | standard/correct | 1 | 1 | 1 | 0 | 2a189e1e | D: omitted predictions c1,c2,c3,c4,c5 + issue flag |
| aut-11 | extreme/correct | 1 | 1 | 1 | 1 | aef45ef8 | all arms ok |
| aut-12 | extreme/defective | 1 | 1 | 1 | 1 | 6c3ccf44 | all arms ok |
| def-06 | hard/defective | 1 | 1 | 1 | 1 | b104ff31 | all arms ok |
| def-07 | hard/correct | 1 | 1 | 1 | 1 | none | all arms ok |
| def-08 | hard/defective | 1 | 1 | 0 | 1 | e09ae02b | C: omitted predictions c1,c2,c3,c4,c5,c6 + issue flag |
| def-09 | standard/defective | 1 | 1 | 1 | 1 | b104ff31,1ddd12be | all arms ok |
| def-11 | extreme/defective | 0 | 0 | 1 | 1 | b104ff31 | A: incomplete structure: no issue_present; B: omitted predictions c1,c2,c3,c4,c5 + issue flag |
| def-12 | extreme/defective | 1 | 1 | 1 | 1 | 97392e3c | all arms ok |
| err-06 | hard/defective | 1 | 1 | 1 | 1 | 2a189e1e,8ba2e504 | all arms ok |
| err-07 | hard/defective | 1 | 1 | 1 | 1 | b104ff31 | all arms ok |
| err-08 | standard/defective | 1 | 1 | 1 | 1 | 82ac7d4b | all arms ok |
| err-09 | standard/correct | 1 | 1 | 1 | 1 | none | all arms ok |
| err-11 | extreme/correct | 1 | 1 | 1 | 0 | 97392e3c,82ac7d4b | D: omitted predictions c1,c2,c3,c4,c5,c6 + issue flag |
| err-12 | extreme/defective | 1 | 0 | 1 | 1 | 9eb4fb2e,82ac7d4b | B: omitted predictions c1,c2,c3,c4,c5,c6,c7,c8 + issue flag |
| num-06 | standard/defective | 1 | 1 | 1 | 1 | 5afe92c4 | all arms ok |
| num-07 | hard/defective | 1 | 1 | 1 | 1 | none | all arms ok |
| num-08 | standard/correct | 1 | 1 | 1 | 1 | 5afe92c4 | all arms ok |
| num-09 | hard/defective | 1 | 1 | 1 | 1 | 82ac7d4b | all arms ok |
| num-11 | extreme/defective | 1 | 1 | 1 | 1 | none | all arms ok |
| num-12 | extreme/defective | 1 | 1 | 1 | 1 | none | all arms ok |
| par-06 | standard/defective | 1 | 1 | 0 | 0 | 9eb4fb2e | C: omitted predictions c1,c2,c3,c4 + issue flag; D: omitted predictions c1,c2,c3,c4 + issue flag |
| par-07 | hard/defective | 1 | 1 | 1 | 1 | 9eb4fb2e | all arms ok |
| par-08 | standard/correct | 1 | 1 | 1 | 1 | none | all arms ok |
| par-09 | hard/defective | 1 | 1 | 0 | 0 | 82ac7d4b | C: omitted predictions c1,c2,c3,c4,c5 + issue flag; D: omitted predictions c1,c2,c3,c4,c5 + issue flag |
| par-11 | extreme/defective | 0 | 0 | 0 | 0 | 9eb4fb2e | A: incomplete structure: malformed c2,c6; B: no validated answer (adapter_execution_failure); semantic undetermined; C: wrong prediction c2:req,c6:req; D: omitted predictions c1,c2,c3,c4,c5,c6 + issue |
| par-12 | extreme/defective | 1 | 1 | 1 | 1 | 9eb4fb2e,82ac7d4b | all arms ok |
| sta-06 | standard/defective | 1 | 1 | 1 | 1 | 5afe92c4,b104ff31 | all arms ok |
| sta-07 | hard/defective | 0 | 1 | 0 | 1 | 8ba2e504 | A: wrong prediction c4:req; C: wrong prediction c4:req |
| sta-08 | hard/correct | 1 | 1 | 1 | 1 | 8ba2e504,82ac7d4b | all arms ok |
| sta-09 | hard/defective | 1 | 1 | 1 | 1 | 97392e3c | all arms ok |
| sta-11 | extreme/defective | 1 | 0 | 0 | 1 | aef45ef8,b104ff31 | B: omitted predictions c1,c2,c3,c4,c5 + issue flag; C: wrong prediction c3:req |
| sta-12 | extreme/correct | 1 | 1 | 1 | 1 | none | all arms ok |

## 7. Cost, scale, recovery

All real inference used the pinned `muse-spark-1.3-contributor` through production Pi to
`https://api.meta.ai/v1/chat/completions` (transport model `muse-spark-1.3-contributor`; the provider
reports no observed identity, so identity is requested, not attested). Across **all** AI-FIRST-04 runs:
**533 provider requests, 1,806,599 measured tokens, 3,964 s summed provider latency** (main run 483
requests/1,632,532 tokens; demonstration 7/22,576; interrupted run 37/130,163; first pilot 6/21,328). Currency cost
is unknown and not estimated. The main run stayed inside the predeclared envelope (<=560 requests) and
the Governor's 500-call ceiling. No failed inference was retried; 6 of 483 main-run requests were not
HTTP 200 (provider truncation or similar provider failure). The selector adds **zero** model calls, so D's call count equals C's.
Restart: `replay` reopened the database, re-read and re-submitted 247 retained requests, provider
requests 467→467, reservations unchanged, policy digest unchanged. Product demonstration
([evidence](evidence/selective-demo.json)): verified experience → owner-approved lesson →
a lesson supplied for the boundary task (`num-05`) and none for an unrelated parsing task (`par-04`) →
independent outcomes → feedback → restart with 7→7 requests. The browser scenario against its
retained database passed with zero write requests ([supplied](evidence/selective-demo-supplied-1440.png),
[mobile](evidence/selective-demo-supplied-390.png), [none](evidence/selective-demo-none-1440.png)).

## 8. Deviations and disclosures (all in the retained ledgers)

1. First pilot produced no lessons (one `output_truncated`, one extraction treated as a review) →
   instruction clarified; one counted extraction retry permitted for *training-state preparation only*
   (9 of 18 tasks needed it; 14 of 18 produced a lesson; 4 did not).
2. The second run was cut off when I edited custody-hashed files mid-run (`capability_authority_changed`,
   the guard working); two validator problems found there were fixed and the study restarted in a clean database.
3. **Amendment 1:** development showed A at 12/12, so 18 `extreme` tasks were added before any
   held-out call; calibration A scored 6/6, and the protocol's pre-committed rule (report the ceiling,
   proceed as locked) was followed.
4. Dev arms B and C were not run (budget); in development D supplied a lesson on 8 of 12 tasks. All lessons stayed `unproven`: no paired gain or loss occurred in
   development, so empirical *demotion* and *useful* promotion were **not exercised live**
   (OFFLINE_TESTED only).
5. `positive` ablation candidates were limited to two tasks (A-fail/D-pass) by design.

## 9. Acceptance gates

| Gate | Status | Boundary |
| --- | --- | --- |
| SELECT-01 integration | IMPLEMENTED, OFFLINE_TESTED | Draft PR #95; tree identical to approved head |
| SELECT-02 v1 evidence preserved | OFFLINE_TESTED | v1 oracle/corpus/lock pinned; regrade is separate and labelled |
| SELECT-03 v2 oracle side effects | OFFLINE_TESTED, LIVE_DEMONSTRATED | 12 oracle tests; used for every live grade |
| SELECT-04 fixtures audited | IMPLEMENTED | Programmatic audit only; **not independent human review** |
| SELECT-05 semantic/structural/reference | OFFLINE_TESTED, LIVE_DEMONSTRATED | Tri-state semantics; first-pass only |
| SELECT-06 typed references | OFFLINE_TESTED, LIVE_DEMONSTRATED | 0 reference failures live |
| SELECT-07 selector can select | OFFLINE_TESTED, LIVE_DEMONSTRATED | |
| SELECT-08 selector can decline | OFFLINE_TESTED, LIVE_DEMONSTRATED | Live declining is weak: 3/13 correct |
| SELECT-09 contradiction affects eligibility | OFFLINE_TESTED | Not exercised live |
| SELECT-10 owner/model boundaries | OFFLINE_TESTED | Wrong owner/destination, tamper, injection, withdrawal tests |
| SELECT-11 decisions and context persisted | OFFLINE_TESTED, LIVE_DEMONSTRATED | Selection event bound to model-input digest |
| SELECT-12 fresh frozen data | IMPLEMENTED | Locked; Amendment 1 disclosed |
| SELECT-13 four conditions, same model | LIVE_DEMONSTRATED | Requested identity only |
| SELECT-14 independent v2 grading | LIVE_DEMONSTRATED | |
| SELECT-15 positive/negative separate | LIVE_DEMONSTRATED | Table above |
| SELECT-16 relevance/quantity ablations | LIVE_DEMONSTRATED (ran), **inconclusive** | Ceiling |
| SELECT-17 selection cost measured | LIVE_DEMONSTRATED | Zero extra calls |
| SELECT-18 product demonstration | LIVE_DEMONSTRATED | Lesson supplied and no-lesson case |
| SELECT-19 restart/replay idempotent | OFFLINE_TESTED, LIVE_DEMONSTRATED | 247 exchanges; 467→467 |
| SELECT-20 conclusions/limits | IMPLEMENTED | This document |
| SELECT-21 no new framework | IMPLEMENTED | |
| **Positive adaptation** | **NOT DEMONSTRATED** | D did not beat A |
| Independent review | **NOT_RUN** | None yet |

## 10. Known limitations and what an independent reviewer should check

* Ceiling: the baseline solved every dev and calibration task; gains were nearly unmeasurable.
* One model, small related Python fixtures, tasks authored by the implementation agent, 36 held-out tasks sharing mechanisms; p-values are descriptive.
* Mechanism tags come from the model (intent call, lesson proposals); poor tagging directly degrades selection. The selector's deterministic rule is auditable but loosely discriminating.
* Structural omission remains the main failure and its relationship to context is unresolved; a smaller, task-specific contract (or constrained decoding) is the obvious next experiment, not claimed here.
* Review targets: oracle v2 and corpus audit independently; whether gold mechanism assignments are fair; the ledger vs the local databases; the selection records of the four D losses; Amendment 1 timing (committed before any held-out call, see git history).
* Full backend suite, Docker, full browser suite, CI qualification: NOT_RUN by design.
