# PI-03A architecture (implementation in progress)

Base: `c1cdd171a70d8ececdc5537dab648105668ee081`. PI-03A only; stop at
independent review. No automatic merge, paid inference, PI-03B/C or selector.

The audit found two existing maps: descriptive OPERATIONS and executable
ADAPTERS. Some descriptive bindings point at underlying ALIVE methods without a
governed adapter. Their legacy metadata must not be treated as execution readiness.

Design:

- Restricted YAML plus strict typed manifests and a bounded JSON-schema subset.
  Reject tags, aliases, anchors, duplicate/merge keys, interpolation, excess
  nesting and unknown fields before canonical hashing.
- One startup catalogue combines manifests and a code-owned implementation
  allowlist. Manifests never resolve Python import strings. Existing operation
  metadata and ADAPTERS become compatibility projections, not authorities.
- Preserve definition JSON/hashes. Store exact per-stage capability contracts in
  an immutable definition-binding record, separately from existing definition
  bytes. Pin identities in the owner grant and retain a snapshot on execution.
- Recheck pinned hash/version, implementation fingerprint, deployment policy,
  owner grant and existing lifecycle authority before invocation and settlement.
  Existing Cognition/Governor/Pi dispatch and cancellation remain authoritative.
- Legacy registration can explicitly adopt bindings without rewriting a
  definition. Old execution records without a retained binding stay unlabelled;
  inspection must never infer historical capability identity from today's catalogue.
- Repository inspection receives an opaque approved snapshot reference and
  constrained immutable content. Trusted snapshot import is bounded, refuses
  symlink/junction escapes and secret/binary/encoding violations, and identifies
  captured bytes without claiming an atomic Git commit or filesystem sandbox.
- Read-only authenticated catalogue API, CLI, and generic dashboard catalogue.
  Observatory links use retained identity and hash, never a name-only latest match.

Testing follows AGENTS.md: parser/schema tests first, targeted registry and
execution cases next, then final qualification once the implementation is ready.
Full CI is a final gate, not the edit loop. Known transitional seams and trust
limitations will be recorded in the final security and implementation reports.
