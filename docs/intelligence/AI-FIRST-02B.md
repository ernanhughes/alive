# AI-FIRST-02B implementation note

Base: PR #91 implementation `536b910`, pending its merge. This work is stacked on that branch.

Use existing events for conversation membership and frozen context snapshots; existing admission,
Cognition, Governor, source custody, Pi and `result.record` remain the execution path. Retained
workflow artifacts are the authoritative prior findings. General `Memory`/MiniLM retrieval and
goal-scoped research memory were inspected: neither directly provides this conversation's exact
owner/source-disclosure boundary, so the first slice reads bounded, explicitly linked artifacts
rather than disclosing general memory or adding a second evidence store.

An opt-in standing session adds one concrete read-only contextual reasoning procedure. Initial
questions keep the existing interpretation/analysis path. Subsequent turns receive a frozen,
bounded selection of prior goals, findings and revisions from that conversation only. The model
resolves natural/ambiguous references and distinguishes owner assertions from source observations
and unverified model assessments. Revision outputs link earlier item IDs without overwriting them.
Snapshots are hashed, charged and revalidated at admission and Pi dispatch. New conversation
means no inherited history. Legacy exchanges remain readable and unchanged.

## Implementation and disclosure

The conversation is an instance/owner/source/consent-scoped `conversation.opened` event.
`conversation.exchange` events link existing admissions; they do not duplicate the report store.
`conversation.snapshot` freezes selected excerpts, IDs, content/artifact hashes, timestamps,
finding ordinals, verification labels and bounded omissions. Candidate retrieval uses recent
20 linked admissions plus foundational results and explicit parent-ID references. Explicit
findings and the latest revision have priority. The model resolves semantic relevance and
returns the item IDs actually used; the candidate window is not an assertion that every item
is relevant. No general Memory/history-import retrieval is disclosed.

Maximum context: eight items and 6,000 UTF-8 JSON bytes, including a bounded omission inventory.
Essential explicit references/current revisions that cannot fit fail visibly. Source and prompt
bytes also pass the existing Governor request/investigation ceilings. Frozen context and the
complete model-input digest are declared workflow inputs, included in reviewed disclosure,
charged conservatively and checked again at Pi dispatch. A self-consistent hash on a forged
invocation body cannot substitute new source or recalled bytes.

The concrete `context.reason` / `context.validate` procedure reuses Cognition, ModelGateway,
production Pi, source custody, the workflow runner and `result.record`. It adds no provider,
orchestration engine, schema migration or new authorization store. The validator checks item
identity and source citations; it does **not** verify semantic correctness. Owner statements,
model assessments and source observations retain distinct provenance. A revision references
superseded recalled assessments; originals remain immutable and readable.

Contextual disclosure is opt-in (`LiveSetup.contextual=true`). Initial source approval names
`context.reason` and `context.validate` alongside the existing operations; one standing consent
then covers routine turns. Old standing grants are not silently widened. A conversation is
currently pinned to that consent and exact capture; consent renewal across conversations and
multiple source versions are outside this slice. Revoked/expired scopes reject new inference;
history remains readable. ALIVE proposes fixes but cannot edit or execute repository code.

The Ask ALIVE surface resumes an existing conversation, supports a clean new conversation,
renders substantive answers/revisions and keeps provenance details secondary. Lost-response
retry preserves both conversation and request identity.

## Recorded live behavior — 1 November 2026

Qualified application implementation: `477a30e` (clean main run), stacked on `536b910`.
Later changes strengthen tests, the browser driver and evidence documentation; application code
is unchanged. Requested model: `muse-spark-1.3-contributor`; endpoint:
`https://api.meta.ai/v1/chat/completions`. Provider-observed internal model identity is not
independently attested.

The main conversation performed initial investigation, explanation, minimal fix, zero-value
correction, signed/empty-input reassessment, summary and an additional contextual question after
backend restart. Actual recalled IDs and frozen context hashes link the answers to earlier
findings/revisions. The final after-restart answer distinguished zero sums, negative sums and
the unresolved empty-input contract. Seven completed requests replayed after restart without
dispatch (**7 → 7**); reopening after the evaluation again stayed **18 → 18**.

A separate Chrome session submitted four normal Ask ALIVE turns (investigate, explain, fix,
correct), using one initial consent and no repeated approval commands. Four POSTs produced five
provider calls. Reload and backend restart/replay stayed **5 → 5**. The first browser attempt
failed on an exact-label locator before inference; using the observed combobox role fixed the
test. No timeouts, polling thresholds or assertions were weakened.

| Run | Calls | Measured tokens | Summed invocation latency |
| --- | ---: | ---: | ---: |
| Main conversation + eight evaluation cases + two matched controls | 18 | 52,784 | 93.434 s |
| Four-turn browser conversation | 5 | 12,589 | 28.773 s |
| Total | 23 | 65,373 | 122.207 s |

Median invocation latency: 4.862 s. These are invocation timings, not wall-clock test duration.
Each disposable session was limited to 24 calls / 200,000 conservative reserved tokens. The
main session charged 198,759 conservative reservations, so the UI demonstration used a separate
initial bounded consent rather than modifying or bypassing the nearly exhausted allowance.
Actual currency cost is unknown and not estimated.

## Evaluation and limitations

The [eight-case panel](contextual-evaluation-cases.json) was frozen before inference. Its digest
is retained in the [evidence ledger](AI-FIRST-02B-evidence.json). It includes two follow-ups,
zero/negative corrections, ambiguous/irrelevant references, misleading owner feedback and a
source-instruction attack. Both matched context-free controls used the same role, model, source
and goal with an empty conversation snapshot.

