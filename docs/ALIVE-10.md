# ALIVE-10 - Native Intelligence Qualification and Recovery

**Status:** `ENGINEERING_PASS`, `NATIVE_SYNTHETIC_PASS`, `NATIVE_META_NOT_RUN`,
`RESEARCH_ADVANTAGE_NOT_DEMONSTRATED`.

ALIVE-10 corrects the three defects identified in the ALIVE-09 review and qualifies the corrected
loop in an isolated native Chrome journey. It does not claim a Meta result or adaptive superiority.

## Starting state

- Base: `origin/main` at `5ee1031f36aa411e8675f208a794de13c478fea0` (ALIVE-09 merged).
- Source commit for the evidence: `021462b480cb7ba33fa431cc949ba3a3db43a237`.
- Branch: `opencode/alive-10-native-intelligence`.
- Primary worktree `C:\Projects\alive` remained untouched.

ALIVE-09's controlled loop was real: feedback persisted, a policy changed and a later decision
consulted it. The review identified three product/intelligence defects:

1. The feedback buttons promised "reuse" and "analyse next time" while negative ratings could pause
   analysis.
2. Repeated ratings of identical excerpts could be counted as independent evidence.
3. Suppression was absorbing: without owner correction, no new feedback could arrive.

## What changed

### 1. Feedback semantics

`extension/panel.html` and `extension/panel.js` now distinguish the rating from the consequence:

- **Useful - this note helped me**
- **Not useful - this note did not help me**

The help text states that repeated unhelpful notes may temporarily pause automatic analysis for this
goal and page, that the owner can request analysis anyway, and that feedback never grants
permissions.

The panel also fixes a feedback-target bug:

- a no-action or uncertain observation disables feedback;
- a new analyse observation disables feedback until its own note is validated;
- a previous candidate note is shown as "Previous note - not a feedback target";
- a recalled note is labelled as recall;
- stopping observation clears the current feedback target.

### 2. Distinct-excerpt evidence

Policy ID: `companion-feedback-usefulness-v2`.

The policy row is still stored in the existing `WebExperience` table; no migration was added. The
schema is:

```text
contexts[goal_id|url|language] = {
  goal_id, url, language,
  evidence: {
    excerpt_sha256: {
      useful, feedback_id, note_id, updated_at, revisions
    }
  },
  suppressions, probes, ...
}
```

The support count is `len(evidence)`, not the number of feedback rows. Consequences:

| Event | Effect |
|---|---|
| Three ratings of one unchanged excerpt | one evidence unit; support 1 |
| Three ratings of three distinct excerpts | support 3 |
| Repeated identical snapshot | no extra support |
| Same note, same rating | idempotent; no policy update |
| Same note, changed rating | one revision; evidence replaced |
| Different note, same excerpt, same rating | audit row; no support/version change |
| Different note, same excerpt, changed rating | latest effective rating for that excerpt |
| Different goal, URL or language | separate context |
| Changed excerpt | separate evidence unit |

Feedback records now include `evidence_sha256`, `duplicate_evidence`, `policy_changed`,
`distinct_support`, useful/not-useful evidence counts and policy hashes before/after.

### 3. Recovery from suppression

The chosen mechanism is Option D: bounded periodic re-evaluation. It is combined with the retained
explicit owner correction (Option C).

- Minimum distinct support: **3**.
- Pause threshold: useful rate **<= 0.20**.
- A paused observation records `suppressions += 1` and a policy version/event.
- After **3** paused observations, the next related observation receives a one-snapshot probe
  authorisation and action `analyse` with `probe=true`.
- The probe still requires the exact-page grant, reviewed hash and Governor budget.
- A probe creates a new note and feedback opportunity. Useful feedback can raise the rate above
  0.20 and restore normal analysis.
- Owner correction on a paused observation resets the suppression counter and records a correction.
- A failed Governor check rolls back both the correction and the reset.

This avoids permanent lock-in without treating every changed excerpt as a fresh context. Cross-
excerpt transfer remains possible because the policy context is still goal/URL/language, not one
excerpt.

### 4. Policy migration

If an ALIVE-09 v1 policy row exists, `policy_row` creates a v2 row with
`migrated_from` metadata and backfills distinct evidence from existing validated feedback rows. The
old policy row remains auditable. New policy versions are recorded in policy history and in decision
and note payloads.

## Decision flow

```text
snapshot
  -> deterministic relevance
  -> exact useful recall?  yes -> recall (0 calls)
  -> adaptive recommendation
       support < 3          -> analyse
       rate > 0.20          -> analyse
       rate <= 0.20         -> no_action, increment suppression
       suppression >= 3     -> analyse with one-snapshot probe
  -> Governor authorisation
  -> provider reservation / execution
  -> owner feedback
  -> distinct evidence update or revision
```

