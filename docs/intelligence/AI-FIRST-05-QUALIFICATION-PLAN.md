# AI-FIRST-05 — Three-day qualification plan (not executed today)

This is a future execution plan, not qualification evidence. Implementation is OFFLINE_TESTED;
real-model smoke, quality comparisons, full CI/Docker/browser qualification and independent
review are NOT_RUN. No favorable outcome is assumed. Do not reuse or tune against the old
AI-FIRST-03/04 held-out tasks. Do not rerun the 533-call experiment.

Use the final reviewed AI-FIRST-05 commit, after resolving the two AI-FIRST-04 post-merge blockers
documented in [AI-FIRST-05.md](AI-FIRST-05.md). Record exact implementation/role/contract hashes,
protocol, source hashes and independent labels before opening fresh held-out tasks. Run only
against a new disposable database/workspace. Pin the same Meta contributor model for intent,
contextual, code-review and repair roles through production Pi; no mock substitution.

## Common commands and custody

From the implementation worktree, reuse installed/locked dependencies. In this installation,
use the existing interpreter with the worktree as the current directory; do not resync another
agent's shared editable environment while it is active:

```powershell
git status --short
git rev-parse HEAD
$taskPython = "C:\Projects\alive\.venv\Scripts\python.exe"
& $taskPython -m pytest -q -o addopts="" tests/test_task_review.py
npm --prefix dashboard test -- src/admission/live.test.tsx
```

Set `DATABASE_URL` and `ALIVE_WORKSPACE` to explicitly new disposable paths before installation
or server startup. Set `ALIVE_MODEL_TRANSPORT=pi`, `ALIVE_META_MODEL=muse-spark-1.3-contributor`
and verify role overrides select that same model. Credentials come from the owner's existing
environment; do not print, commit, or copy them into evidence. Disable autonomous background
model work and embeddings in this disposable run. Set the Pi runtime directory to the existing
verified installation if the new worktree has no installed Pi dependencies. Initialize only the
explicitly disposable database with the normal migrations, then start the existing app:

```powershell
& $taskPython -m alembic upgrade head
& $taskPython -m uvicorn alive.app:app --host 127.0.0.1 --port 8965
```

In a second shell with the same disposable database/workspace settings, after startup created
the instance, install the closed profiles:

```powershell
& $taskPython -m alive.admission install --profile contextual-reasoning
& $taskPython -m alive.admission install --profile code-review-v1
& $taskPython -m alive.admission install --profile code-review-repair-v1
```

Use the existing owner-local source-capture CLI (`python -m alive.sources --help`) to
capture/inspect/approve only vetted public fixture files for `intent.interpret`,
`repository.inspect`, `repository.analyze`, `context.reason`, `context.validate`. Create/accept
a disposable owner goal through the existing API. Enable the configured model through
`POST /api/v1/cognition/control` with `{"command":"enable_model","provider":"meta"}`.

Prepare a bounded standing session, with token/call/expiry limits recorded in the predeclaration:

```json
POST /api/v1/admissions/live/setup
{
  "goal_ref": "accepted-goal-id",
  "approval_ref": "exact-source-approval-id",
  "paths": ["README.md", "implementation.py"],
  "contextual": true,
  "adaptive": true,
  "code_review": true,
  "completion_repair": true,
  "max_calls": 30,
  "max_tokens": 400000,
  "ttl_seconds": 3600
}
```

Inspect the actual session with `uv run python -m alive.admission inspect-trust CONSENT`, then
`uv run python -m alive.admission trust CONSENT --confirm-sha256 EXACT-HASH`. These are examples
of finite ceilings, not authorization to start today. Pick phase-wide totals before execution
and account for every source session and intent/review/repair call; stop at the global ceiling.
Do not auto-increase a budget, change recipients/source classes or retry ambiguous dispatch.

Each independent turn starts a fresh `POST /api/v1/admissions/live/conversations` with that
consent. The goal API supports this request shape:

```json
POST /api/v1/admissions/live/ask
{
  "consent_ref": "consent-id",
  "conversation_ref": "fresh-conversation-id",
  "goal": "The frozen question, identical across matched conditions",
  "idempotency_key": "phase-task-arm-once",
  "strategy_mode": "stateless",
  "task_mode": "code_review",
  "task_case_ids": ["c1", "c2"],
  "repair_incomplete": false
}
```

Store the entire response and actual Pi receipts immediately, including blocked/failed calls.
`GET /api/v1/admissions/live/EXCHANGE` reads retained state. A request with the same key must
retain the same task/cases/repair flags; changing them is a conflict, not permission to retry.
Do not call a structurally complete answer verified. Map typed predicted values to an
independent verifier transparently; typed undetermined values stay unknown rather than wrong
or fabricated values. The existing oracle v2 can support vetted fixture execution, but the
new response format needs an explicitly reviewed projection; do not silently feed it as the
old contextual output or alter historical oracle semantics. Never execute model patches or
untrusted captured repositories for structural checks.

