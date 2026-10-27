# ALIVE-10 - Native Intelligence Qualification and Recovery

Status: **ENGINEERING_PASS**, **NATIVE_SYNTHETIC_PASS**, **NATIVE_META_NOT_RUN**,
**RESEARCH_ADVANTAGE_NOT_DEMONSTRATED**.

This archive records the corrected ALIVE-09 feedback loop and an isolated native Chrome journey
against the current branch. It is not a Meta qualification and does not establish adaptive
superiority.

## Provenance

| Item | Value |
|---|---|
| Base `origin/main` | `5ee1031f36aa411e8675f208a794de13c478fea0` (ALIVE-09 merged) |
| Branch | `opencode/alive-10-native-intelligence` |
| Source commit | `021462b480cb7ba33fa431cc949ba3a3db43a237` |
| Policy | `companion-feedback-usefulness-v2` |
| Context | `goal_id | URL | language` |
| Independent evidence | Reviewed excerpt SHA-256 |
| Minimum distinct support | 3 |
| Pause threshold | useful rate <= 0.20 |
| Recovery | 3 paused observations -> one bounded periodic probe |
| Chrome | `155.0.8059.85`, native extension page |
| Docked side panel | **not produced** by the automation target |
| Provider | local Meta-compatible synthetic HTTP stub |
| Meta inference | **No** |
| Paid calls | **0** |

## Corrected behaviours

### Feedback semantics

The panel now says:

- **Useful - this note helped me**
- **Not useful - this note did not help me**

The explanatory copy states that repeated unhelpful notes may pause automatic analysis for this goal
and page, that the owner can analyse anyway, and that feedback never grants permissions. A paused
state disables the feedback buttons and clears any previous feedback target. A recalled note is
labelled as recall. A previous candidate note cannot receive feedback for a new observation.

### Independent evidence identity

Policy v2 stores evidence per reviewed excerpt hash inside the goal/URL/language context:

```text
contexts[goal|url|language].evidence[sha256] = {
  useful, feedback_id, note_id, updated_at, revisions
}
```

- Three ratings of one unchanged excerpt count as **one** evidence unit.
- Three distinct excerpts count as three.
- Repeated identical snapshots do not add support.
- A same-note rating revision replaces the effective rating and increments policy once.
- A duplicate rating request is idempotent.
- A same-excerpt rating from another note updates the audit row but not support or version.
- A contradictory rating for the same excerpt uses the latest effective rating.
- Contradictory ratings from different excerpts are separate evidence units.
- Context isolation remains goal/URL/language.

### Recovery

After three no-action observations in a paused context, the next observation is a **bounded periodic
probe**: one analysis is eligible with a probe authorisation tied to that snapshot. The probe is
still subject to the exact-page grant, reviewed hash and Governor budget. Owner correction remains
available at any paused observation and resets the suppression counter. A useful probe rating can
restore analysis when the useful rate rises above 0.20.

This is Option D from the assignment. It was chosen over permanent suppression and over treating
every changed excerpt as a fresh context, which would destroy cross-excerpt transfer.

## Native synthetic journey

`evidence/native-synthetic-journey.json`

| Step | Result |
|---|---|
| Three distinct controlled observations | analysed; support 1 -> 2 -> 3; calls 3 |
| First paused observation | `no_action` from feedback policy; call count stays 3 |
| Second paused observation | `no_action`; suppressions 2 |
| Owner correction | analysed; correction recorded; suppressions reset; calls 4 |
| Three more paused observations | `no_action`; suppressions 1 -> 2 -> 3 |
| Periodic probe | `analyse` with `probe=true`; calls 5 |
| Useful probe feedback | support 4, 1 useful / 3 not useful, rate 0.25; analysis restored |
| Duplicate analysis request | HTTP 409; no call |
| Restart | policy v11 persists; notes 5 -> 5; calls 5; stale grant 403 |
| Wrong origin grant | HTTP 403 |
| Modified excerpt hash | HTTP 403 |
| Budget exhaustion | HTTP 409; no call |

The five provider calls used **750 synthetic tokens** and an estimated **$0.0016875** under ALIVE's
`price()` formula. This is not a Meta charge.

### Native limitation

Chrome was real and the extension was loaded from a temporary unpacked copy. The harness triggered
the extension action and exercised the actual service worker, storage, observer, panel, backend and
SQLite path. Chrome did not expose a docked side-panel target under `Extensions.triggerAction` in
headless or headful runs, so the extension page was used. No claim is made for the docked side panel.

The isolated backend used a free loopback port, a fresh SQLite database, a fresh Chrome profile and a
test-only loopback page. No primary worktree process or owner database was read or stopped.

## Policy comparison

`evidence/policy-comparison.json` is a **frozen decision-level replay**, not native outcome evidence.
Eight observations have predeclared usefulness labels; no model was called.

| Arm | Calls | Labelled useful analyses | Useful missed | Paused | Probes |
|---|---:|---:|---:|---:|---:|
| Corrected adaptive v2 | 5 | 2 | 2 | 3 | 1 |
| ALIVE-09 v1 | 3 | 0 | 4 | 5 | 0 |
| Simple one-negative | 1 | 0 | 4 | 7 | 0 |
| Constant analyse | 8 | 4 | 0 | 0 | 0 |

The corrected policy recovers where v1 remains paused, but it misses some useful analyses that
constant analysis would obtain. It is **not** claimed superior. The constant policy gets more
labelled useful outcomes at higher call cost. Counterfactual cost avoided is explicitly labelled
as an estimate.

## Controlled evidence

- `evidence/feedback-independence.json` - repeated excerpt counts once; three distinct excerpts
  count three; revision and duplicate semantics.
- `evidence/suppression-recovery.json` - three paused observations, probe, restoration.
- `evidence/restart-proof.json` - policy v11 persists; support 4; no replay.
- `evidence/governor-revocation.json` - native 403/409 checks and unit invariants.
- `evidence/native-panel.png` - extension panel with connection details collapsed.

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
| Prior archives | All manifests unchanged |

## Reproduction

```powershell
uv run pytest -q
uv run pytest -q tests/test_web_experience.py
uv run python -m scripts.native10
uv run python -m scripts.alive10_evidence
uv run python -m scripts.alive10_compare
uv run python -m scripts.archive10
```

`native10.py` starts and stops only its own backend, page server, provider stub and Chrome profile.
It does not use port 8000 or the owner's database.

## Limitations

- No Meta inference; no paid calls.
- The native qualification used an extension page, not a docked side panel.
- Provider output is synthetic and fixed; it does not demonstrate model reasoning quality.
- The comparison is decision-level with predeclared labels, not an outcome study.
- One controlled excerpt page and one goal; no open-web generalisation.
- The pause threshold and probe count are fixed constants in this version, not runtime-tunable.
- No browser-history ingestion, cross-device inference or Docker search integration.
- ALIVE-08 remains unchanged and negative on its primary comparison. Its post-hoc diagnostic is not
  promoted here.
