# PI-03A architecture

PI-03A only. It stops at independent review. No automatic merge, paid inference, PI-03B/C or
Bespoke selector.

## Starting point (audit)

Before PI-03A there were two maps: descriptive `OPERATIONS` and executable `ADAPTERS`. Some
legacy bindings pointed at ALIVE methods that were never governed workflow adapters, so a
non-null binding was not proof of execution readiness. `operations.py` and `adapters.py` are
now derived views over one catalogue.

## Decisions

- **One catalogue.** Restricted YAML manifests plus a code-owned implementation allowlist form
  an immutable startup `CapabilityRegistry`. `OPERATIONS` and `ADAPTERS` remain only as
  compatibility projections (see "Transitional seams").
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

## Transitional seams

- `LEGACY_OPERATIONS` and `bind(..., legacy_compatibility=True)` adopt PI-02 definitions that
  carry no pins. At registration the legacy path checks the DAG's declared contract only; at run
  time both contracts are enforced. Retire it once no PI-02 definition lacks pins.
- `ADAPTERS` and `operations.OPERATIONS` are derived at import from the default registry.
  An app built with a custom registry resolves through `registry_for(kernel)`; the module-level
  maps are used only as a fault-injection seam in tests.
- Executions created before migration 0011 have no retained snapshot and stay unlabelled.

## Out of scope

Marketplace, remote install, hot reload, arbitrary writes, shell, general network, automatic
capability selection, and any claim of sandboxing in-process trusted code.
