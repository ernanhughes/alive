# ALIVE-11-R1 handoff - Safe Experience Reuse

## Repository

| Item | Value |
|---|---|
| Baseline `origin/main` | `f19391d0fe2825710aeec01ba4c66fa8d852f01c` |
| Branch | `codex/alive-11-r1-safe-experience-reuse` |
| Product code commit | `9f05a625de54d1810e863209186557db7a15e9cc` |
| Evidence tooling commit | `1bc947152098ff82918c4247074fe9b76b48c3f5` |
| Worktree | `C:\Projects\alive-worktrees\alive-11` |
| PR | `_Pending creation._` |
| Paid inference | **None** |

The primary checkout and its 25 local changes were not touched. The prior ALIVE-11 qualification
archives were not modified.

## Corrected defects

- No-action, suppression and uncertain decisions now clear the previous note cost, heading and
  feedback controls. Historical candidate notes are labelled and cannot receive feedback.
- Suppression counting is evidence-aware: repeated identical excerpts do not advance suppression or
  probe eligibility.
- Previously rated excerpts, already-probed excerpts and repeated paused excerpts cannot become a
  probe candidate.
- Probe authorisation remains snapshot-bound; stale snapshots still receive 409.
- Owner correction remains permission- and Governor-bound.
- `suppressed_excerpts` and `probed_excerpts` persist across restart.
- Legacy v2 contexts without excerpt tracking cannot auto-probe until new distinct paused excerpts
  are recorded.

## Policy comparison

Protocol: `archives/ALIVE-11-R1/protocol.json`.
Evidence: `archives/ALIVE-11-R1/evidence/policy-comparison.json`.

| Arm | Calls | Useful met | Missed | Wasted | Repeated | Corrections |
|---|---:|---:|---:|---:|---:|---:|
| A frozen context-wide | 7 | 3 | 2 | 4 | 1 | 0 |
| B exact-negative reuse | 10 | 5 | 0 | 5 | 0 | 0 |
| C evidence-aware contextual | 5 | 2 | 3 | 3 | 0 | 1 |
| D constant analyse | 13 | 5 | 0 | 8 | 3 | 0 |

Recommendation: keep the production default unchanged for now. Exact-negative reuse is the safest
candidate for the next native evaluation and for a demonstration where false abstention is the
primary risk; it is not semantic generalisation and costs more calls. The evidence-aware contextual
arm is cheapest but misses three opportunities. No utility advantage is adopted from this replay.

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

## Evidence

`archives/ALIVE-11-R1/` contains the frozen protocol, policy comparison, native synthetic evidence,
validation transcripts and SHA-256 manifest. The historical ALIVE-11 v1/v2 archives and all
ALIVE-01-10 payloads remain frozen.

## Review focus

1. Confirm repeated or previously rated excerpts cannot advance probes.
2. Confirm legacy v2 contexts cannot auto-probe from an untracked numeric count.
3. Confirm probe authorisation remains bound to a fresh snapshot.
4. Confirm owner correction still resets only after all permission/Governor checks.
5. Confirm no stale cost or feedback target survives a no-action/uncertain decision.
6. Confirm the policy comparison labels and recommendation are not overstated.
7. Confirm no paid calls and no prior archive changed.

Publication will be review-only: no merge and no auto-merge.
