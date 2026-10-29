# ALIVE-DEMO-INTEGRATION-01 — independent review checklist

Reviewer: read-only. Do not trust the report's test totals; reproduce. Each item says what would
falsify the claim.

## 1. Source-pair fidelity
- [ ] `alive/demo_tour.py::TourRun.compare` raises unless the consent preview's `goal_id`,
      `current_url`, `current_sha256` and `historical_memory_id` equal this run's snapshot and memory.
      *Falsify:* forge the preview (see `test_tour_refuses_a_consent_for_a_different_source_pair`).
- [ ] The abstention is bound to its own source hash, which differs from the 3.12 hash.
- [ ] `load_captures()` verifies each pinned capture against `fixtures/demo_live_01/manifest.json`
      **before any row is written**. *Falsify:* edit a capture; the run must 409 with zero goals.
- [ ] `save_memory` rejects a source whose identity is not the pinned bytes.
- [ ] `dashboard/src/DemoTour.tsx::isBound` refuses to render a result for another goal, memory or
      hash. *Falsify:* the three mutations in the report each fail a test.
- [ ] Analyses of two runs never share ids or goals (`test_analyses_never_cross_between_goals`).

## 2. Consent and provider
- [ ] No path to a paid provider: `grep -n "meta\|MetaProvider" alive/demo_tour.py` finds only the
      label text. `PROVIDER` is the constant `local_fixture_claim`.
- [ ] Every consent is `external: false` with provider id `local_fixture_claim`, else the run stops
      before `authorize`.
- [ ] The consent text is shown **before** Start and recorded in the run row.
- [ ] Gating: `ALIVE_DEMO_TOUR_ENABLED` (default `false`) **and** `ALIVE_RELATIONSHIP_ALLOW_TEST_PROVIDERS`;
      compose ties both to `ALIVE_DEMO_MODE`. With either off: 403 and zero rows.
- [ ] `ALIVE_CLAIM_META_ENABLED`, `ALIVE_RESEARCH_META_ENABLED` and `ALIVE_META_API_KEY` are not set by
      compose for the tour. Tests monkeypatch `MetaProvider.{structured,_request,discover}` to raise.
- [ ] The tour calls the public endpoints with the caller's own bearer token (no elevated token).

## 3. Withdrawal and restart
- [ ] `withdraw` is the existing `POST /research/memories/{id}/withdraw`; the tour does not delete rows.
- [ ] After withdrawal the **public** reads (`/research/memories`, `/research/relationships`,
      `/research/retrieve`) exclude the source and everything built on it
      (`test_pause_then_withdraw_uses_the_real_endpoints`).
- [ ] A fake withdrawal is detected (`test_tour_fails_if_withdrawal_does_not_actually_retire_the_source`).
- [ ] Audit rows are statuses and ids only; no source text; `physically_deleted: false` is stated, and
      the text says "retained", not "erased".
- [ ] Restart: a new process id and identical persisted answers (`test_persisted_state_...restart`
      and the Docker `after-restart` phase, which also covers `down` then `up` with volumes kept).

## 4. Synthetic labelling
- [ ] `DETERMINISTIC LOCAL FIXTURE — NOT LIVE META` is on the page, on every fixture step, and in the run.
- [ ] No UI text claims model reasoning, truth, verification of claims, or self-improvement
      (the React test scans for it).
- [ ] The recorded walkthrough carries a **RECORDED** banner in every frame.
- [ ] Separate labels for: pinned source, persisted backend row, fixture provider, ordinary read,
      audit read. A fixture is never presented as a replay of a live result.

## 5. Docker-only cold start
- [ ] From a fresh clone: `./scripts/demo.ps1` (runs `init.ps1`, then `docker compose up -d --build`),
      open `http://localhost:8000`, paste the per-checkout token, click **Start**. No Hugo, no
      Chrome in Docker, no extension, no key. (A bare `docker compose up` now stops with a "run
      scripts/init.ps1" message by design.)
- [ ] `docs/demo/evidence/` shows the run; `scripts/demo-acceptance.ps1` reproduces it on clean volumes
      under a disposable compose project.
- [ ] The page still loads fonts from Google when online; offline it falls back to system fonts
      (cosmetic, pre-existing `@import` in `style.css`).

## 6. Original expectations preserved
- [ ] `git diff origin/main --stat` touches no extension, manifest, Dockerfile, `archives/`,
      `evaluations/`, `fixtures/`, `tests/` other than the new file and the existing ones' unchanged content.
- [ ] Existing suites pass unchanged (Python, 15 dashboard tests, extension Node suites, CI).
- [ ] No test expectation was edited to make the demo pass.

## 7. Zero spend
- [ ] Receipts show no outbound provider request; `ALIVE_META_API_KEY` empty in every run.
- [ ] No approval, grant, campaign or budget record was created.

## Known limits to confirm are disclosed
Pacing of the step reveal is cosmetic (steps are already persisted when shown). The step log is the
tour's own row, though every id in it resolves to an ordinary row. The comparison logic is fixture
output, so nothing here is evidence of semantic capability.
