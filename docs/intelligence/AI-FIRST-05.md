# AI-FIRST-05 — Task-contract reliability

Status: **IMPLEMENTED / OFFLINE_TESTED**; not yet independently qualified.
Real-model smoke: **NOT_RUN**. Independent qualification, empirical improvement, full CI,
Docker and broad browser/benchmark qualification: **NOT_RUN**. This is implementation, not a
claim that intelligence or accuracy improved.

## Baseline and isolation

GitHub recheck found #96 merged at 22:13:10 UTC on 1 November 2026. This work therefore branches
from main `06b4b7148678a8357351625cda9eceaba48af662`, rather than stacking on its former branch.
Worktree: `C:\Projects\alive-ai-first-05`; branch: `ai-first-05-task-contracts`; PR target: main.
The original checkout, experiments, databases and background processes were not modified.
Existing installed dependencies are reused. No dependencies, CI settings or timeouts changed.
Implementation/test commit: `db0f853e5a170d5808dfdde3f3a00583e21500e5`; the handoff documentation
is committed separately after those checks.

AI-FIRST-04's contextual instructions, schema, role contract, intent contract, selection policy,
oracle versions, corpora and evaluation artifacts are untouched. The contextual role digest is
still `26abfc77d3f5e32a533ef4a07c5d8ad5790733bcec9e3846fdab403205b3579a`.

## Small, explicit contracts

The existing default is `task_mode: general_contextual`. `task_mode: code_review` explicitly
selects a new, separately consented `code-review-v1` admission profile. Nothing automatically
switches normal conversations to this schema. The new profiles derive the existing closed
reason → validate → record workflow; they do not add a runner, model client, persistence engine,
tool power, selector or generic contract compiler. They are not added to the intent catalogue,
so the catalogue presented to the existing intent model is unchanged.

Existing intent/continuity/selective context assembly happens first. Then the server freezes a
task request over that exact selected context. The contract contains task identity and objective,
version and digest, source/capture/approval/scoped hashes, file hashes, declared case IDs, required
outputs, uncertainty rules, verification requirements and completion requirements. It is included
in the complete model-input digest, which the existing grant, Cognition/Pi dispatch fence and
source custody recheck. Candidate metadata does not grant authority.

The new role `code_reviewer` uses a compact response schema:

```json
{
  "contract_version": 1,
  "contract_sha256": "the exact supplied task digest",
  "explanation": "A concise explanation, at most 1800 characters",
  "predictions": [{
    "case_id": "c1",
    "observed": {"status": "predicted", "value": "2"},
    "required": {"status": "undetermined", "reason": "The contract omits empty-input behavior"}
  }],
  "defect": {"status": "undetermined", "reason": "The required behavior is not established"},
  "citations": [],
  "reference_ids": []
}
```

A definite defect decision is `{"status":"determined","issue_present":true}` (or false).
There is no missing/null/guessed boolean default. Known values use JSON-encoded strings or
`ERROR:ExceptionName`; unknown values require the separate typed state and a nonblank reason.
The same distinction applies independently to observed and required behavior. Structurally
complete unknowns remain unresolved; they are not full semantic success.

Cases come from explicit bounded `task_case_ids` (maximum eight distinct nonempty IDs of at most
40 characters), or from the approved README convention `Named input cases: [{"id":"c1",...}]`.
Malformed/duplicate declarations fail visibly. Other natural-language case formats are not
silently inferred: the owner supplies explicit IDs. With no declared cases the contract requires
an empty predictions list and an explicit defect decision/uncertainty; it does not invent cases.

## Completion is not semantic verification

The pure validator runs in the existing restricted read-capability context: it has captured
source data, not database/kernel access or execution tools. It deterministically checks required
fields/types, contract version/hash, valid value/unknown representations, every declared case
exactly once, missing/duplicate/unexpected IDs, supplied memory-reference identities and citation
existence. Definite source judgments require a source citation. Quotes/locators are checked for
existence only. No captured code is executed and no model judge is called.

The retained result records separate properties:

