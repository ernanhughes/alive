# Deterministic selection

Policy versions: `bespoke-selector/v1`, `bespoke-suitability/v1`, `bespoke-rationale/v1`.
The canonical `POLICY` document is hashed and retained with each recommendation. Handoff refuses
changed policy identity; historical reads continue to use their retained schema and explanation.

## Eligibility first

For every bounded candidate, verify active recipe status; captured source compatibility;
explicit objective; required evidence; requested ceilings; requested permissions; deployment
transport and configured provider availability; exact installed capability versions and manifest hashes; active registered workflow
and canonical hash; retained registration receipt; complete per-stage pins; current binding
contracts, implementation fingerprints and deployment limits; input presence/types; actual
permission requirements; and workflow/stage resource ceilings. Unknown or changed dependencies
produce bounded typed reasons. A score cannot reverse a rejection.

Source approval validation happens before candidate evaluation. Invalid, expired, revoked,
cross-instance, cross-goal, cross-inquiry or withdrawn context receives a bounded 409 refusal,
not a fake recommendation. A valid source with no feasible procedure produces an immutable
`abstained` selection with all candidate rejection reasons.

## Suitability, not outcome probability

Eligible candidates receive these explicit factors:

| Factor | Points |
| --- | --- |
| Explicit objective alignment | 40 |
| Captured context match | 25 |
| Required evidence present | 15 |
| Declared validation contract | 10, or 0 for none |
| Resource headroom | 5 for no model calls, otherwise 0 |
| Operational simplicity | `max(0, 6 - stage_count)` |

The latter factors describe resource/complexity preferences, not evidence of better outcomes.
There are no fabricated confidence percentages, success probabilities, latency measurements,
historical quality labels or self-assessed performance signals. The rationale names the policy
and displays every factor. Ineligible candidates have score zero and no suitability factors.

Sort by eligibility, descending suitability, then recipe ID, version and canonical hash.
Return the best eligible candidate and all bounded alternatives. An unspecified intent abstains
and asks the user to choose an explicit objective; observation never silently becomes intent.

Procedural diversity counts distinct execution contracts (canonical workflow, retained binding
and exact input hash). Multiple recipe labels over one execution contract count as one procedure.
No prompt rewrite or presentation-only change creates another execution strategy.

## Resource envelope

- At most 32 recipes; at most 128 installed capabilities considered by selection.
- At most 32 stages per recipe, inherited workflow bounds, bounded YAML/context declarations.
- Five-second total selection deadline, including lock/database waits.
- At most 262,144 canonical bytes per retained selection, checked before persistence.
- At most 50 context references, history summaries or linked runs returned per request.
- Sequential bounded recipe lookups and registration-receipt validation; no unbounded table scan
  by recommendation ID. The bound is linear in recipe and stage count, not page length.
- Exactly zero selection model calls, provider requests, network fetches or filesystem capture.

## API

All endpoints reuse existing bearer authentication and runtime readiness:

```
GET  /api/v1/bespoke/recipes
GET  /api/v1/bespoke/contexts
POST /api/v1/bespoke/recommend
GET  /api/v1/bespoke/recommendations
GET  /api/v1/bespoke/recommendations/{id}
GET  /api/v1/bespoke/recommendations/{id}/runs
```

The first endpoint reports installed dependency compatibility, not contextual eligibility or
execution authority. The context endpoint returns only references from currently valid grants.
There are no approve, execute, install, register, cancel or inference endpoints under Bespoke.
