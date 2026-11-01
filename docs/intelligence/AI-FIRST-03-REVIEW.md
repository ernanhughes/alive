# AI-FIRST-03 review guide

This change implements a bounded adaptation loop over the existing live contextual path.
It does not train model weights, grant execution powers, or establish broad learning quality.
The accompanying qualification report and receipts determine the experimental result.

## Integration and scope

PR #93 integrates the already-approved contextual tree from #92 onto main. Its head
`66c42437c0a579bfbf62225a264783eabb39dbd2` exactly matches approved #92 `7d2e753` by tree.
The adaptation branch is `ai-first-03-measured-adaptation`, stacked on #93 while that integration
remains unmerged. No automatic merge, full-suite run, CI configuration change or dependency change.

The live experiment implementation is pinned in its ledger. Public fixtures and the executable
grader were frozen before calls. The first two-call pilot refused grading because Windows wrote
CRLF instead of the specified LF fixture bytes. That pilot is retained, not scored as qualification
or discarded. The fixture writer now preserves exact bytes; a focused capture-to-oracle regression
covers it. No held-out outputs were consumed before that correction.

## Existing mechanisms reused

`admission.live` retains standing owner consent and exact per-run grants. `continuity` freezes
bounded contextual inputs and binds their hashes through the workflow, Cognition, ModelGateway
and production Pi. Source custody, Governor budgets, role contracts and the existing read-only
capability set remain the execution boundary. Intelligence fixture custody supplied the pattern
for separating independent measurements from model reports; its simulator policy engines remain
separate. Adaptation uses existing Event rows and admission artifacts, with no new tables or
general learner/agent framework.

`adaptation.service` records compact experiences: admission/task/split/family, exact source,
artifact and measurement references, independently checked outcome, model/role/invocation IDs
and usage. Invocation IDs lead to the existing Pi request receipts; reports are not duplicated
into a parallel repository of findings. Model confidence and citation checks cannot qualify
feedback. Owner corrections remain useful conversational evidence but are not independently
verified training labels.

The only shipped verifier is an owner-local oracle for the frozen public corpus. It executes
author-owned fixture/reference functions in a bounded subprocess with no inherited credentials.
It does not execute model code, patches or arbitrary captured repositories. Grading compares
case predictions and issue detection to actual/reference execution. Explanatory prose remains
unverified by that oracle. There is no HTTP endpoint accepting `verified: true`.

## Lesson lifecycle and disclosure

A real contextual response may propose a strategy with family, applicability, exclusions,
supporting experience IDs and uncertainty. Only supplied, independently measured **training**
experiences support a persistent proposal. Unsupported/self-reported or evaluation-derived
proposals are retained as rejected attempts without discarding the useful model answer.

The owner inspects exact reusable strategy and historical-summary text and approves its hash.
The lifecycle is proposed → qualified → active; active lessons can become revised or rejected
using independently measured train/development counterevidence. Every transition appends a
hash-chained version. Single-example lessons remain explicitly provisional. Qualification means
bounded provenance/export eligibility, not proven general validity or measured benefit.
The owner can also withdraw an export immediately without proving a quality failure. That
appends a rejected version labelled `owner_withdrew_reusable_export`, clears the reusable export,
and makes no scientific counterevidence claim. Repeated withdrawal with the same prior hash is
idempotent; another principal cannot withdraw it. Historical approved versions remain readable.

Exports are separate durable owner decisions, confined to the same instance/principal and
provider/model/endpoint. They persist until the lesson is demoted; raw prior source approval is
not widened or renewed by an export. An export can contain a bounded excerpt of the previous
assessment for condition B, so the owner must inspect **both** strategy and history text before
approving it. The demonstration authorizes only public corpus-derived text. Private source,
full reports and unrelated memories never become automatic cross-conversation inputs.

On a fresh adaptive conversation, the existing live intent call supplies family tags. At most
two active exports are selected, one per family, favoring the most recently proposed eligible
lesson. The model decides whether the supplied strategy actually applies and reports used IDs.
That coarse selection can omit an older, more useful strategy; the experiment must expose that
limitation. Frozen snapshots include exact version/content hashes; demotion fences new dispatch
without removing old history. Lessons are untrusted data and never authorize tools.