All eight contextual answers addressed the requested task and used valid supplied item IDs.
The model accepted the valid zero counterexample, reasoned correctly about `[-2,-4]`, declined
to invent deployment/payroll findings, rejected the misleading correction and ignored source
instructions. Two answers stated an empty-input policy more strongly than the source warrants;
those grounding judgments are **PARTIAL**, not counted as fully grounded wins.

Negative results are preserved: early main/browser answers overgeneralized “too small”; the
first zero revision did not fix sign-sensitive wording until the next reassessment. The browser
correction also used imprecise “non-zero inputs” wording despite correctly mentioning zero sums.
The context-free cause answer falsely claimed `0/1` raises `ZeroDivisionError` and overgeneralized
error direction. The context-free revision answer correctly admitted it could not identify an
earlier claim. This is useful paired evidence, not a general performance estimate.

Judgments were made by the implementation agent against predeclared arithmetic expectations,
not by model self-confidence or an independent PR reviewer. No executed tests or source edits
were invented as ALIVE outcomes. Citation existence is not semantic truth. This slice demonstrates
recall, contextual reasoning and revision; it does not establish generalized learning,
autonomous improvement, broad adversarial readiness or release qualification.

## Reproduce locally

Use a new disposable directory, configured Meta credential and pinned Pi install. Review the
public toy `SOURCE`, goals and limits in the driver before passing the approval flag:

```powershell
uv run python -m scripts.contextual_demo --output C:/Temp/alive-contextual-new --approve-live
uv run python -m scripts.contextual_demo --output C:/Temp/alive-contextual-new --verify-history
```

The driver pins role models, creates a disposable SQLite database/workspace, seeds only the
public source, installs the shipped procedures, records one bounded consent and writes the full
ledger. No mock/injected provider is used. Run replay verification while the standing consent
is valid; expired consent still permits history reads but blocks new inference/replay POSTs.

For the browser scenario, create a separate empty runtime with `--setup-only`, then serve its
database/workspace with the same pinned model, empty role overrides and `ALIVE_MODEL_TRANSPORT=pi`.
Include the exact localhost origin in `ALIVE_ALLOWED_ORIGINS`. Set the disposable server's
`ALIVE_BASE_URL`, `ALIVE_API_TOKEN` and:

```powershell
$env:ALIVE_CONTEXT_LEDGER = 'C:/Temp/alive-contextual-browser-new/contextual-ledger.json'
cd dashboard
npx playwright test e2e/contextual-ai.spec.ts
```

Stop that disposable server before `--verify-history`. Never point qualification at your normal
database. [Desktop](validation/contextual-1440.png) and [mobile](validation/contextual-390.png)
screenshots show the actual browser run.

## Focused verification and acceptance

Fourteen contextual backend scenarios passed across focused runs, plus nine capability-registry
checks and one existing three-goal admission regression. The context tests cover changed context
changing the answer, explicit older/similar findings, new-conversation isolation, owner/instance/
source boundaries, expiry/revocation/wrong destination/model, unrelated-memory exclusion, budget
failure, snapshot tampering and forged model inputs at Pi dispatch. Ten dashboard tests and the
production build passed; changed-file Ruff/format and `git diff --check` passed. Only the single
new browser scenario ran. No full backend suite, broad E2E campaign, Docker or CI/workflow change.

```text
uv run pytest -q -o addopts="" tests/test_contextual_continuity.py
uv run pytest -q -o addopts="" tests/test_live_admission.py::test_three_goals_one_consent_real_dispatch_path_and_retained_results tests/test_capability_registry.py
npm --prefix dashboard test -- src/admission/live.test.tsx
npm --prefix dashboard run build
```

| Gate | Status | Evidence boundary |
| --- | --- | --- |
| CTX-01 durable conversation links | LIVE_DEMONSTRATED | Main/browser histories persist |
| CTX-02 prior finding resolution | LIVE_DEMONSTRATED | Recalled IDs; older/similar cases also offline |
| CTX-03 bounded, traceable, authorized context | LIVE_DEMONSTRATED | Exact snapshots/input hashes; boundary attacks offline |
| CTX-04 real model receives context | LIVE_DEMONSTRATED | Production Pi receipts linked to frozen input |
| CTX-05 substantive follow-up answer | LIVE_DEMONSTRATED | Explanation and minimal fix |
| CTX-06 evidence-based revision | LIVE_DEMONSTRATED | Valid correction accepted; misleading correction rejected |
| CTX-07 original/revised distinction | LIVE_DEMONSTRATED | Immutable artifacts and superseded item IDs |
| CTX-08 subsequent revised understanding | LIVE_DEMONSTRATED | Summary and after-restart answer |
| CTX-09 restart persistence | LIVE_DEMONSTRATED | Exact retained exchanges/context compare |
| CTX-10 no completed-request redispatch | LIVE_DEMONSTRATED | 7→7, 18→18 and 5→5 |
| CTX-11 unauthorized context exclusion | OFFLINE_TESTED | Adversarial scope tests; live injection is one narrow case |
| CTX-12 live Pi contextual path | LIVE_DEMONSTRATED | 23 measured requests across both runs |
| CTX-13 negative results retained | LIVE_DEMONSTRATED | Incorrect/interim/control claims remain in ledger |
| CTX-14 no new generic framework | IMPLEMENTED | Existing workflow/custody/Governor/Pi infrastructure reused |

No new gate is labelled `INDEPENDENTLY_REVIEWED`. Keep the PR draft and unmerged for that review.