## Test day 1 — Contract reliability

Freeze a small fresh, independently labelled public task set (for example 8 development and
12 held-out tasks, including correct implementations, exceptions and caller-input effects).
Have an independent reviewer validate contracts/reference outputs and ambiguity before model
calls. Keep final held-out labels unavailable to prompt/retrieval development.

Compare, on identical source/question/memory settings:

1. `task_mode=general_contextual`, `strategy_mode=stateless`, no repair: existing broad v2 control.
2. `task_mode=code_review`, `strategy_mode=stateless`, `repair_incomplete=false`: first pass.
3. Same new contract, repair explicitly enabled: analyze first and repaired candidates separately.

For general mode omit `task_case_ids` and `repair_incomplete`; named cases are still visible in
the identical README. Keep declared cases/output limits/model equal and seeded arm order frozen.
Do not add extra inference to a baseline or hide the repair call in the new condition's count.

Measure transport/schema validity, first-pass task completeness, omission/duplicate/fabricated
ID rates, typed unknown rate, semantic correctness including input mutation, reference integrity,
measured tokens/latency and repair acceptance/refusal/cost. Keep raw candidates and parent IDs.
Report correctness conditional on supplied predictions separately from end-to-end success;
unknowns can be complete structure but cannot earn full semantic success.

Criteria: wiring gates hold; no accepted field changes in repair; at most one extra dispatch;
honest per-task comparisons and uncertainty. A structural gain is not a semantic gain. More
calls/cost without benefit, regressions and no improvement are acceptable findings. Diagnose on
development only; any change to prompts/limits/contracts requires a new frozen held-out set.

## Test day 2 — Memory interference

Hold the reviewed code-review contract, model, source access, output limits and repair policy
fixed. Use fresh independent conversations. Compare no memory, one relevant approved lesson,
one irrelevant approved lesson (controlled owner-local evaluation intervention), and unchanged
selective adaptation. Use existing `selection.evaluation_override` only in a labelled local
evaluation process, never as an HTTP authority bypass; unauthorized items must remain excluded.

Include self-contained tasks where memory is unnecessary and tasks requiring a retained project
fact unavailable from the current source alone. Verify that the latter actually lose essential
information when history is removed. Freeze the lesson policy; held-out outcomes cannot train it.
Record exact selection refs/versions/item hashes and distinguish supplied, reported-used and
causally helpful evidence. Use matched interventions for causal claims, not retrieval counts.

Measure structural completion and semantic correctness separately; record irrelevant-memory
interference, abstention/no-lesson decisions and all negative transfer. Do not introduce a new
ranking/relevance call during this comparison. If the AI-FIRST-04 metadata or paired-feedback
blockers remain, mark this phase blocked/NOT_RUN rather than qualifying those boundaries.

## Test day 3 — Integration and independent review

Run the appropriate broader focused regressions on the final reviewed head:

```powershell
uv run pytest -q -o addopts="" tests/test_task_review.py tests/test_contextual_continuity.py tests/test_live_admission.py tests/test_selective_adaptation.py
npm --prefix dashboard test -- src/admission/live.test.tsx
npm --prefix dashboard run build
```

Add separately reviewed real-browser scenarios for opted-in complete/incomplete/repaired output,
disabled repair, refused overwrite, model failure, source/consent withdrawal during dispatch and
replay after restart. A read-only screenshot is insufficient evidence of actual repair inference.
Verify original and repair receipt IDs, model/endpoint/source equality, raw candidates and zero
new requests/feedback changes on replay. Challenge malformed JSON, whitespace-only unknown reasons,
version/hash tampering, duplicated/extraneous cases, fake references and concurrent duplicate POSTs.

Independently inspect the two AI-FIRST-04 guard fixes and their adversarial regressions. Confirm
that no foreign candidate metadata is projected and no non-stateless/wrong-source/owner/model
measurement can create paired utility. Check ordinary contextual mode and selective eligibility,
explicit none decisions, withdrawals and hashes remain compatible.

Let normal CI run broader qualification when requested; do not duplicate full CI locally by
default. Full backend, Docker and all-browser qualification require an explicitly scheduled tier,
not a default daily loop. Preserve jobs and owner processes; no speculative timeout changes.

The independent report should classify the outcome as structural gain, semantic gain, reduced
memory interference, higher cost without benefit, regression or no demonstrated improvement.
Publish measured denominators, all failures, labels/limitations, exact SHAs and qualification
states. Deployment readiness is a separate decision; do not merge automatically.