| Property | Meaning |
| --- | --- |
| `transport_completed` | A bounded provider response reached the role parser |
| `response_schema_valid` | Original review / repair response matches its declared schema |
| `schema_valid` | Effective review candidate matches the review schema |
| `completion.task_complete` | Its actual task-specific structure and references are complete |
| `completion.all_cases_addressed` | All declared cases have the required typed parts |
| `completion.contains_undetermined` | At least one value/decision explicitly remains unknown |
| `semantically_verified` | Always false here; needs an independent checker outside this gate |

For example, a schema-valid review with one missing case is incomplete; an entirely complete
but wrong prediction remains unverified. Provider/ModelInvocation envelope validation does not
mean the candidate's schema or task contract passed.

The parser retains raw text and the parsed candidate even when JSON/schema/completeness fails.
Invalid JSON is retained verbatim with a null parsed candidate and explicit invalidity. The
result artifact retains accepted case parts, all omissions/unsupported references, completion
diagnostics, candidate identity, source/context/task hashes and original invocation/receipts.
Existing valid predictions survive; no missing value is filled deterministically. A fallback
display message explicitly says the response is incomplete; it is not an invented AI answer.

## Optional, one-attempt repair

Repair is **disabled by default**. It needs both a standing session prepared with
`completion_repair: true` and a task request with `repair_incomplete: true`. The setup must also
enable `code_review`; repair cannot be enabled by changing a replay payload. An already complete
answer, including a properly typed undetermined answer, never triggers repair.

An incomplete response can invoke the separately receipted `code-review-repair-v1` profile and
`code_review_repairer` role once. Its configured model/provider/endpoint must exactly match the
review profile at setup. It reuses the same approved source, conversation and selected items;
no new relevance call or memory selection runs. The frozen repair binds the original admission,
artifact digest, raw text, candidate ID, exact candidate and deterministic errors/allowed fields.
Changing candidate data, context, scope or original identity refuses dispatch.

The model returns only:

```json
{
  "contract_sha256": "the same task digest",
  "original_sha256": "the exact original candidate identity",
  "changes": {"predictions": ["replacement structured case entries"]}
}
```

Changes may touch only missing/malformed top-level fields named by the gate. Accepted original
leaves are locked: explanation, defect decision, valid case values/unknowns and valid reference
entries must survive exactly. For a partially valid predictions array, the patch may repeat its
accepted members verbatim and add/fix missing parts; it cannot change their meaning. This uses
an explicit small patch model rather than a generic JSON-patch/compiler system. Extraneous
top-level fields may be removed by setting those fields to null. It never repairs a structurally
valid prediction merely because it might be wrong.

Both candidate versions, raw repair and receipts remain auditable. A valid partial patch can
produce a new still-incomplete candidate; there is no second repair. An identity/overwrite
violation refuses adoption and leaves the original effective. Transport failure, insufficient
consent, size ceiling or budget exhaustion also preserve the original and failed/blocked repair.
The existing idempotent admission/stage identities prevent redispatch on retry or restart.

Every dispatched repair counts separately, with usage and receipt retained. Rejection at the
actual dispatch fence counts zero extra provider calls, even if a workflow reservation exists.
The count uses Pi's durable dispatch marker; ambiguous attempts remain charged/count conservatively
and are never retried. An incomplete original remains available even if repair fails.

Limits remain the existing one-call/1536-output-token profile and Governor/standing envelopes.
Selected memory keeps its existing 6KB ceiling. Task snapshots are at most 18KB and assembled
task data at most 24KB, additionally subject to capability and Governor byte/token ceilings.
Those bounds can refuse repair for a larger candidate; the code never raises budgets or asks
for further automatic approval to work around a refusal.

## Product and owner setup

Install the new closed workflow definitions through the existing owner-local mechanism:

```powershell
uv run python -m alive.admission install --profile code-review-v1
uv run python -m alive.admission install --profile code-review-repair-v1
```

The existing Ask ALIVE setup accepts `code_review: true` and optional `completion_repair: true`.
Inspect and approve its exact standing hash once using the existing CLI. Older sessions cannot
authorize the new roles. Existing source approvals need the same `context.reason` and
`context.validate` operations, not new execution permissions. Normal deployment implementation
hash checks still apply; historical grants are not rewritten to approve new code.

