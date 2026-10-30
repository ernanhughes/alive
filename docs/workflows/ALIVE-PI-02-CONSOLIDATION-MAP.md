# ALIVE-PI-02: consolidation map (non-executable)

This is analysis, not a plan of record and not a refactor. **PI-02A deletes, moves and migrates
nothing.** It records where ALIVE already has two ways of doing one thing, so a later, separately
authorised change can replace duplicated paths with the workflow model **without** losing behaviour
or evidence. Each row says what must survive, what protects it, what data would move, where a safe
cut exists, and what could go wrong.

Rules for any future consolidation (all rows): the old path is removed only after the new path passes
the old path's tests unchanged; frozen evaluation evidence and archived experiments are never
rewritten or re-keyed; historical rows are migrated by *adding* references, not editing them; and each
step is its own independently reviewed PR.

| # | Overlap | Behaviour that must be retained | Tests that establish it | Data requiring migration | Safe replacement boundary | Risks |
| --- | --- | --- | --- | --- | --- | --- |
| 1 | **Cognition orchestration** (`Cognition.execute`: observe -> propose -> critique -> evaluate, with budgets and settlement) vs **workflow stages** | The role order and gating (`use_critic`); reservation before every model call; settlement of every reservation on completion, failure and cancellation (the F-002 invariant); abstention when evidence is missing; the exact prompts and request bodies | `test_cognition.py`, `test_recovery_budgets.py`, `test_model_gateway.py` golden-request and ratchet tests | None for new runs. Existing `investigations` rows stay as they are; a workflow run may *reference* one (`investigation_id`) | Re-express the stage sequence as a definition whose operations are the existing methods (`world_state`, `call_role`, `validate_references`, `evaluate`); keep `Investigation` as the record of the run until its readers move | The F-002 class of bug lives exactly here (cancellation between reservation and settlement). Do not change the sequence and the executor in one step. Frozen experiments call these paths |
| 2 | **Experiment scheduling** (`experiment/service.py`, `experiment_budget.py`) vs workflows | The frozen ALIVE-03/14 protocols byte-for-byte: corpus, policy, prompts, evaluator, spending guard; owner authorisation before unsealing; no retries | `test_experiment03.py`, `test_alive14*`, `test_experiment_budget.py`, archive verifiers in CI | None. Frozen evidence is never re-keyed | **Leave alone** until a workflow can reproduce a frozen campaign's exact request bytes. At most, a *new* campaign type could be a workflow | Highest risk of invalidating evidence. The guard overlay exists because the frozen runner could not be changed |
| 3 | **Invocation tracking** (`model_invocations`, `agent_runs`) vs **Pi receipts** (`pi_runs`, PR #66) vs `workflow_stage_runs` | One authoritative record of what was requested, dispatched and settled per model call; unknown usage stays unknown, never zero; ambiguous dispatch is never replayed | `test_recovery_budgets.py`, PR #66's Pi suites | Link, do not merge: stage rows carry `model_invocation_id` and `pi_run_id`. No data moves | The Pi receipt remains authoritative for provider detail; the Governor's `model_invocations` remain authoritative for spend. A stage record is a *join*, never a third accounting | Re-deriving spend in the workflow layer would create two ledgers that can disagree |
| 4 | **Research task execution** (`research_memory`, `research_relationships`, `research_blind`, `claim_comparison`) vs workflow stages | Provenance of every claim; blind-evaluation separation; evidence qualification rules; no paid calls without authorisation | `test_research_*.py`, `test_evidence_qualification.py`, `test_notebook*` | None initially. Operations are *bound*, not rewritten | Wrap each research capability as a workflow operation one at a time, behind its existing tests | Large (about 2,100 lines in one file). A wrapper that changes arguments or ordering alters research results silently |
| 5 | **Capability declarations**: Skill Forge `SAFE_OPERATIONS` and `extensions/` specimens vs future Pi skills/extensions (PI-03) | Closed operation set; owner grants; Governor checks; a model cannot register handlers; skills are never loaded as unconstrained instructions | `test_skill_forge_p0.py` | Existing manifests: none migrate until an adapter exists. They remain valid as-is | PI-03 designs one capability reference (a library entry resolved by policy). Skill Forge becomes either an adapter into it or a retired parallel format, decided then | Two manifest formats drifting apart; or a rushed merge that widens what a skill may do |
| 6 | **Event history** (`events`) vs workflow traces | Append-only, ordered, with correlation ids; `source` identifies the producer; replay reads events | many (`test_runtime.py`, kernel tests) | None: workflow events already use `events` with `source="workflow"` | Nothing to consolidate; this is the pattern to keep. A separate trace table must **not** be introduced | Building one would fork the history readers |
| 7 | **Approvals** (`experiment_approval.py`) vs a workflow `approval_gate` | An approval is explicit, scoped, revocable and recorded; a stage cannot approve itself | `test_experiment_approval*`, `test_demo*` | None | Generalise the approval record only when a second use exists; until then `approval.request` stays unavailable | A generic gate that is easier to satisfy than the specific one would weaken it |
| 8 | **Docker/entrypoint seeding** vs startup seeding | Migrate before serve; seed never destroys data; healthcheck | `test_docker_config.py`, Docker E2E | None | Keep builtin seeding in application startup (it needs the kernel lock); leave the entrypoint as is | Seeding in two places invites divergence |
| 9 | **Hugo notebook output** vs run history | Static, public-safe pages; the notebook is not a database | `test_notebook*` | None | A future export renders a finished run to a page from stored hashes and references | Treating generated pages as the source of truth |

## What PI-02A already does to make this easier

* One vocabulary (`operations.py`) names the existing functions that a consolidated workflow would
  call, and a test proves each still exists. Renaming or removing one breaks that test, so drift is
  caught early.
* Definitions are data with a canonical hash, so "the old orchestration and the new one run the same
  stages" becomes a checkable statement.
* Runs and stage records reference existing ids instead of copying them, so nothing needs
  re-keying later.

## Not proposed

Deleting `Investigation`, merging `agent_runs` into anything, replacing the frozen experiment runner,
or removing Skill Forge. Each needs its own evidence and review.
