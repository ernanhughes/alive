# ALIVE-PI-02A: workflow foundation

Status: draft for independent review. PI-02A defines, stores and **shows** workflows. It does **not**
execute them: no scheduler, no Pi process, no model call, no write endpoint. Execution is PI-02B and
needs the PI-01B Pi runtime (PR #66, merged) to pass its independent re-review first.

Base: `main`, after PR #66 (PI-01B) merged. PI-02A itself uses no code or table from it.

## 1. What is added

| Piece | Where |
| --- | --- |
| Strict, versioned definition schema, DAG/reference validation, canonical form and hash | `alive/workflows/spec.py` |
| The **closed** operation set, each bound to existing ALIVE code or marked unavailable | `alive/workflows/operations.py` |
| Run / stage state machines | `alive/workflows/states.py` |
| Three tables and immutability guards | `alive/workflows/models.py`, migration `0008_workflows.py` |
| Registration (trusted path), lifecycle, run and stage *records*, reads | `alive/workflows/store.py` |
| Read-only, authenticated inspection API | `alive/workflows/api.py` |
| One shipped example definition | `alive/workflows/builtin/research-review.v1.json` |

Wiring in `alive/app.py` is three lines: import, seed at startup, `include_router`.

## 2. Inventory and reuse-versus-replace matrix

Every row was read from the repository at `8da23b4`. "Duplicate?" asks whether a workflow abstraction
would re-create something that already exists.

| Component | Responsibility today | Interface / records | Protected by | PI-02 decision | Duplicate? |
| --- | --- | --- | --- | --- | --- |
| Cognition (`alive/cognition.py`) | Runs one **Investigation**: observer, proposer, optional critic, evaluator; budgets; settlement | `Cognition.execute`, `call_role`, `world_state`, `finish`; tables `investigations`, `model_invocations`, `cognitive_*` | `test_cognition.py`, `test_recovery_budgets.py` | **Reuse and leave alone.** Its stage sequence is the model for a workflow; four of its functions are bound as operations. Consolidation is future work (map in the companion document) | This *is* an orchestration; the workflow must not run beside it. PI-02B must call into it or replace it deliberately, never wrap it |
| ModelGateway (`alive/model_gateway.py`) | The single audited seam for model calls (`cognition.role` only) | `StructuredRequest`, `gateway_for` | `test_model_gateway.py` ratchets | **Reuse.** `cognition.role` is the only `pi_agent` operation; no new provider client | A second dispatch path would break the ratchet |
| Agent / Pi runs (`alive/agents.py`, `agent_runs`) | Older agent runner records | `Agents`, table `agent_runs` | `test_agents*` | **Leave alone.** The PI-01B run lifecycle (`pi_runs`, PR #66) is on `main`; a stage stores `pi_run_id` as a plain id until PI-02B adds the foreign key | Do not model Pi receipts again; reference them |
| Research (`research_memory.py`, `research_relationships.py`, `research_blind.py`, `claim_comparison.py`, `exploration_api.py`) | Research capture, relationships, blind evaluation, claim comparison | Services under `app.state`; tables in `web_experiences`, `memories` | `test_research_*`, `test_notebook*` | **Leave alone.** Future workflow operations, not rewritten here | Not duplicated; nothing new is built |
| Evidence (`evidence_qualification.py`, `society.validate_references`/`evaluate`) | Qualify and validate evidence | `EvidenceQualifier.qualify`, functions | `test_evidence_qualification.py`, `test_cognition.py` | **Reuse.** Bound as `validation` operations | None |
| Evidence/artifact persistence | `events`, `memories`, `cognitive_observations`, `experiences`, `web_experiences` | SQLAlchemy models | many | **Reuse by reference.** Stage records hold opaque refs and hashes, never copies | A new artifact store would duplicate this; none is added |
| Authorization, budgets, approvals (`experiment_approval.py`, `experiment_budget.py`, cognition `CognitiveControl.spent/reserved`) | Owner approvals; spending guard; reservations | `ExperimentApprovals`, `BudgetedExperiments`; `experiment_authorizations` | `test_experiment_budget.py`, `test_recovery_budgets.py` | **Reuse by reference.** A run stores `authorization_ref` and a budget snapshot; it never mints authority. `approval.request` is declared **unavailable** (approvals are experiment-specific today) | A generic approval engine would duplicate this; none is added |
| Events (`events` table, `Kernel.add_event`, outbox/ZMQ) | Append-only history | `Kernel.add_event(session, type, payload, source, correlation)` | many | **Reuse.** Registration and run events go here with `source="workflow"`. **No new trace table** | A separate workflow trace table would duplicate it |
| Skill Forge (`skill_forge/`) | Declarative skills over a closed `SAFE_OPERATIONS` set | `SkillRegistry`, `execute_requested_skill` | `test_skill_forge_p0.py` | **Leave alone.** Same idea (closed operation set, data-not-code) at smaller scale; the consolidation map covers merging them | A second manifest format exists *because* this one does; PI-03 decides the adapter |
| Extension specimens (`extensions/`) | Design specimens, "not loaded or executed" | README says so | none | **Leave alone**; document the future capability reference (section 9) | n/a |
| Docker init (`docker/entrypoint.sh`, `scripts/docker-demo-seed.py`, `scripts/init.ps1`) | `alembic upgrade head`, optional demo seed | shell/Python | `test_docker_config.py` | **Reuse.** The migration runs there unchanged; the workflow seed runs in app startup, not the entrypoint | None |
| API (`alive/app.py`, `create_app`, `ready` dependency, routers) | Auth and routing | `APIRouter(..., dependencies=[Depends(ready)])` | many | **Reuse the exact convention** | None |
| Hugo notebook (`site/`, `site/notebook.py`) | Static notebook pages | build step | `test_notebook*` | **Leave alone.** A future run export is a projection, not a store | Hugo is never the database |

**Nearest existing "workflow-like" things, and why a third thing is still justified.** `Investigation`
is a fixed, cognition-only state machine with its stages hard-coded in `Cognition.execute`. Skill
Forge is a closed-operation manifest for browser/graph skills. Neither is data-defined, versioned,
inspectable per stage or reusable across kinds of work. PI-02A adds *only* the definition and the
records; it does not add an executor, so it cannot become a fourth orchestrator beside them.

## 3. Schema

Three tables, the minimum that satisfies the requirements (verified against alternatives: events
already hold the trace; `model_invocations` already hold model calls; no new artifact store).

**`workflow_definitions`**: `id`, `name`, `version`, `schema_version`, `title`, `description`,
`definition_json` (canonical), `definition_sha256`, `status`, `source`, timestamps.
`UNIQUE(name, version)`; `CHECK(version >= 1)`; `CHECK(status IN draft|active|superseded|archived)`.
Only `status` (and its timestamp) ever changes; content, name, version and hash are guarded in the ORM
(`ImmutableRecord`), uniquely constrained in the database, and re-hashed on every read
(`integrity.verified`). Definitions are never deleted.

**`workflow_runs`**: `id`, `instance_id`, `definition_id` (**FK RESTRICT**), a *snapshot* of
`workflow_name`/`workflow_version`/`definition_sha256`/`schema_version`, `goal_id` and
`investigation_id` (existing ids, optional FKs), `trigger`, `input_ref`/`input_sha256` (opaque
reference and hash, never content), `authorization_ref`, `budget_json`, optional unique
`idempotency_key`, `status`, `terminal_reason`, timestamps. Snapshot columns are guarded, so a run can
never be repointed at a newer revision.

**`workflow_stage_runs`**: `id`, `run_id` (**FK RESTRICT**), `stage_id`, `attempt`, snapshot of
`stage_type`/`operation`, `state`, `input_*`/`output_*` refs and hashes, `pi_run_id` (a plain id; the FK
to `pi_runs` is PI-02B's), `model_invocation_id` (FK to the existing table),
`evidence_refs`, `validation_status`, `error_category`/`error_detail`, `uncertainty`, timestamps.
`UNIQUE(run_id, stage_id, attempt)`; `CHECK` constraints on every enumerated column.

Indexes serve the read patterns: definitions by name, runs by workflow/created and by status, stage
runs by run. Migration `0008` follows PI-01B's `0007` (`pi_runs`), which is on `main` (PR #66). A test asserts column, nullability, index, foreign-key and constraint parity between the
migration and the models, and that downgrade/upgrade round-trips.

## 4. The definition format (`schema_version: 1`)

JSON, canonicalised before hashing: defaults filled in, keys sorted, set-like lists sorted
(`depends_on`, `required`), compact separators. Stage *order* is part of the definition. Equivalent
spellings (key order, whitespace, explicit defaults, dependency order) share one hash; duplicate JSON
keys are refused rather than merged.

Stage types (schema values only in PI-02A): `deterministic`, `pi_agent`, `validation`,
`approval_gate`. Each stage names one `operation` from the closed set; the operation's kind must equal
the stage type.

Refused: unknown operations; stage/operation kind mismatch; duplicate or malformed stage ids;
unknown, repeated or self dependencies; cycles; references to anything but a declared workflow input
or an *upstream* stage's declared output field; more than 32 stages, 8 dependencies, 16 inputs/fields;
definitions over 64 KiB; any unknown key at any level (so `shell`, `command`, `import`, `class_path`,
`code`, `eval`, `capability`... cannot ride along); template/markup/escape characters in strings
(`${}`, `{{}}`, backticks, `<>`, backslash, control characters); titles outside a narrow character
set (nothing a diagram language treats as syntax); `max_attempts` other than 1 (**no automatic
retry of any stage**); `skip` on a stage with side effects; an approval gate that does anything but
stop; a `pi_agent` stage without `max_output_tokens`; more `pi_agent` stages or tokens than the
workflow's declared limits. A definition may only become `active` if every operation it names can
actually run.

## 5. Operations: closed, and honest about what exists

`alive/workflows/operations.py` is the whole vocabulary. Nothing a definition, an API or a plugin
says can add to it. A test imports every `binding` to prove it is real code.

| Operation | Kind | Bound to | Status |
| --- | --- | --- | --- |
| `context.prepare` | deterministic | `alive.cognition:Cognition.world_state` | available |
| `memory.retrieve` | deterministic | `alive.memory:MemoryService.retrieve` | available |
| `cognition.role` | pi_agent | `alive.model_gateway:gateway_for` | available |
| `evidence.validate_references` | validation | `alive.society:validate_references` | available |
| `evidence.evaluate` | validation | `alive.society:evaluate` | available |
| `evidence.qualify` | validation | `alive.evidence_qualification:EvidenceQualifier.qualify` | available |
| `evidence.record` | deterministic | none: `Cognition.finish()` cannot be called on its own | **unavailable** |
| `approval.request` | approval_gate | none: approvals are experiment-specific | **unavailable** |

The shipped `research-review` v1 is the four-stage example (Prepare context, Pi analysis, Validate
result, Record evidence). Its last stage needs `evidence.record`, so it is registered as **`draft`**
and cannot be activated or run until that operation exists. The system says so instead of inventing it.

## 6. Authority boundary (who may register a workflow)

There is **no HTTP write path**. Definitions enter only through `store.register_definition`, called
by (a) `seed_builtin` at application startup, which reads package data shipped in the repository, so
changing it is a reviewed code change, and (b) trusted in-process callers (tests, a later admin
tool). A CLI is deliberately not provided: the kernel holds an exclusive per-database lock, so an
offline tool could not safely run beside the server. Seeding is idempotent; if the stored bytes for a
shipped (name, version) ever differ from the shipped ones, startup reports it and does **not**
overwrite or stop.

## 7. Read-only API

All under `/api/v1`, all behind the same `ready` dependency as every other route (401 without the
bearer token), all `GET`: `/workflow-operations`, `/workflows`, `/workflows/{name}`,
`/workflows/{name}/versions/{n}`, `/workflows/{name}/versions/{n}/graph`, `/workflow-runs`,
`/workflow-runs/{id}`, `/workflow-runs/{id}/stages`. Responses are built from explicit field lists:
hashes and opaque references only; no credentials, run tokens, prompt text or file paths. Path
parameters are pattern-validated.

## 8. Visualisation compatibility (PI-02C)

`.../graph` returns plain nodes (`id`, `title`, `type`, `operation`, `available`) and edges, derived
from the stored definition. Mermaid is **not** stored or generated here. The renderer must: use the
stable stage `id` as the node id and for selection, escape every label, and never build `click`/link
syntax from stored text. Titles are already restricted to a character set containing no diagram
syntax, as defence in depth, not as the escaping mechanism. Run status joins by `stage_id`; Pi receipt
and artifact links come from `pi_run_id` / `evidence_refs`.

## 9. Future contracts (designed here, not executed)

**A Pi stage (PI-02B).** Carries workflow id and version, run id, stage id, attempt, the approved
operation, the run's `authorization_ref`, input ref and hash, the Governor reservation
(`model_invocation_id`), the Pi run id and receipt, and the settlement state. **A stage cannot
manufacture authorization:** the reservation is created by the existing Governor path; the stage only
presents it. The PI-01B receipt stays authoritative for provider-request details; the stage record
links to it and never re-derives accounting. There is no automatic retry after an ambiguous dispatch.

**Capability references (PI-03).** Reserved shape, **not accepted today** (the schema rejects the key):

```json
"capability": {"type": "pi_skill", "id": "research-paper-search", "version": "1.0"}
```

It would name a *library entry* resolved through a policy-mediated registry; a definition never
carries a path, URL or code. Existing Skill Forge manifests are not converted.

**Replay versus rerun.** *Replay* reads an existing run and its recorded events: no Pi process, no
provider call, no budget, no state change. *Rerun* is a new run with a new id, a new reservation and
fresh authorization; it never reuses a previous run's reservation or idempotency key.

**Recovery rules (PI-02B implements; recorded here so readers share them).**
Completed stages stay completed. Pending stages stay pending and are only started by a live run.
Failed stages stay failed (no auto-retry). Cancelled means no effect was in flight. **`UNKNOWN` is
terminal and is never resumed automatically**: a Pi stage whose dispatch is ambiguous makes the stage
and the run `UNKNOWN`, and only a human decision or a fresh run can follow. After an ALIVE restart, a
non-terminal run is reconciled from its stage records and the linked Pi run; a stage is never
re-dispatched because its record looks incomplete. A run is `COMPLETED` only when every required stage
is settled and validated.

## 10. Qualification

Local results at the head under review (Windows 11, Python 3.13; Docker 29.8). The PR description
records the exact SHA and the GitHub CI run; section 11 lists what is not demonstrated.

| Check | Command | Result |
| --- | --- | --- |
| Lint and format | `uv run ruff check alive migrations scripts tests` and `ruff format --check ...` | PASS |
| New workflow tests | `uv run pytest tests/test_workflows_spec.py tests/test_workflows_store.py tests/test_workflows_api.py tests/test_migrations.py` | PASS (see the full count below) |
| Full backend suite | `uv run pytest -q -rs` | PASS: 877 passed, 7 skipped (existing), 1 xfailed |
| Real PostgreSQL (pgvector/pgvector:pg16) | `DATABASE_URL=... uv run python -m scripts.workflows_check` | PASS: 14/14 (migrate, seed, idempotency, 8-way registration race with one winner, run snapshot, restart persistence, no token leak, downgrade to 0007 and up again) |
| Existing Docker E2E (migration runs inside the image against PostgreSQL) | `docker compose -f compose.e2e.yaml up --build --abort-on-container-exit --exit-code-from e2e` | PASS: 6 groups |
| Mutation probes | 28 deliberate breakages of the load-bearing guards | all caught (2 gaps found first, closed with tests) |
| GitHub CI on Ubuntu and Windows | PR checks | see the PR |

## 11. Limits

* Nothing executes. The records, state machines and `store.open_run` exist and are tested, but no
  component drives them yet.
* `evidence.record` and `approval.request` are declared and unavailable; the shipped example is a
  `draft` for that reason.
* The ORM guards and database constraints protect against application mistakes, not against someone
  with direct write access to the database; that case is *detected* on read (hash re-check), not
  prevented.
* YAML is not accepted (JSON only), to avoid a second parser in a trust-sensitive path.
* The workflow tables do not yet reference `pi_runs`; PI-02B adds that foreign key.