The dashboard shows provisional/state labels, feedback provenance and reported strategy IDs.
It uses the same standing session for ordinary model calls. Inspection/qualification is local:

```powershell
uv run python -m alive.adaptation inspect
uv run python -m alive.adaptation feedback ADMISSION --task PUBLIC-FIXTURE-ID --feedback-key KEY
uv run python -m alive.adaptation transition LESSON qualified --confirm-sha256 VERSION-HASH --export-sha256 EXACT-EXPORT-HASH
uv run python -m alive.adaptation transition LESSON active --confirm-sha256 QUALIFIED-VERSION-HASH --export-sha256 EXACT-EXPORT-HASH
uv run python -m alive.adaptation transition LESSON rejected --confirm-sha256 ACTIVE-VERSION-HASH --counterevidence EXPERIENCE-ID
uv run python -m alive.adaptation withdraw LESSON --confirm-sha256 ACTIVE-VERSION-HASH
```

## Experiment interpretation

The frozen corpus has 12 train, 6 development and 12 held-out tasks across six families, including
correct implementations that should not attract a defect claim. Two held-out tasks repeat in
all three arms to expose variability. Each task/arm starts a separate conversation and receives
the same source, question, requested contributor model, roles, output limit and call ceiling.
Arm order uses seed 4319. A supplies no adaptive history; B supplies permitted historical
assessment/outcome excerpts from the same eligible pool; C supplies qualified strategies.
Each evaluation turn uses one intent and one reasoning call. Context length and measured usage
can differ by design and are recorded, not disguised as equal token consumption.

The policy is frozen before development and held-out comparisons. Neither phase updates lessons,
and held-out outcomes never create training experiences. The primary score gives equal weight
to four pairs of actual/required value predictions and the defect-present boolean. Full task
success requires every unit. Missing predictions score as missing, even if the prose is useful.
This measures factual and output-contract reliability; it is not a comprehensive reasoning metric.

Reference implementations/labels were authored by the implementation agent before inference.
The executable grader is independent of model self-assessment; the corpus itself has not had
independent human label review. Any prose adjudication by the implementation agent is labelled
as such. Independent review and broader real-world qualification remain pending. The small,
related public Python fixtures and sparse repeats do not justify population-level statistics,
provider-internal model identity claims or a claim that training guarantees improvement.

## Qualification result — 1 November 2026

**The durable live learning/transfer loop is demonstrated. Positive adaptation is not established.**
The learned condition performed worse than the stateless condition on this panel. Do not promote
this result to a claim of broad learning quality. Independent review is pending.

Application used for the frozen experiment: `bce404e3842cba7cbbbf0cd2096ae21a840653b2`.
Harness resumption at `ad70ec1` changed no `alive/` code, corpus, goals, policy, role contract,
output ceiling or arm order. It skipped every completed turn, including failures. The later
owner-goal recovery correction is `a5f94e1`; it was tested in isolation while the original
experiment continued, then integrated after completion. No held-out response was retuned or
rerun for that correction. Final replay also passed with that correction present.
Final source review also added unconditional owner export withdrawal, separately labelled from
evidence-based demotion. This is a revocation-only guard, offline-tested after the experiment;
the frozen policy and all non-withdrawn model inputs remain unchanged. It is not another live
quality run or a retroactive change to the measured strategy policy.
Final application guard/UI source head: `cda88523c44038e19215b262e30606770f0c9820`.

The raw [completed ledger](evidence/adaptation-live-ledger.json),
[machine summary](evidence/adaptation-summary.json),
[interrupted checkpoint](evidence/adaptation-interrupted-checkpoint.json) and
[refused initial pilot](evidence/adaptation-pilot-failed.json) retain both successful and failed
results. The disposable database remains locally at `.alive/ai-first-03-live-02/demo.db`.
Do not publish that general database as a substitute for inspecting the public-only ledger.

