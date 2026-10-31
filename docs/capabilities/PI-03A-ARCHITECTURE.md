# PI-03A architecture

PI-03A only. It stops at independent review. No automatic merge, paid inference, PI-03B/C or
Bespoke selector.

## Starting point (audit)

Before PI-03A there were two maps: descriptive `OPERATIONS` and executable `ADAPTERS`. Some
legacy bindings pointed at ALIVE methods that were never governed workflow adapters, so a
non-null binding was not proof of execution readiness. `operations.py` is now a descriptive
projection of one catalogue, and `adapters.py` holds only the reviewed adapter functions.

## Decisions

- **One catalogue.** Restricted YAML manifests plus a code-owned implementation allowlist form
  an immutable startup `CapabilityRegistry`. Every question (validation, grants, the workflow
  graph, built-in seeding, the catalogue API, execution) is answered by that application registry
  through `registry_for(kernel)`. `OPERATIONS` survives only as a descriptive projection used as
  a default by unit tests; an AST test fails if production code relies on it. The global `ADAPTERS`
  map no longer exists.
- **The runner executes the bound implementation.** `invoke()` has no callback parameter. The only
  runtime resolver is `registry.adapter_for(identity)`, which re-verifies the retained id,
  version, manifest hash and implementation fingerprint and then resolves that exact version.
- **Capability versus implementation.** The manifest is a contract. An implementation is
  reviewed code in `alive/capabilities/trusted.py`; the YAML only names it by opaque id.
- **Definition hashes are unchanged.** Exact per-stage capability contracts are stored in a
  separate immutable `workflow_capability_bindings` record (migration 0011). Optional stage pins
  (`capability_version`, `capability_sha256`) are omitted from canonical bytes when absent, so
  every PI-02 definition keeps its hash.
- **Authority is an intersection.** Manifest declaration, implementation ceiling, deployment
  policy, workflow definition, owner grant, run and stage limits, and lifecycle state must all
  allow an action. The registry rechecks identity, implementation fingerprint and policy before
  each invocation; a changed or disabled capability fails the run closed.
- **Implementation identity covers the selection, not just the bytes.** An implementation's
  fingerprint hashes its id, interface, kind, side effects, the `module:function` adapter the
  allowlist selects, the legacy binding, permission ceiling, traits and source-file list, as
  well as the normalised bytes of those files.
- **Traits, not names, express what downstream code relies on.** An implementation may carry
  code-owned traits (`model.role`, `result.writer`, `validation.independent`,
  `validation.reference-identity`). Result recording, artifact serving, validation views,
  observatory Pi linkage and Intelligence receipts check the trait of the implementation a stage
  *retained*, so reusing an implementation under a new capability id keeps its behaviour. A
  manifest cannot declare a trait.
- **Repository reads are content, not paths.** The trusted host captures bounded content once
  (`capture_repository`); the owner approves the content digest; the stage receives an immutable
  reader over only the approved subset. The capability never sees a root path.
- **Restart activation.** Manifests load at startup. There is no hot reload, so a running
  execution cannot gain permissions from an edited file.

## Flow

```
manifests (YAML)  -> parse + canonicalise + hash
                  -> registry: cross-check vs trusted implementation ceiling
workflow register -> registry.bind(spec) -> retained binding snapshot (+ event receipt)
owner grant       -> pins binding hash, per-stage identity, permissions, limits, resources
runner start      -> verify binding + grant, snapshot copied onto the execution
runner stage      -> recheck pin -> invoke (input contract, timeout) -> output contract + size
                  -> existing transactional persistence and events
observatory       -> retained identity only; never today's catalogue
```

## Compatibility and history

- **Genuine history only.** The DAG-only contract of PI-02 is applied in two cases: a definition
  row that already exists without a binding (it predates migration 0011), and a shipped
  definition whose exact hash is in `LEGACY_DEFINITION_SHA256` (`research-review` v1 and the
  `intelligence-fixture` v1 harness definition). A new definition, pinned or not, must satisfy the
  full capability contract and is refused atomically otherwise. Retirement: re-issue a shipped
  definition as a new version that passes the modern contract, remove its hash, and delete the
  branch when the set is empty.
- **Runtime still enforces both contracts** on an adopted definition.
- **History never depends on today's catalogue.** A run with a retained snapshot is read from
  it. A run without one (it predates migration 0011) is read from its stored, hash-verified
  definition with no catalogue consulted, and is never attributed a capability identity.
  Pre-0011 implementation lookups use a frozen operation-to-implementation table.
- **Retention.** `persistence: none` forbids a capability-created artifact. The runner always
  keeps each stage's output in run history (dependencies, hashing and replay need it). The
  generic event feed (REST, WebSocket and live publish) withholds stage output and is scoped to
  this instance; the observatory projections already withhold it.

## Out of scope

Marketplace, remote install, hot reload, arbitrary writes, shell, general network, automatic
capability selection, and any claim of sandboxing in-process trusted code.
