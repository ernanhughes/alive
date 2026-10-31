# L1-02 — Governed LLM analysis: architecture

Status: implementation for independent review. **Dependent on L1-01 (PR #80, head `f7b97a1`), which is
not yet merged or independently reviewed.** This branch is pinned to that commit and its PR targets
the L1-01 branch. L1-01's no-inference profile and its authorization logic are unchanged.

## What it does

An owner can ask for a review of an approved repository capture by one governed model call. The
model reasons about the code. Deterministic code decides what may be sent, how much, to whom, under
which budget, and what may be believed about the answer.

```
objective + approved capture ──► review (profile approved-repository-analysis, grants nothing)
        │                                   │ owner reads: files, destination, model, limits
        │                                   ▼
        │                   local CLI approval with the exact review digest
        ▼                                   │
 start (same digest) ──► Grant ──► WorkflowRunner
      read      repository.inspect@1.1.0   re-checks custody, returns the approved bytes
      analyze   repository.analyze@1.0.0   re-checks the disclosure approval, ONE model call
      validate  repository.validate_findings@1.0.0   citation existence, report
      record    result.record@1.0.0        retains the integrity-checked result
```

## What is reused, not rebuilt

| Need | Existing mechanism |
| --- | --- |
| Procedure choice | BESPOKE-01 recipe `approved-repository-analysis` (separate from `approved-repository-inspection`) |
| Authority | L1-01 admission: immutable review, local CLI approval, identical Grant, `verify_grant` |
| Source custody | PI-03B approvals; a new *operation* `repository.analyze` means "may be disclosed to the model" |
| Capabilities | PI-03A manifests and the code-owned allowlist (two new fingerprinted implementations) |
| Model call | `Cognition.call_role` → `ModelGateway` → `PiGateway` → loopback egress → `DirectMetaGateway` |
| Budget | Governor reservation, charged at the worst case before dispatch, never retried |
| Execution | the unchanged `WorkflowRunner`, dispatch fence, cancellation and recovery |
| Visibility | the Workflow Observatory, plus `GET /api/v1/admissions/{id}/report` |

## Changes to shared code (each small, each tested)

* `Cognition.call_role(..., spec=None)`: a typed role (schema, instructions, parser) may replace the
  fixed `RoleOutput` role, **only** inside an authorized workflow stage. `spec=None` is the old path.
* `workflows.context.model_claim(..., analysis=None)`: when a typed role is used the owner's Grant
  must name that implementation and that role contract, and the model input must equal the context
  rebuilt from the stage inputs. Every other check is shared.
* `WorkflowRunner.authorize_dispatch`: for the analysis role the call is bound again at the
  dispatch fence (instructions, role contract, context digest, source digest).
* `capabilities.execution.invoke`: a model stage that also holds `source.read` keeps the full stage
  context (it needs Cognition); source-only adapters keep the narrow context.
* `Cognition.admit_owner_workflow(..., model=True)`: a model admission needs Cognition explicitly
  started with the `meta` provider; the inspection path still requires autonomy paused.
* `alive.providers.meta_endpoint_host`: names the destination host for disclosure without reading
  any credential.

## Where the LLM is used, and where it is not

The model reads the supplied lines and reasons about the objective. It produces findings, an
assessment of severity, uncertainty and suggested verification. Code owns source identity,
authorization, the size and number of calls, the output schema and every citation check. No
deterministic check stands in for semantic judgement, and no model assessment is promoted to fact:
findings carry `verification: "none"` and the assessment states `independent_verification: false`.

## Failure semantics (as implemented by the existing runner)

| Event | Result |
| --- | --- |
| Output breaks the schema | run `UNKNOWN`: a request was sent, no outcome is claimed; no retry |
| Provider answers with an HTTP error | run `FAILED`, reservation stays charged |
| Provider times out after dispatch | run `UNKNOWN` (ambiguous), never retried |
| Cancel during the provider call | run `CANCELLED` or `UNKNOWN`; never retried |
| Fence or reservation refuses | no provider request exists |
| Replay, restart, second start | recorded history; no dispatch |

## Boundaries of this milestone

No model-assisted recipe selection (L2-01), no workflow composition (L2-02), no outcome learning
or promotion (L3). The analysis covers only the files supplied, at most 8 files and 8,192 bytes, and
says so in the context and in the report. There is no local inference path in ALIVE: the only
destination is the configured Meta endpoint, so this profile always means remote disclosure.