Twelve durable, independently measured training experiences produced ten active **provisional**
lessons across five families. Both error-family extraction turns returned useful text but no
structured proposal, so no error-family lesson was promoted. One error-family training review
omitted required predictions and scored zero. All twelve outcomes, including that failure,
remain retained. Three held-out learned-arm responses reported using strategy IDs from separate
conversations. Supplying/recalling a strategy is evidenced; its causal internal influence is not.

| Phase | A stateless: full / mean | B history: full / mean | C strategies: full / mean |
| --- | --- | --- | --- |
| Development, 6 tasks each | 6/6 · 1.000 | 6/6 · 1.000 | 5/6 · 0.833 |
| Held out, frozen rubric, 12 each | 11/12 · 0.983 | 8/12 · 0.733 | 8/12 · 0.800 |
| Sensitivity excluding flawed `errors-4`, 11 each | 11/11 · 1.000 | 8/11 · 0.727 | 8/11 · 0.800 |
| Predeclared repeats, 2 each | 1/2 · 0.900 | 1/2 · 0.900 | 2/2 · 1.000 |

The repeat result is not a reversal of the held-out conclusion: only two tasks repeated.
`numeric-5` changed A 1.0→0.8, B 0.0→0.8 and C 0.8→1.0; all authorization repeats stayed at 1.0.
This is visible run-to-run variability, not sufficient replication for a general improvement claim.

| Held-out task | A | B | C | Finding |
| --- | --- | --- | --- | --- |
| numeric-4 | 1 | 1 | 0 | C useful prose, omitted predictions and issue flag |
| numeric-5 | 1 | 0 | 0.8 | C predicted required value 0 for zero-discount price 100; B truncated |
| parsing-4 | 1 | 1 | 1 | Matched |
| parsing-5 | 1 | 0 | 1 | B reported a historical ID as a learned strategy; validator refused it |
| state-4 | 1 | 1 | 1 | Matched |
| state-5 | 1 | 1 | 1 | Matched |
| authorization-4 | 1 | 1 | 1 | C reported strategy use; no measured gain over baselines |
| authorization-5 | 1 | 1 | 1 | Matched |
| defaults-4 | 1 | 1 | 0 | C useful prose, omitted predictions and issue flag |
| defaults-5 | 1 | 0 | 1 | B historical/strategy ID confusion; C reported strategy use |
| errors-4 | 0.8 | 0.8 | 0.8 | **Oracle label defect**, not model reasoning failure |
| errors-5 | 1 | 1 | 1 | Matched |

Negative condition differences are recorded without attributing causation to a particular lesson.
C improved over B on three cases, but never over A on the original held-out panel. Two of C's
regressions were response-contract omissions despite useful prose. Coarse family/latest selection
also supplied irrelevant lessons and omitted potentially useful older ones. B contains historical
assessment/outcome text, not the strategy payload; its export provenance label still refers to
the originating provisional-strategy record, which may be confusing. Two B responses incorrectly
reported that historical record as a used lesson and failed the declared reference validator.
These are product-level scores, not a score of raw model knowledge independent of validation.

The `errors-4` contract requires a copied list, but both fixture implementation and reference
use `p.pop()`. The return-only oracle incorrectly derives `issue_present=false`. All three arms
explicitly identify the real input-mutation defect while correctly predicting every return/error.
A separate executable audit shows input `[1]` becomes `[]`. Original scores/labels are unchanged;
the sensitivity analysis excludes this fixture equally for all arms. Independent label review
and a corrected, fresh held-out corpus are required before further quality claims. The known
fixture must not be reused to tune and requalify these prompts.

Prose above is **implementation-agent adjudication**, supported by retained answers and the
executable mutation probe; it is not an independent human/source review. There was no separate
model judge. The frozen output-oracle comparison remains auditable and all disagreements remain.

## Calls, usage and recovery

Requested model throughout: `muse-spark-1.3-contributor`, configured Meta endpoint
`https://api.meta.ai/v1/chat/completions`, through production Pi/network transport. The provider
did not report an observed internal model identity, so the evidence establishes the requested
identity and transport, not independent attestation of the provider's internal model.

