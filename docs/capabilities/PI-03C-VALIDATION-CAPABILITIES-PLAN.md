# PI-03C plan: validation and compositional qualification

Not started. Requires PI-03B review authorization.

## Validation capabilities

| Capability | Checks | Explicitly does not claim |
| --- | --- | --- |
| `evidence.validate-references` (migrate to a v1.1 contract) | Cited ids exist in the approved context | That the claim is supported |
| `evidence.verify-locators` | A cited file/page/section locator exists in a captured source and its hash matches | Semantic support |
| `evidence.compare-claims` | Exact or normalised comparison against controlled sources | Truth in the world |
| `report.compose` | Deterministic rendering of validated records | New findings |

Validation status vocabulary stays: contract, structural, reference identity, semantic
(`unverified` unless an independent process sets otherwise), independent verification.

## Compositions to qualify

At least three genuinely different workflows built only from manifests and existing stages:
repository review (inspect, validate locators, compose), research review (retrieve, extract,
Pi analysis, validate references, record), and deterministic source comparison. Each is
registered, granted, executed, replayed and compared in the observatory.

## Compatibility and upgrade tests

- A capability patch/minor/major upgrade: old definitions keep their pins; new definitions can
  select the new version; a permission change forces a new implementation review.
- Revocation and deprecation while a run is active and while history is inspected.
- Retirement of the PI-02 compatibility path once no unpinned definition remains.

## Independent evaluation

Run the Pi regression, Intelligence regression and extension suites, PostgreSQL (including
migration 0011), Docker, and Linux and Windows CI. Use scripted providers only; no paid
inference. Record the exact head SHA and source/image parity.

## Bespoke readiness

The catalogue answers: what exists, supported source types, required inputs, requested
permissions, limits, which workflows pin each exact version, and which versions are approved.
A future selector may propose a workflow from this metadata; the proposal must still pass
registration, an exact owner grant and runtime admission. No model may alter permissions or
activate an implementation. PI-03C documents this boundary; it builds no selector.
