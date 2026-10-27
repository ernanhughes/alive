# ALIVE-11-R1 - Safe Experience Reuse

Engineering: **PASS**. Research: **BEHAVIOUR_CHANGE_DEMONSTRATED** for the existing loop;
**NO UTILITY ADVANTAGE ADOPTED**. No paid inference was performed.

Baseline: `f19391d0fe2825710aeec01ba4c66fa8d852f01c` (ALIVE-11 merge).
Branch: `codex/alive-11-r1-safe-experience-reuse`.
Product code commit: `9f05a625de54d1810e863209186557db7a15e9cc`.
Evidence tooling commit: `1bc947152098ff82918c4247074fe9b76b48c3f5`.

## Review findings addressed

### Stale cost and feedback target

The panel previously retained a previous note's cost when a new observation returned `no_action`,
suppression or `uncertain`. `clearCurrentNote` now clears the note, heading, cost and feedback
controls for those decisions. A previous note used only as historical context is explicitly
labelled and its cost is prefixed "Previous note usage". Feedback cannot be attached to a historical
or previous-excerpt note.

A regression test executes the shipped panel script with a mocked no-action decision containing a
candidate note and asserts that cost is empty and feedback is disabled.

### Repeated snapshots and recovery probes

Policy v2 now stores two explicit maps per context:

```text
suppressed_excerpts[sha256] = first_paused_at
probed_excerpts[sha256] = first_probe_at
```

- A repeated observation of an unchanged paused excerpt does not increment the suppression count,
  does not create a policy revision and does not advance the probe.
- A previously rated excerpt is not a fresh probe: the exact evidence hash is checked before probe
  authorisation.
- A probe is authorised only for a snapshot whose excerpt is not already rated, paused or probed.
- Probe authorisation remains attached to that snapshot; stale paused snapshots still receive 409
  and cannot dispatch.
- Owner correction remains available, clears the suppression counter and is still bounded by grant,
  revocation, hash and Governor checks.
- `suppressed_excerpts` and `probed_excerpts` persist across restart. A restart cannot replay or
  inflate the counters.

Legacy v2 contexts without the new maps are treated conservatively: their old numeric count is
displayed for audit, but it cannot trigger an automatic probe until new distinct paused excerpts
are recorded. This avoids a migration that would invent excerpt identities.

### Presentation and documentation corrections

- Feedback is scripted operator intervention, not a user study.
- ALIVE-11 has two paid campaigns and 16 recorded calls, 8,732 charged tokens and approximately
  $0.023665 estimated spend.
- Evidence comes from controlled pages, not arbitrary browsing.
- The synthetic comparison shows missed opportunities, not adaptive superiority.
- Runtime identity is reported and hash-compared; it is not inherently trusted because the backend
  states it.
- Lexical relevance accepts one matching content token. The negation case is one failure of that
  shallow rule, not a negation-specific defect.

## Frozen policy comparison

Protocol: `archives/ALIVE-11-R1/protocol.json`, frozen before the replay.
Evidence: `archives/ALIVE-11-R1/evidence/policy-comparison.json`.

Fourteen predeclared controlled observations. Labels describe source adequacy, not owner
usefulness. No model was called; costs are synthetic price-formula estimates.

| Arm | Calls | Useful opportunities met | Missed | Wasted calls | Repeated work | Corrections | Est. USD |
|---|---:|---:|---:|---:|---:|---:|---:|
| A frozen context-wide | 7 | 3 | 2 | 4 | 1 | 0 | 0.0023625 |
| B exact-negative reuse | 10 | 5 | 0 | 5 | 0 | 0 | 0.0033750 |
| C evidence-aware contextual | 5 | 2 | 3 | 3 | 0 | 1 | 0.0016875 |
| D constant analyse | 13 | 5 | 0 | 8 | 3 | 0 | 0.0043875 |

The replay does not force exact-negative reuse to win: C is cheaper and makes fewer calls, B is
more expensive and still wastes calls on inadequate new excerpts, and A has fewer calls than B.
Under the declared objective of preserving useful opportunities, B is the strongest arm: it meets
all five labelled opportunities and avoids repeated exact work, while D meets the same count at
higher call and waste cost. Under a strict cost objective, C is strongest but misses three
opportunities. This is a real trade-off, not evidence of semantic generalisation.

## Recommendation

**Do not change the production default from this decision-level replay alone.** The current v2
context-wide policy remains in production with the repeated-suppression correctness repair. The
replay is controlled, synthetic, and does not measure native owner utility.

For the next native evaluation and the hackathon demonstration, **B exact-negative reuse is the
safest candidate** if avoiding false abstention is the priority: it never generalises a negative
rating to a different excerpt and is simpler to explain than context-wide suppression. Its cost is
higher (10 synthetic calls versus 7 for A and 5 for C). Do not describe it as semantic
generalisation; it is an exact-hash negative cache.

C is the conservative cost-oriented candidate and retains contextual learning, but its false
abstentions are worse than A in this replay. It should not become the default without a native
comparison. A should not be retained unchanged where new excerpts are ignored.

Any future default change requires a new policy version, migration plan and native qualification.
The current production policy remains interpretable; old v2 records are not rewritten.

## Verification

| Check | Result |
|---|---|
| Backend suite | 145 passed |
| Focused companion/policy tests | 30 passed |
| Extension tests | 9 passed |
| Frontend suite | 7 passed |
| Production build | Passed |
| Ruff check/format | Passed |
| Native synthetic journey | Passed; docked side-panel target |
| Paid calls | 0 |
| Prior archives | Unchanged |

## Limitations

- The policy comparison is a decision replay with predeclared labels, not native outcomes or owner
  ratings.
- The labels do not establish that the exact-negative policy improves real task quality.
- Feedback in the historical native evidence was scripted.
- The corrected policy is not re-qualified with real Meta inference in R1.
- Controlled excerpts only; no arbitrary browsing or research-history ingestion.
- The comparison costs are price-formula estimates, not invoices.
- B is a deterministic exact-negative cache, not semantic generalisation.