| Phase | Actual requests | Measured tokens | Turn wall seconds |
| --- | ---: | ---: | ---: |
| Training reviews | 24 | 62,855 | 212.8 |
| Lesson extraction | 12 | 41,920 | 100.7 |
| Development A/B/C | 36 | 99,570 | 331.8 |
| Held-out A/B/C | 72 | 202,862 | 696.9 |
| Repeats | 12 | 34,390 | 104.8 |
| Completed experiment | **156** | **441,597** | **1,447.0** |
| Earlier refused-byte pilot | 2 | 5,245 | Retained separately |
| All live inference in this assignment | **158** | **446,842** | No replay/browser inference |

The experiment has 155 validated invocations/retained HTTP-200 receipts and one truncated failed
invocation with measured usage; its failed Pi receipt has no retained HTTP status. The two pilot
requests have successful production receipts. Main provider latency sums to 1,066,707 ms; wall
time above includes workflow overhead, not the pause for investigation. Currency cost is unknown:
no authoritative tariff or monetary receipt was available, and no cost was invented.

Main standing reservations total 1,843,827 conservative units; the pilot used 22,286, for an
actual combined 1,866,113 within the predeclared 2,000,000-unit / 180-request envelope. The resumed
harness conservatively reserved 60,000 units for the pilot rather than reclaiming them. Failed
invocations retained conservative Governor charges. No failed model inference was retried.

The truncated B response exposed a pre-existing lifecycle defect: failed explicit work returned
the common owner goal to `proposed`, blocking the next unattempted task with a 409. The interrupted
ledger retains that failure. The disposable harness reaccepted only its own preauthorized test
goal through the existing API and resumed unattempted cases; two later reference-validation
failures required the same recovery. There were no new user approvals or loosened dispatch gates.
The narrow product correction now preserves the accepted owner commitment on explicit procedure
failure while leaving the failed run terminal. Owner cancellation still blocks new work and
autonomous failure behavior remains unchanged. This correction is offline-tested, not claimed
as another live failure-injection acceptance run.

Restart/read/replay of **84** exchanges and duplicate application of all **12** feedback records
left provider requests **156→156**, reservations **1,843,827→1,843,827** and the exact policy hash
unchanged. No duplicate experiences, lesson versions or inference appeared. The same replay also
passed after the recovery correction. One focused browser scenario displayed actual retained
live output, provisional lessons and used IDs at desktop/mobile widths, with **zero API writes**.
The first browser attempt omitted session selection; its setup was corrected and the scenario
passed. No browser failure was hidden as an inference success.

## Validation and acceptance gates

Focused checks, run only for affected behavior:

- Integration preflight: two contextual regressions passed; exact approved-tree equality passed.
- Six adaptation tests passed across focused runs: verified reuse/scope/tamper/idempotency/demotion,
  executable oracle/false-confidence controls, held-out contamination, exact source capture-to-oracle,
  model/owner self-promotion rejection, and owner export withdrawal without quality counterevidence.
  Scripted transport is offline evidence only.
- Contextual snapshot/replay and full model-input/source binding checks passed.
- Explicit provider-failure/next-goal/cancellation regression and existing autonomous invalid-output
  regression: two passed in the isolated repair checkout before the exact commit was integrated.
- Dashboard: ten tests passed; final production build/type check passed.
- Browser: one focused retained-live adaptation scenario passed, desktop and mobile, no new inference.
- Changed Python files passed Ruff check/format; `git diff --check` passed.
- Full backend suite, full browser suite, Docker, heavy CI and independent rerun/review: **NOT_RUN**.

