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

## Independent review targets

1. Check integration PR #93 separately, then review only the adaptation diff against its head.
2. Verify corpus/oracle hashes, original plan, all three arms and every failure in the ledger.
3. Inspect the owner export boundary, independent-measurement custody and idempotency conflicts.
4. Challenge family relevance, missed older lessons, unsupported generalization and negative transfer.
5. Reproduce replay against the retained disposable database without enabling new inference.
6. Independently review labels and prose before accepting broader quality claims. Use a new frozen
   held-out set for any prompt/retrieval revision; do not tune against and rerun this test panel.
