# ALIVE-11-R1 qualification archive

Status: **ENGINEERING_PASS**. Research: **BEHAVIOUR_CHANGE_DEMONSTRATED**; no utility advantage
adopted. Paid inference: **none**.

Baseline: `f19391d0fe2825710aeec01ba4c66fa8d852f01c` (ALIVE-11 merge).
Product code commit: `9f05a625de54d1810e863209186557db7a15e9cc`.
Evidence tooling commit: `1bc947152098ff82918c4247074fe9b76b48c3f5`.

This supplementary archive records the ALIVE-11-R1 correctness fixes and a frozen four-policy
decision replay. It does not modify the ALIVE-11 qualification-v1/v2 archives or any ALIVE-01-10
archive.

## Evidence

| File | Meaning |
|---|---|
| `protocol.json` | predeclared fourteen-observation policy comparison |
| `evidence/policy-comparison.json` | executable replay results |
| `evidence/native-synthetic.json` | current-code native synthetic journey with docked side panel |
| `validation/backend.txt` | 145 backend tests |
| `validation/companion-focused.txt` | 30 focused companion/policy tests |
| `validation/extension.txt` | 9 extension tests |
| `validation/frontend.txt` | 7 frontend tests |
| `validation/build.txt` | production dashboard build |
| `validation/ruff.txt` | Ruff check and format |
| `validation/native-synthetic.txt` | native synthetic command output |
| `manifest.json` | SHA-256 and byte length for every payload except itself |

## Result

The protocol labels source adequacy, not owner usefulness. Costs are synthetic price-formula
estimates, not provider invoices.

| Arm | Calls | Useful opportunities met | Missed | Wasted | Repeated | Corrections |
|---|---:|---:|---:|---:|---:|---:|
| A frozen context-wide | 7 | 3 | 2 | 4 | 1 | 0 |
| B exact-negative reuse | 10 | 5 | 0 | 5 | 0 | 0 |
| C evidence-aware contextual | 5 | 2 | 3 | 3 | 0 | 1 |
| D constant analyse | 13 | 5 | 0 | 8 | 3 | 0 |

Exact-negative reuse is strongest for preserving useful opportunities, but costs more calls and
still wastes calls on inadequate new excerpts. The evidence-aware contextual arm is cheapest but
misses three predeclared opportunities. No policy is adopted into production from this replay.

## Correctness fixes

- Panel no-action/suppression/uncertain results clear stale cost and feedback targets.
- Repeated unchanged excerpts do not advance suppression or probe eligibility.
- Previously rated or probed excerpts cannot be used as the recovery probe.
- Probe authorisation remains snapshot-bound and permission/Governor-gated.
- Suppression and probe tracking persist across restart.
- Legacy v2 numeric suppression counts without excerpt tracking cannot auto-probe.

## Boundaries

- The comparison is a decision-level replay, not native outcome evidence or a user study.
- Feedback in historical native evidence was scripted.
- No real Meta call was made for R1.
- Controlled excerpts only; no arbitrary browsing.
- Exact-negative reuse is a deterministic hash cache, not semantic generalisation.
- The production default remains unchanged; candidate adoption requires a new version, migration
  plan and native evaluation.
