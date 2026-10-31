# BESPOKE-01 delivery

Implementation status: deterministic selector, versioned YAML catalogue, strict context and
rationale contracts, immutable recommendation history, trusted laboratory handoff, integrated
Bespoke dashboard, retained graph previews and real Observatory run linkage. Production execution
from the selector is unavailable. Independent review is pending; no automatic merge.

## Changes

- New `alive/bespoke/` package and five recipe declarations.
- Shared restricted YAML reader extracted from the existing capability parser.
- New authenticated Bespoke routes wired into `alive/app.py`.
- Migration 0012 for immutable scoped recommendation records; migration-head assertions updated.
- Bespoke dashboard, existing graph reuse, capability/history/run links and race-safe requests.
- Behavioral tests, dashboard tests, desktop/mobile browser scenarios, controlled demonstration,
  independent expected fixture package and implementation-authored mutation campaign.
- Architecture, schema, selector, security, evaluation, authoring and independent-review guides.

No source-ingestion or semantic-validation capabilities, new model client, workflow engine,
learning subsystem, extension permissions or production authorization endpoint were introduced.

## Compatibility

`captured-repository` binds only real `repository.inspect` v1.0.0; `controlled-comparison` binds
prepare/evaluate/record; `bounded-evidence-review` binds prepare/cognition/reference-check/record.
Exact versions, manifest hashes and workflow hashes are retained in YAML; binding/implementation
and policy identities are retained in recommendations. Definitions must actually be registered
and active. `scientific-document` and `discussion-source` stay unavailable because their required
source capabilities and workflows do not exist. The original shipped research-review v1 remains
a draft and is never substituted for the recipe's pinned v2.

## Local qualification

The detailed JSON/PNG receipts are in `validation/`. Checks performed during development:

- Focused Bespoke/YAML and migration checks; real handoff through the existing runner.
- 154 focused capability-registry, resolution/authority, workflow-spec/store and model-gateway tests.
- Dashboard: 105 unit tests; production TypeScript/Vite build.
- Two real Chrome E2E scenarios at 1440px and 390px, against a disposable migrated/seeded runtime,
  checking retained graphs and actual Observatory navigation with zero execution writes.
- SQLite and disposable PostgreSQL migration-0012 demonstrations: repository and source-comparison
  runs completed, with zero model calls or paid inference.
- Docker image built, including its production dashboard and pinned Pi binary; real PostgreSQL
  Docker smoke passed all eight checks against an isolated qualification container/database.
- Fixture evaluation: 14/14 deterministic cases, 13/14 gated fixed-default cases, zero unauthorized
  selections; exact replay, provenance, explanation and resource-ceiling assertions passed.
- Eleven behavioral mutants killed, zero survived, zero invalid; independent mutations still due
  from the external reviewer.

Wall time and record sizes are actual measurements in demonstration/evaluation JSON, not promises
or quality scores. The selector enforces a five-second total deadline and 262,144-byte record ceiling.
There is no downstream quality evaluation and no claim of improved real-world task accuracy.

The PR description is the final-head qualification ledger: exact head, Windows/Linux CI jobs,
pending or failed checks, and any reruns are reported there without status-only commits. Local
checks are not represented as green full CI. The independent-review gate remains closed until
a separate reviewer assesses the final implementation and its qualification evidence.

## Known limits

The single-owner bearer model is inherited. There is no production source-capture consent or
owner-approval route, so the normal dashboard initially has no approved contexts. Real example
procedures are registered only by trusted host code, not implicitly by recipe loading. Controlled
fixture grants remain laboratory-only. Independent feedback references stay empty; no learning
or automatic promotion occurs. Broader scientific/discussion use requires PI-03B/03C and a separately
qualified source/owner approval boundary.

Screenshots: [desktop](validation/bespoke-1440.png), [mobile](validation/bespoke-390.png).