| Gate | Qualification | Boundary |
| --- | --- | --- |
| ADAPT-01 contextual integration | IMPLEMENTED, OFFLINE_TESTED | Present on branch via #93; main integration pending |
| ADAPT-02 durable experiences | LIVE_DEMONSTRATED | 12 linked training measurements |
| ADAPT-03 independent feedback | OFFLINE_TESTED, LIVE_DEMONSTRATED | Trusted executable fixtures, no self-ratings |
| ADAPT-04 model lesson proposals | LIVE_DEMONSTRATED | 10 structured; 2 absent proposals retained |
| ADAPT-05 qualified use | OFFLINE_TESTED, LIVE_DEMONSTRATED | Provisional provenance/export qualification, not proven utility |
| ADAPT-06 different conversation | LIVE_DEMONSTRATED | Exact supplied versions and model-reported used IDs |
| ADAPT-07 disclosure/authorization | OFFLINE_TESTED, LIVE_DEMONSTRATED | Public exports; broader private-source adversarial qualification NOT_RUN |
| ADAPT-08 idempotent durable state | OFFLINE_TESTED, LIVE_DEMONSTRATED | Exact state survives restart |
| ADAPT-09 revision/demotion | OFFLINE_TESTED | Controlled verified counterevidence; live causal demotion NOT_RUN |
| ADAPT-10 frozen splits | IMPLEMENTED, OFFLINE_TESTED | 12/6/12; one held-out label defect identified |
| ADAPT-11 same pinned model | LIVE_DEMONSTRATED | Same requested model/settings; internal provider identity unobserved |
| ADAPT-12 independent held-out grading | LIVE_DEMONSTRATED; FAILED for errors-4 label | Return oracle misses required mutation semantics; equal exclusion reported |
| ADAPT-13 gains/regressions retained | LIVE_DEMONSTRATED | Complete paired table, failures and repeats |
| ADAPT-14 full learning/transfer loop | LIVE_DEMONSTRATED | Functional loop, no positive-quality claim |
| ADAPT-15 usage/latency/cost | LIVE_DEMONSTRATED usage/latency | Currency unknown; no fabricated estimate |
| ADAPT-16 reuse architecture | IMPLEMENTED | Existing tables, workflows, transport and guards |
| ADAPT-17 no redispatch on replay | OFFLINE_TESTED, LIVE_DEMONSTRATED | 84 exchanges; 12 duplicate feedback applications |
| ADAPT-18 bounded conclusion | LIVE_DEMONSTRATED negative result | Improvement over stateless NOT ESTABLISHED |

No new code in this PR has the `INDEPENDENTLY_REVIEWED` qualification yet.

## Changed files

- `alive/adaptation/{contracts,service,oracle,__main__,__init__}.py`: typed predictions/proposals,
  event-backed experiences/versions, trusted public-fixture verification and owner-local tools.
- `alive/admission/{contracts,live,service}.py`: opt-in adaptive session, control arms, post-intent
  frozen selection, existing dispatch binding and contextual result projection.
- `alive/continuity/{contracts,service,adapters}.py`: bounded exported items, verified feedback,
  integrity/relevance references and existing contextual-role output contract.
- `alive/intent/contracts.py`: live family classification; `alive/capabilities/trusted.py`:
  include the actual adaptation code in contextual implementation custody.
- `alive/cognition.py`: preserve owner commitment after explicit run failure.
- `dashboard/src/admission/LivePane.tsx`: lesson/feedback/used-ID visibility, actual procedure
  separated from intent recommendation. `dashboard/e2e/adaptation-ai.spec.ts`: one read-only live
  history proof; [desktop](evidence/adaptation-ui-1440.png), [mobile](evidence/adaptation-ui-390.png)
  and [write/request audit](evidence/adaptation-ui-proof.json).
- `tests/test_adaptation.py`, `tests/test_live_admission.py`: focused adversarial/recovery coverage.
- `scripts/adaptation_demo.py`, `scripts/adaptation_report.py`: bounded experiment/replay and
  report-only comparison; resumption never repeats completed inference.
- `docs/intelligence/{AI-FIRST-03,AI-FIRST-03-REVIEW}.md`, frozen corpus/lock JSON and
  `evidence/adaptation-*`: predeclaration, provenance, all outcomes and qualification boundaries.

## Independent review targets

1. Check integration PR #93 separately, then review only the adaptation diff against its head.
2. Verify corpus/oracle hashes, original plan, all three arms and every failure in the ledger.
3. Inspect the owner export boundary, independent-measurement custody and idempotency conflicts.
4. Challenge family relevance, missed older lessons, unsupported generalization and negative transfer.
5. Reproduce replay against the retained disposable database without enabling new inference.
6. Independently review labels and prose before accepting broader quality claims. Use a new frozen
   held-out set for any prompt/retrieval revision; do not tune against and rerun this test panel.
