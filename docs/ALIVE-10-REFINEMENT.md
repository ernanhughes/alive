# ALIVE-10 post-review refinement

This change addresses the two independently reproduced review findings on PR #14
at `2686a8008d48b8932072a6d1b53b4379fed4a754`. It retains the v2 policy's design,
thresholds, Governor and browser permissions. It adds no paid Meta qualification.

## Snapshot-bound recovery

Reaching the three-observation pause threshold makes a **new designated snapshot**
eligible for one probe. It does not authorise old paused snapshots. Previously the
analysis endpoint consulted the current `analyse` recommendation at the threshold,
allowing all three old snapshots to dispatch without correction or recorded probes.

The endpoint now distinguishes probe eligibility from ordinary eligibility. Analysis
under a paused context requires either the snapshot's persisted `probe_authorized`
flag or explicit owner correction, even when the policy says a probe is due.
The existing one-attempt-per-snapshot constraint prevents duplicate probe dispatch.
Grant/hash checks, restart revocation, reservations and budget checks still apply.
A rejected budget check leaves the designated snapshot eligible for an explicit retry;
it creates neither a provider call nor a successful correction record.

## Migration preserves revisions

ALIVE-09 revised feedback rows in place: `created_at` described the original rating,
while `policy_version_after` advanced on revision. Backfilling by row creation order
could therefore undo the owner's latest correction on a shared excerpt.

Migration now processes effective policy revision order, then timestamp and row ID
for deterministic tie breaking. Unversioned feedback predating the adaptive policy
is processed before versioned feedback. The v1 policy row remains intact, a new v2
row is created, and subsequent reads reuse the migrated row.

New feedback updates record `updated_at`. Migration takes an effective timestamp
from that field or retained legacy history. If a legacy revision's time is no longer
available, it remains null; creation time is not misrepresented as revision time.
The effective policy version and original feedback/note provenance are retained.

## Regression coverage

- Old paused snapshots reject analysis both before and after the designated probe.
- One eligible probe succeeds; a duplicate request makes no additional call.
- A budget-rejected probe preserves policy state and succeeds after an explicit
  budget correction, with exactly one dispatch.
- v1 same-excerpt feedback A/useful, B/useful, revised A/not-useful migrates to the
  last effective rating, regardless of row creation order.
- Migration works with retained history and with a revision timestamp that is no
  longer recoverable, preserves v1, and creates only one v2 row.

The original ALIVE-10 archive remains frozen evidence of the reviewed implementation.
Supplementary post-review validation is recorded separately. Synthetic-provider
qualification does not imply native Meta behaviour or an adaptive research advantage.