Ask ALIVE adds a small response-contract selector, optional case-ID input and repair checkbox.
Its completion panel separates transport/schema, case coverage, task completeness, undetermined
outcomes, independent verification and repair/call status. Original candidate and repair evidence
remain inspectable. Request retry identity includes the task/cases/repair choice. Normal
conversation and selective-adaptation displays remain available.

## Outstanding AI-FIRST-04 post-merge blockers

Both prior review concerns remain unresolved in merged #96 head `06b4b71`; this PR deliberately
does not redesign or silently fix the selector/feedback mechanism:

1. **Candidate metadata before authorization filtering.** `adaptation.selection.choose` builds
   all candidate IDs, families, mechanisms, utility and supporting outcomes, marking foreign-owner
   or foreign-destination lessons with exclusion reasons. It persists that metadata and `view`
   exposes candidates. Not sending their strategy text to the model is insufficient protection
   for private metadata. The existing scope test even expects those excluded IDs in the view.
   A separate fix must filter/redact before projecting/support lookup, with a regression proving
   no foreign lesson metadata reaches the selection view or model input.
2. **Insufficient paired-feedback binding.** `record_application` checks the primary measurement
   marker/instance/admission ID and the baseline task/split/different admission. It does not
   sufficiently revalidate source/artifact, principal, model/destination or true stateless
   baseline identity; the baseline's instance is not checked there either. A separate micro-fix
   needs same-task/source/owner/model/corpus/verifier binding and a verified stateless snapshot,
   plus forged/mismatched baseline regressions. A trusted measurement is not automatically a
   valid paired comparator.

These are **post-merge blockers for combined release/independent qualification**, not fixed or
qualified by the task-contract tests. AI-FIRST-05 does not apply learning feedback or modify
lesson utility/ranking. Its own contract/repair source and candidate binding is checked separately.

## Files and focused handoff

- `alive/task_review/contracts.py`: small typed response/unknown/patch models and role specs.
- `validation.py`: deterministic completion and accepted-content preservation.
- `service.py`: task/snapshot/repair custody and Pi input binding; no new tables/events engine.
- `adapters.py`: read-only validation/artifact projection. The existing contextual reasoning
  adapter makes the Cognition call for both contracts, avoiding a duplicate transport path.
- Admission profiles/contracts/live/service, contextual adapters/history and runner bindings:
  opt-in wiring to the existing execution path, consent and provenance projections.
- `capabilities/trusted.py`: include the new implementation files in existing closure custody.
- `LivePane.tsx` and its focused test: compact selection/completion UI.
- `tests/test_task_review.py`: scripted contract, repair, source, budget, dispatch and restart checks.

Run only focused commands today. See [the three-day qualification plan](AI-FIRST-05-QUALIFICATION-PLAN.md)
for the deliberately deferred real-model and independent work. No dataset, historical ledger,
oracle or AI-FIRST-04 experiment was rewritten or rerun.

Focused results on this implementation:

- **32 task-contract checks passed across focused runs**: required fields/cases/types,
  unknowns, references, exact version/hash, accepted-leaf locking, invalid JSON retention,
  successful/disabled/refused/failed repair, completed first pass, budget/model/source fences,
  request conflicts, restart/replay, source-declaration parsing and unchanged general identity.
  One new assertion initially expected `abstained` from an empty store with a known family;
  the unchanged selector correctly returns `none/no_lessons_available`. That test expectation
  was corrected and its complete repair/replay/general-conversation scenario rerun successfully.
- Existing contextual snapshot/revision/replay and explicit no-lesson/selective-prompt regressions
  passed. These are scripted infrastructure checks, not intelligence-quality evidence.
- **14 dashboard tests passed** and production build/type checking passed.
- Changed Python files passed Ruff check/format; `git diff --check` passed.
- Existing v2 role/policy/oracle/corpus/evidence files remained byte-unmodified in the diff.
- All test databases/workspaces were disposable. No live provider calls, benchmark run,
  independent review, full backend/browser suite, full CI or Docker qualification was performed.

The implementation environment used the existing interpreter
`C:\Projects\alive\.venv\Scripts\python.exe` from this worktree, with `-m pytest -q -o addopts=""`
and explicit file/node selectors. It did not reinstall or redirect the shared editable package.
An ignored dashboard dependency junction reused the already installed node modules.
