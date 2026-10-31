# ALIVE-DEMO-01-PR-C-CLAUDE-REVIEW

**Reviewer:** Claude (independent; no implementation, merge, paid call or campaign change)
**Date:** 28 October 2026
**Scope:** (1) merged PR-A (#29) and PR-B (#30); (2) proposed PR-C, "Claim-Level Evidence Comparison"
**Companion file:** `test_zz_prc_probe.py`, containing probes C-real, D, E and F (throwaway; runs from `tests/` in a local clone)

---

## 1. Executive verdict: **REVISE**

| Dimension | Verdict | One-line reason |
|---|---|---|
| **Engineering Integrity** (PR-A + PR-B) | **REVISE: stop PR-C until C0 lands** | Two of the three R0 defects are fixed, but the withdrawal invariant is **not comprehensive**: a `paired` analysis keeps the withdrawn quote and is served by the endpoint the panel reads. Owner revocation can still be followed by **outbound egress**. `main` is **red** (1 failing test). |
| **PR-C Design Readiness** | **REVISE** | The direction is right: extend the existing pipeline, add one mode, add no tables. It must also (a) run on the `analyze()` history-assisted path, not the bounded/paired path; (b) key dependency on consent lineage, not on a per-row field; (c) gate `explicitly_supersedes`, scope and partial quotes **deterministically**; (d) either build the reliance anchor or drop "what you relied on" from the pitch. |
| **Hackathon Demo Readiness** | **NOT READY** | No claim mode, no fixture corpus, no native-Chrome run, no anchor. A strong, verified real-source fixture now exists (§5.4) and makes the demo better than the packet's version. |

The packet says: "If independent review finds PR-A unsafe, stop PR-C and repair the dependency first." That condition is met, narrowly. The repairs are small (§7, stage C0) and should take hours, not days.

---

## 2. Verified state

| Item | Value |
|---|---|
| `main` HEAD | `65fc0f0cde5953090e9fe65e790457d345304ea6` (2026-10-28 11:46 UTC), the merge of **#30** |
| PR #29 (PR-A) | Merged at `6bb9e44`; commits `b83141d`, `f863106`, `43511e1`, `b1d6e22` |
| PR #30 (PR-B) | Merged at `65fc0f0`; commits `6dce3fe`, `dbfde13`, `83aa827`, `d1fb60d`, `6c71012` |
| Open PRs | **UNKNOWN.** The GitHub API is not enabled for this session; state is inferred from merge commits on `main`. |
| Working tree | Clean except the reviewer's throwaway probe files (removed before the full-suite run) |
| Environment | Linux, Python 3.13.18, `uv sync` from the lockfile, SQLite, Node 22.23.4. **Not** PostgreSQL, Windows or native Chrome. |
| Full Python suite | `uv run pytest -q`: **1 failed, 254 passed, 6 skipped** (213 s). The failure is `tests/test_research_memory.py::test_grant_revocation_between_reservation_and_dispatch_blocks_call` (expects `failed`, gets `invalidated`; L1314). The test passed at `acd9b05` (84/84 in the R0 run), so **PR-A regressed it and was merged red.** |
| Extension tests | `node --test tests/extension-background.test.cjs` → 5 pass; `extension-panel.test.cjs` → 6 pass; `node --check` on `panel.js` and `background.js` OK |

**Files inspected:** `alive/research_memory.py` (withdraw L310–363); `alive/research_relationships.py` (`_analyze_bounded` L790–1180, `analyze` L1254–1525, `_scrub_withdrawn_data` and `invalidate_for_memory` L1594–1634, `_settlement_source_valid` L1636–1654, `list`); `alive/web_experience.py` (revoke L463, `valid_grant` L532, routes L1270–1372); `extension/panel.js` (PR-B block); `extension/background.js` L190–192; `extension/panel.html`; `docs/ALIVE-DEMO-01-PR-A.md`; `docs/ALIVE-DEMO-01-PR-B.md`; `tests/test_demo01_evidence_integrity.py` (three unit tests).

### Reproduction

```bash
git clone https://github.com/ernanhughes/alive && cd alive && git checkout 65fc0f0
uv sync
cp /path/to/test_zz_prc_probe.py tests/
uv run pytest tests/test_zz_prc_probe.py -q -s      # prints PROBE_* lines
uv run pytest -q                                    # full suite (remove probe file first)
```

### Probe output (verbatim)

```
# R0 probes re-run on 65fc0f0 (they assert the OLD defect, so failing = fixed)
PROBE_A after withdrawal: {"status": "invalidated", "historical_quote": null}
PROBE_A after restart: invalidated
PROBE_B finding status after grant revoked mid-dispatch: None

# New probes
PROBE_C_REAL mid-flight dispatch_status: dispatch_possibly_started | after restart recovery: ('interrupted', 4887, 4887)
PROBE_E provider called with grant status: ['revoked'] | attempt: invalidated | finding: None
PROBE_D stored copies of withdrawn text:
    ('web_experiences', 'snapshot', 'recorded', False)
    ('web_experiences', 'note', 'validated', False)
    ('web_experiences', 'research_memory', 'withdrawn', True)
PROBE_D API exposure (status, contains withdrawn text): {"/research/relationships": [200, false], "/research/memories": [200, false], "/notes/<historical note id>": [200, true], "/": [200, false], "/research/blind/runs": [200, false]}
PROBE_F paired rows after withdrawal: [('validated', True)] | listing contains withdrawn text: True
```

**R0 probe C** was synthetic (a hand-built row) and is superseded by **C-real**, which runs a genuine mid-flight crash and shows full liability charged.

---

## 3. Findings

### Blocker

**B1 (REPRODUCED): Paired analyses survive withdrawal and are served.**
- **Failure:** A `paired`-mode analysis using memory A remains `validated`, holding A's exact quote in `evidence[]` and `answer`, after A is withdrawn. `GET /research/relationships` returns it under `paired_analyses` (unredacted except during blind collection).
- **Cause:** `_scrub_withdrawn_data` callers select rows by `data.historical_memory_id == id`. Paired and current-only analysis rows are built from `shared` (L1100–1137), which does **not** carry `historical_memory_id`; only the consent and attempt carry it.
- **Why the panel hid it:** the PR-B panel only reads `connections`. That is luck, not design.
- **Why it blocks PR-C:** PR-C proposes *another* output shape, which is exactly where this keying bug recurs.
- **Fix (structural):**
  - every derived row must carry `consent_id` (they already do);
  - withdrawal computes `affected_consents = {c.id | c.historical_memory_id == id}`;
  - scrub any row of the five kinds whose `historical_memory_id == id` **or** `consent_id ∈ affected_consents`, in the same transaction;
  - add `historical_memory_id` to `shared` for belt and braces;
  - read-time: `list()` excludes rows whose consent's memory is not active.
- **Evidence:** Probe F; `research_relationships.py` L1100–1137; `research_memory.py` L336–362.

### Major

**M1 (REPRODUCED): Egress after owner revocation.**
- **Failure:** On the `analyze()` path, the dispatch guard validates sources inside one `k.lock` acquisition, **releases the lock**, then reacquires it to write `dispatch_possibly_started` **without revalidating**. A revocation queued on `k.lock` lands in that gap, and the provider is then called with the grant already `revoked`.
- **What still holds:** settlement correctly refuses the finding (attempt `invalidated`).
- **What is violated:** the bytes still left the machine after the owner said stop. That breaks "every capability checked at dispatch".
- **Contrast:** the R5 bounded path does this correctly (revalidate and mark in one transaction).
- **Fix:** make the guard session `sessions.begin()` and write the marker **inside** it, under the same lock hold, after all checks.
- **Evidence:** Probe E; `research_relationships.py` L1336–1384.

**M2 (REPRODUCED): `main` is red.**
- **Failure:** PR-A changes the guard-failure outcome from `failed` to `invalidated` (because `_settlement_source_valid` also fails and the scrub path then rewrites status), regressing an existing test. It also **erases a distinction that matters**:
  - `failed` + `reserved_never_dispatched` means "never left the box";
  - `invalidated` means "source retired".
  Both currently also scrub.
- **Fix:** when `dispatch_status == "reserved_never_dispatched"`, keep `failed`; reserve `invalidated` for post-dispatch source loss. Make the existing test pass unchanged. Use `invalid_reason` values that say what happened: `grant_revoked_before_settlement` vs `historical_memory_withdrawn` (today every case is labelled `historical_memory_withdrawn`, see L1602–1604).

**M3 (REPRODUCED; policy): "Withdrawn" is not "gone".**
- **What remains:** after withdrawal, A's full text remains in its `snapshot` and its `note` (model summary plus `evidence_quote`), and the withdrawn `research_memory` row keeps `excerpt`. `GET /notes/{id}` serves withdrawn content.
- **Severity:** this is a retention decision (open since R0, Q1), not a code bug. But it makes two claims **forbidden** until decided: "removed everywhere" and "deleted".
- **Default if undecided (D1):** keep authoritative rows, block display. Return `410 Gone` from `/notes/{id}` when its research memory is withdrawn, and scrub the `excerpt` on the withdrawn row (the snapshot remains the audit original).

**M4 (INFERRED from code): The panel shows findings from every goal.**
- **Failure:** `list()` has no goal filter, and `refreshEvidenceCards` shows up to 10 candidates across all goals. With two inquiries, cards from inquiry X appear while working on Y.
- **Fix:** add a `goal_id` query parameter on `/research/relationships` (or a new read-only `/research/evidence` endpoint) and pass the active goal from the panel.

**M5 (INFERRED; demo claim): "What you relied on" is still not modelled.**
- **Gap:** the R0 reliance anchor was never built (R0's PR-B became the card).
- **Consequence:** the PR-C pitch line *"ALIVE remembers what you relied on"* is an overclaim. The system knows what you **saved**; the model picks the quote.
- **Options:** build the anchor (one endpoint plus a validator rule, §7 C1) or change the pitch to "what you saved".

### Minor

| ID | Status | Finding |
|---|---|---|
| m1 | REPRODUCED | PR-B renders the raw enum (`possible_disagreement`) as the card heading. Map to approved text (§6). |
| m2 | INFERRED | PR-B shows capture SHA but no dates. Show "Captured <date>" from snapshot `created_at`, and "Saved <date>" for memory. |
| m3 | INFERRED | `analyze()` wraps dispatch in `except BaseException`, which swallows `CancelledError`. A real task cancellation is settled rather than propagated. Pre-existing; note for C1, do not widen. |
| m4 | INFERRED | A withdrawn source's snapshot can, while its grant is still valid, yield a *new* note that is saved as a *new* research memory. `save()` refuses only the same note. This is arguably deliberate owner action; document it as such or block on `snapshot_id` with a withdrawn memory. |
| m5 | INFERRED | `test_demo01_evidence_integrity.py` unit-tests helpers in isolation. None of the PR-A report's own qualification gates (DB scan, restart, crash) were implemented as tests. Probes C-real, D and F should become permanent tests. |

### Verified correct (keep)

- Withdrawal scrubs consents, attempts and connections in the **same transaction** as retirement.
- Settlement recheck under lock blocks late findings (B → `None`).
- The crash-after-dispatch marker charges full liability on restart.
- Panel renders via `textContent` only.
- The withdraw action clears views and re-fetches, failing closed on error.
- No new Chrome permissions.
- Events carry IDs only (`web.add` → `{"id","status"}`).

---

## 4. Scope reconciliation

| PR-C asks for | Already built | Truly missing |
|---|---|---|
| Owner preview, exact request hash, TTL authorisation | `preview` / `authorize` (10 min) | Nothing |
| Bounded dispatch, governor, durable pre-dispatch accounting | `analyze()` + markers (PR-A) | **M1 fix** |
| Exact-quote check | `validate_relationship_output` (substring in payload windows) | Sentence-bounded quotes, cross-excerpt ambiguity check, anchor overlap |
| Claim-level relation set | 4-label `RelationshipOutput` | New versioned output for one new mode (§5) |
| Supersession requiring a basis | None | Deterministic basis gate (§5.3) |
| Scope comparison | None | Model field plus deterministic demotion rule |
| Withdrawal invalidates all derivatives | Partial (B1) | Consent-lineage scrub plus read-time filter |
| Grant revoked mid-flight → no finding | Done | — |
| Evidence card, withdraw action | PR-B panel | Approved labels, dates, goal scoping, "Why flagged?" expander, dismiss-interpretation action (reuses `connection_feedback`, already revisioned) |
| Fixture with provenance | None | Fixture manifest plus loopback pages (§5.4) |
| Dates "only when verified" | Capture/save timestamps only | Publication date **only** from the fixture manifest, labelled as such. The model never outputs dates. |

**Minimal patch list:** C0 (B1, M1, M2, M4) → C1 (claim mode, validators, anchor, fixtures, stubs) → C2 (panel) → C3 (one Meta call) → C4 (qualification). No new table, migration, scheduler, provider client or Chrome permission.

---

## 5. Claim schema and classification/abstention policy

### 5.1 Placement

- New `analysis_mode = "claim_comparison"`, accepted by `preview()` and dispatched by **`analyze()`** (the history-assisted code path, with `experiment` forbidden).
- **Not** `_analyze_bounded`, which is the paired/experiment path and is shared with ALIVE-14 campaigns.
- The output is stored as a `research_connection` row with `analysis_version = "alive-demo01-claim-v1"`.
- `list()` must accept `{ANALYSIS_VERSION, "alive-demo01-claim-v1"}` (today it filters on equality).
- Existing modes are unchanged.

### 5.2 Model output contract (`ClaimComparisonOutput`, `extra="forbid"`)

```python
relationship: Literal[
    "supports",
    "conflicts",
    "qualifies",
    "explicit_supersession",
    "unrelated",
    "insufficient_evidence",
]
claim_aspect: Literal["behaviour", "recommendation", "status", "measurement", "other"]
historical_claim_quote: str | None  # ≤300, exact in historical_excerpt
current_claim_quote: str | None  # ≤300, exact in current_excerpt
scope_alignment: Literal["same", "different", "unclear"]
scope_note: str  # ≤300, e.g. "same method; 3.11 vs 3.12 docs"
supersession_basis_quote: str | None  # ≤300, exact in CURRENT excerpt
reason: str  # ≤600
limitations: str  # ≤400
confidence: float  # 0..1, displayed nowhere
```

Two changes from the packet:

- `contradicts` is renamed `conflicts`, so the stored label never reads as a verdict.
- `uncertain` is dropped in favour of the existing `insufficient_evidence`; there is one abstention label.

The model **never** outputs dates or URLs; those come from stored provenance.

### 5.3 Deterministic validator

All rules run locally after the model call. Any failure means **no alert**.

| Rule | Check | Failure result |
|---|---|---|
| V1 exact | Both quotes are substrings of their **own** payload excerpt | reject |
| V2 unambiguous | A quote must **not** also occur in the other excerpt (catches swapped labels) | reject |
| V3 sentence-bounded | Each quote starts at an excerpt start or after `[.!?:]\s` or a newline, and ends at `[.!?]` or an excerpt end. Catches partial spans that drop "not", "only if", "except". | reject |
| V4 anchor | If the memory has a reliance anchor, `historical_claim_quote` must overlap it | demote → `insufficient_evidence` |
| V5 scope | `conflicts` requires `scope_alignment == "same"` | demote → `insufficient_evidence` (never upgrade to `qualifies` automatically) |
| V6 supersession | `explicit_supersession` requires `supersession_basis_quote` to be exact in the current excerpt **and** to match the marker lexicon (`deprecated`, `superseded`, `replaced by`, `no longer recommended`, `removed in`, `erratum`, `correction`, `retracted`) | demote → `insufficient_evidence`. Recency alone is never a basis. |
| V7 negation sanity | `supports`, where exactly one quote contains a negator (`not`, `no`, `never`, `n't`, `without`) | reject |
| V8 abstention | `unrelated` / `insufficient_evidence` must have confidence ≤ 0.2 and no assertive language (reuse `ASSERTIVE_EVIDENCE_LANGUAGE`) | reject |
| V9 lineage | Payload binds `historical_memory_id`, `reliance` (if any), both SHAs and `goal_id`; settlement recheck (PR-A) applies | invalidate |

**Alert policy:**

- `conflicts` (scope same), `qualifies` and `explicit_supersession` that **pass all rules** produce the indicator.
- `supports` is shown only inside the panel as "Checked: consistent".
- `unrelated` and `insufficient_evidence` produce "Checked: no alert".
- Rejected outputs produce "Check could not be validated; nothing shown".

### 5.4 Fixture corpus

**Real, verified, licence-clean primary case** (checked by the reviewer at primary source):

- **Source:** CPython `Doc/library/datetime.rst`, `datetime.utcnow()` entry.
  - Branch `3.11` @ `ffbb7500…` (file sha256 `ae8a521f…`): describes the method and warns that aware datetimes are preferred. **No deprecation.**
  - Branch `3.12` @ `3d6d2a63…` (file sha256 `d9ce3438…`): same text **plus** `.. deprecated:: 3.12 — Use datetime.now with UTC instead.`
  - Retrieved 2026-10-28T11:57Z.
- **Licence:** per `docs.python.org/3/license.html`, *"Python software and documentation are licensed under the Python Software Foundation License Version 2."* Mirroring with attribution is permitted.
- **Why it is the ideal demo case:**
  - Golden label: `explicit_supersession`, `claim_aspect = status`, basis = the 3.12 deprecation notice.
  - The **behaviour** sentence ("Return the current UTC date and time…") is **not** contradicted: the method still does exactly that.
  - A careless system will say "contradiction". ALIVE should say "Python 3.12's own docs deprecate this method; the earlier description of what it does is not contradicted." That distinction is the product.
- **Capture rules:**
  - Mirror the **rendered** HTML text of the `utcnow` section from `docs.python.org/3.11/…` and `/3.12/…`. The reviewer verified the `.rst` source only; the rendered strings (e.g. "Deprecated since version 3.12: Use datetime.now() with UTC instead.") must be captured and hashed by Codex and **re-verified by a human**.
  - Serve each as a **focused excerpt page** on loopback, so the quotes fall inside the 2,000/3,000-character windows.
  - Each page carries a header: `LOCAL MIRROR — excerpt of <canonical URL>, Python docs <version>, retrieved <date>, PSF License v2`.

**Synthetic, labelled `SYNTHETIC FIXTURE` on the page and card.** One each:

| Case | Golden label |
|---|---|
| Clear conflict (same benchmark, same hardware, opposite result) | `conflicts` |
| Scope change (same metric, different hardware) | `qualifies` |
| Same topic, agreement | `supports` |
| Unrelated topic | `unrelated` |
| Misleading exact quote: "It is **not** true that caching improves recall." | V3 rejects the partial span "caching improves recall." |
| Newer but no supersession marker | must **not** become `explicit_supersession` |
| Abstention (too thin) | `insufficient_evidence` |

**Manifest** (committed as `fixtures/demo01/manifest.json`): `id`, `kind` (`real_mirror` | `synthetic`), `canonical_url`, `upstream_commit`, `retrieved_at`, `licence`, `text_sha256`, `golden_relationship`, `golden_aspect`, `golden_author` (a human, recorded **before** any model run), `notes`.

---

## 6. Browser UX language

### Approved

| Situation | Text |
|---|---|
| Indicator (none) | `Evidence checked · no alert` |
| Indicator (alert) | `1 saved claim to review` |
| `explicit_supersession` | `Source-stated change: the newer source marks this as deprecated/corrected.` plus the basis quote |
| `conflicts` | `Possible disagreement — model interpretation of exact quotes, not independently verified.` |
| `qualifies` | `Possible qualification — the newer source may narrow the conditions.` |
| `supports` | `Checked: consistent with your saved source (model interpretation).` |
| Abstain or rejected | `Insufficient evidence — no alert.` / `Check could not be validated; nothing shown.` |
| Quote provenance | `Exact text from your saved capture · sha256 3d6d…` |
| Dates | `Captured 28 Oct 2026` · `Saved 28 Oct 2026` · `Published (per fixture manifest): …` |
| Mirror / fixture | `Local mirror of docs.python.org/3.12/…` · `Synthetic fixture` |
| Actions | `Keep for review` · `Dismiss interpretation` (records feedback; never alters sources) · `Withdraw saved source…` (confirm) |
| After withdrawal | `Saved source withdrawn. Dependent findings retired.` |

### Must not be said, in the UI or the pitch

- "false", "wrong", "debunked", "contradiction confirmed", "verified", "fact-checked"
- "deleted" or "removed everywhere" (until M3 is decided and implemented)
- "what you relied on" / "what you believed" (unless the anchor is built; then "the passage you anchored")
- "ALIVE discovered" or "found overnight". Every check is owner-triggered.
- "live" for a recorded run, or "from the web" for a local mirror
- Any numeric confidence or percentage

---

## 7. Codex implementation prompt (staged)

> **ALIVE-DEMO-01 PR-C.** Base `main` @ `65fc0f0`. Open **draft** PRs only; do not merge. **No real Meta call** at any stage before C3, and C3 only after explicit owner approval with a hard cap. Never call `_analyze_bounded`, campaign or approval endpoints, or modify ALIVE-14 code. No new tables, migrations, schedulers, provider clients or Chrome permissions.
>
> **C0: repair the dependency (separate PR, must merge before C1).**
> 1. **B1:** withdrawal (`ResearchMemory.withdraw` and `invalidate_for_memory`) scrubs rows of all five kinds where `historical_memory_id == id` **or** `consent_id ∈ {consents with that memory}`, in the same transaction. Add `historical_memory_id` to the bounded-path `shared` dict. `list()` excludes any row whose consent's memory is not active.
> 2. **M1:** in `analyze()`, open the dispatch guard with `sessions.begin()` and write `dispatch_possibly_started` inside it, after all checks, under the same lock hold. Delete the separate marker block.
> 3. **M2:** if `dispatch_status == "reserved_never_dispatched"`, the terminal status is `failed` (not `invalidated`). Use reasons `grant_revoked_before_settlement`, `historical_memory_withdrawn` and `current_source_changed`. `test_grant_revocation_between_reservation_and_dispatch_blocks_call` must pass **unchanged**.
> 4. **M4:** add an optional `goal_id` filter to `GET /research/relationships`.
> 5. **Tests:** convert reviewer probes C-real, D, E and F into permanent tests with these assertions:
>    - E: the provider is never called after revocation;
>    - F and D: zero occurrences of a withdrawn marker string in any derived kind, and in every GET response except authoritative `snapshot`/`note` rows pending D1;
>    - C-real: full liability is charged.
>    Add a **leak-scanner helper** (all tables, all derived kinds) reusable by later tests.
> 6. **Gate:** full suite green on SQLite **and** PostgreSQL; probes pass; report the SHA, counts and the skipped list.
>
> **C1: claim mode (backend only).**
> - Implement §5.1–5.3 exactly.
> - Add `POST /research/memories/{id}/anchor {quote}`: exact substring of the stored excerpt; store offsets; revisioned; refused on withdrawn memories. Include `reliance` in the payload hash.
> - Add `local_stub_claim`, which returns the manifest's golden output per fixture ID, plus an adversarial stub set: swapped labels, partial negation span, missing basis, scope mismatch labelled `conflicts`, newer-only "supersedes", invented quote and over-confident abstention.
> - Commit the fixtures and manifest of §5.4; the real mirror must carry its provenance header.
> - **Gate:** each V-rule has a passing and a failing test. Each fixture yields its golden label via the stub. Withdraw before, during and after settlement and after restart leaves zero leaks (leak scanner). Existing modes are unaffected (full suite green).
>
> **C2: panel.**
> - Extend the PR-B section only: §6 labels; dates; "Why flagged?" expander (scope note, both quotes, basis quote, limitations, validator result); goal-scoped fetch; `Dismiss interpretation` via the existing `connection_feedback`.
> - Text-only rendering. Links, if any, use `http:`/`https:` schemes only, are built with `URL()`, and carry `rel="noopener noreferrer"`.
> - **Gate:** a native Chrome run of anchor → check (local stub) → card → dismiss → withdraw → card gone → backend restart → still gone; `node --test` green; 360 px width readable.
>
> **C3: one Meta call (requires owner approval and cap).**
> - Run the utcnow mirror pair through `claim_comparison` with `provider = "meta"`.
> - Record model ID, usage, `request_sha256`, validator result, the card screenshot and any non-golden outcome. A non-golden result is reported, not retried until it matches.
>
> **C4: demo qualification.** A 90-second scripted run (§8 of the packet, using §6 language), offline fallback on `local_stub_claim`, recorded video labelled as recorded, and an evidence archive. The engineering verdict is reported separately from demo readiness.
>
> **Stop and roll back** if any of these occur: any leak-scanner hit in a derived kind; any provider call after revocation; any change to ALIVE-14 files; any test weakened to pass. Each stage is a separate PR, and rollback is a revert of that PR (no schema changes).

---

## 8. Owner decisions (with recommended defaults)

1. **Retention (M3).** *Default:* keep `snapshot`/`note` as audit originals but return `410` for notes of withdrawn memories; scrub `excerpt` on the withdrawn row. Never claim "deleted".
2. **Reliance anchor (M5).** *Default:* build it in C1 (small). Otherwise the pitch must say "saved", not "relied on".
3. **C3 Meta call.** *Default:* approve exactly **one** call on the utcnow pair, `muse-spark-1.3` (re-verify availability), with a hard cap equal to one reservation.
4. **Real mirror.** *Default:* use the utcnow pair as the headline, with synthetic fixtures as the regression corpus. A human re-verifies the rendered text before the demo.
5. **Pitch.** *Recommended:* "ALIVE remembers the passages you anchor, and when a newer source changes their standing, it shows you exactly why — then lets you retire them."

---

*Caveats: verified on SQLite/Linux only. ALIVE-14-R5 safety claims, PostgreSQL behaviour, native Chrome and open-PR state were **not** verified. Rendered Python docs pages could not be fetched from this environment; the fixture claim rests on the CPython `.rst` sources at the pinned branch SHAs and must be re-verified against the rendered pages.*