The policy cannot grant permission, expand the allowlist, bypass a reviewed hash, bypass the
Governor, increase budgets or replay an interrupted call.

## Native harness

`scripts/native10.py`:

1. selects free loopback ports;
2. starts an isolated controlled page server;
3. starts a local Meta-compatible synthetic HTTP provider;
4. runs Alembic against an isolated SQLite database;
5. starts the current-branch backend;
6. copies the unpacked extension to a temporary directory and rewrites only `config.js` plus
   test-only host permissions;
7. launches system Chrome with a fresh persistent profile;
8. loads the extension with `Extensions.loadUnpacked`;
9. triggers the extension action and uses the panel;
10. exercises the journey and writes evidence;
11. stops only its own processes.

The harness does not use port 8000, the owner's database, the primary worktree or a paid provider.
The extension copy is test-only; production defaults remain the two documentation pages and local
backend port.

### Native result

| Step | Result |
|---|---|
| Three distinct excerpts | analysed; support 1 -> 2 -> 3; 3 calls |
| Paused observation 1 | `no_action`; 0 calls |
| Paused observation 2 | `no_action`; owner correction then analysed; call 4 |
| Three more paused observations | suppressions 1 -> 2 -> 3; 0 calls |
| Periodic probe | analysed; call 5 |
| Probe feedback useful | support 4, useful rate 0.25; analysis restored |
| Duplicate analysis | HTTP 409; no call |
| Restart | policy v11 persists; notes 5 -> 5; stale grant 403 |
| Wrong origin | HTTP 403 |
| Modified hash | HTTP 403 |
| Budget exhaustion | HTTP 409; no call |

Provider usage: **5 calls, 750 synthetic tokens, estimated $0.0016875, paid $0**. The model name
recorded by the companion is its pinned `muse-spark-1.3`, but the endpoint was the local stub.

Chrome version: `155.0.8059.85`. The extension was real; the actual service worker, storage,
observer, panel, backend and SQLite path were exercised. Chrome did **not** produce a docked
side-panel target under `Extensions.triggerAction` in headless or headful runs; the extension page
was used. This is a presentation limitation, not a backend simulation.

## Comparison

`archives/ALIVE-10/evidence/policy-comparison.json` is a frozen decision-level replay with eight
predeclared labelled observations. It is not native outcome evidence.

| Arm | Calls | Labelled useful | Useful missed | Paused | Probes |
|---|---:|---:|---:|---:|---:|
| Corrected adaptive v2 | 5 | 2 | 2 | 3 | 1 |
| ALIVE-09 v1 | 3 | 0 | 4 | 5 | 0 |
| Simple one-negative | 1 | 0 | 4 | 7 | 0 |
| Constant analyse | 8 | 4 | 0 | 0 | 0 |

The corrected policy recovers where v1 remains paused. It still misses useful analyses that constant
analysis would obtain and makes fewer calls. The result is a trade-off, not a demonstrated
intelligence advantage. Counterfactual cost avoided is an estimate, not observed spend.

## Verification

| Check | Result |
|---|---|
| Backend suite | 133 passed |
| Companion focused | 23 passed |
| Frontend suite | 7 passed |
| Production build | Passed |
| Ruff check/format | Passed |
| Extension JavaScript syntax | Passed |
| Native synthetic journey | Passed |
| Previous archives | All manifests unchanged |

## Reproduction

```powershell
uv run pytest -q
uv run pytest -q tests/test_web_experience.py
uv run python -m scripts.native10
uv run python -m scripts.alive10_evidence
uv run python -m scripts.alive10_compare
uv run python -m scripts.archive10
```

Native evidence is written under `.alive/native10-*`; `scripts/archive10.py` sanitises it into
`archives/ALIVE-10/evidence/` and verifies previous manifests.

## Meta status

No Meta inference was run. `archives/ALIVE-10/evidence/meta-qualification-status.json` records a
bounded request: maximum 8 calls, 12,000 tokens and $0.10 estimated spend, no automatic paid retry,
isolated database/profile and redacted evidence. Owner approval is required before execution.

## Limitations

- No Meta inference and no paid calls.
- Native journey used the extension page, not a docked side panel.
- Synthetic provider output; no model reasoning quality claim.
- Decision-level comparison with predeclared labels, not a task-outcome study.
- One controlled page and one goal; no open-web generalisation.
- Thresholds are fixed constants, not runtime-tunable.
- No browser-history ingestion or cross-device inference.
- ALIVE-08 remains negative on its primary comparison; its post-hoc always-retrieve diagnostic is
  not promoted or used here.

## Next step

1. Owner reviews this branch and the archive.
2. Claude independently audits policy, UI and native evidence.
3. If approved, run the bounded Meta qualification and record real calls/tokens/cost separately.
4. Only then consider comparative product claims or ALIVE-11.
