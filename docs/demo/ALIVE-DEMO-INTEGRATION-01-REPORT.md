# ALIVE-DEMO-INTEGRATION-01 — report

**Branch:** `feat/alive-demo-integration-01` (draft PR, no auto-merge). **Base:** `main` `395f6bd`
(the prompt's reference `1b6da07` was stale). **Spend: USD 0.00.** No provider key was set, no
inference was run, no approval or grant was created.

## What was built

A **Demonstration** tab in the bundled dashboard. One **Start demonstration** click runs ALIVE's
own evidence lifecycle through its own public API and shows each step with the rows it persisted:

observe a pinned source → save it as research memory → anchor one sentence → observe a later source
→ show the exact payload and record demo-scoped consent → compare (deterministic local fixture) →
decline to infer on a no-change source → ordinary read → **withdraw** → ordinary read → audit view.

Primary lane: **Docker only, web-native.** `docker compose up --build -d`, open the app, enter the local
token, click Start. No Hugo, no Chrome-in-Docker, no extension, no provider key. Optional second
lane (host Chrome + unpacked extension) is unchanged and needs port 8000 (PR #54).

## Preflight findings, re-verified at `395f6bd`

| # | Prompt's finding | Result |
|---|---|---|
| 1 | Port 8080 vs extension/`PAGES` on 8000 | **Resolved on main by PR #54** (compose publishes 8000, drift-guard tests). The app is at `http://localhost:8000`, not 8080. The web lane works on any free port (acceptance ran on 8090). |
| 2 | Image lacks `extension/`, `site/`, Hugo, Chrome; dashboard had no lifecycle UI | **True, and by design.** The lifecycle UI is now in the dashboard, so none of those are needed. |
| 3 | `local_fixture_claim` needs test-provider flag and possibly more | **All prerequisites identified:** `alive_relationship_allow_test_providers` (provider identity), the pinned-page allow-list (`PAGES`), pinned captures (`demo_live_01.identify`), source-identity check on save, and the consent/preview/authorize chain. The tour adds one new default-off flag, `ALIVE_DEMO_TOUR_ENABLED`; both are tied to `ALIVE_DEMO_MODE` in compose. No gate was weakened. |
| 4 | CI red at `1b6da07`; `test_select` full-mode defect | `1b6da07`'s ubuntu timing failure has not recurred. **`main` is red again, for a different reason:** `94b0e9a`, `6cf7298` and `395f6bd` all fail the Windows backend job on `tests/test_authentication_tokens.py::test_first_creation_is_stable_and_private` (`assert 4 == 1`, a token-file ACL check added by SEC-01 #56). Ubuntu, dashboard, notebook and first-contact jobs are green. That test passes in my local Windows run, so it is runner-environment dependent. Not touched here. The `test_select` defect is also **not** fixed here (separate PR, per the prompt). |
| 5 | PR #53 merged before R1/R2; local `feat/alive-pi-01a-r2` worktree | **Resolved on main:** #55 (ratchet hardening) and #56 merged. That worktree was clean and untouched; no gateway change is in this branch. |

## Architecture

`alive/demo_tour.py` is a **client of ALIVE's public API.** It calls the real
`/api/v1/browser-experience/*` endpoints in-process (ASGI transport) with the caller's own bearer
token, so every guard on those endpoints applies and the tour adds no privilege. It has no code path
to a paid provider (`PROVIDER = "local_fixture_claim"`; every consent must be `external: false`).
It is gated by `ALIVE_DEMO_TOUR_ENABLED` (default off) **and** the existing test-provider flag.

Pinned captures are verified against `fixtures/demo_live_01/manifest.json` **before any row is
written**. Source identity is checked on save. Each consent must name this run's exact goal, memory,
source URL and source hash, or the run stops. A failed run records "Stopped (fail closed)" and shows
no finding.

### Step → endpoint → persisted row

| Step | Endpoint(s) | Row kinds written |
|---|---|---|
| 1 observe original | `POST /goals`, `/grants`, `/snapshots` | goal, grant, snapshot |
| 2 remember | `POST /research/memories` | research_memory (identity = pinned bytes) |
| 3 anchor | `POST /research/memories/{id}/anchor` | revision on the memory |
| 4 observe later | `POST /grants`, `/snapshots` | grant, snapshot |
| 5 consent | `POST /research/outbound/preview`, `/authorize` | research_outbound_consent |
| 6 compare | `POST /research/relationships` | analysis, connection (candidate) |
| 7–8 abstain | same chain with `synthetic-no-change` | analysis (`insufficient_evidence`), no connection |
| 9 / 11 ordinary read | `GET /research/memories`, `GET /research/relationships`, `POST /research/retrieve` | none |
| 10 withdraw | `POST /research/memories/{id}/withdraw` | memory → `withdrawn`; its consents, analyses, connection → `invalidated` in the same transaction; event `research.memory_withdrawn` |
| 12 audit | direct read of those rows by id (status only) + the event | none |
| run log | `demo_tour_run` row (ids, step log, consent text) | demo_tour_run |

## Honest labelling

`DETERMINISTIC LOCAL FIXTURE — NOT LIVE META` appears on the page and on every fixture step. Each
step carries provenance chips that separate *pinned source*, *persisted backend row*, *fixture
provider*, *ordinary read* and *audit read*. The page says what it does not show: that either document
is true, that a model reasoned, or that ALIVE improves research. Matching pinned bytes identifies a
document; it is not a judgement of its claims. The tour is **not** self-improvement and is not
described as such.

## Verification

All results below are from this branch; the acceptance run is from a **fresh `git clone` of the pushed
branch with clean volumes**, under a disposable compose project.

| Check | Result |
|---|---|
| New API tests `tests/test_demo_tour.py` | **22 passed** |
| New React tests `DemoTour.test.tsx` | **8 passed** (dashboard total 15) |
| Full Python suite (local, Windows) | **698 passed, 7 skipped, 1 xfailed, 0 failed** |
| `ruff check` / `ruff format --check` | clean |
| Dashboard `npm run build` (tsc + vite) | passes |
| Clean-clone Docker acceptance (`scripts/demo-acceptance.ps1 -Port 8090 -Record`) | **all phases passed** at `ac33075` (see Evidence) |
| CI on the PR | At last read: 5 passing, 0 failing, 5 pending. The Windows backend job is expected to fail on the inherited SEC-01 test above. **Gate 6 (all required CI green) is therefore not met and is not claimed.** |

### Discrimination (mutation checks I ran)
* Tour: dropping the source-identity check, the pair-binding check, the fixture-provider check, or the
  whole after-withdrawal verification each **fails a test**. Three of those first survived my initial
  suite (the underlying API already enforced them), so I added forged-backend tests until each guard had
  to fire.
* React: ignoring the memory id, ignoring the source hash, or enabling Start when the runtime is
  disabled each **fails a test**.

### Negative cases (gate 4)
Wrong or changed source (`test_changed_pinned_source…`, `test_a_source_that_is_not_the_pinned_bytes…`),
unavailable fixture, unauthorised request (401), disabled tour / disabled provider / both (403, zero
rows), analyses never crossing goals, a dismissed candidate not changing the abstention binding, a
failed run showing no finding and refusing withdrawal, a forged non-fixture provider, a forged
different-pair consent, a withdrawal that does not retire the source, post-withdrawal retrieval, no
credentials (Meta methods patched to raise), and unknown run (404). In the UI: a result bound to a
different memory or hash is not shown, a disabled runtime cannot start, and an API refusal is shown as
an error.

## Evidence

Final run: fresh `git clone` of the pushed branch at `ac330758bda5d1642ca5421e8bfca3636e5b3e05`, clean
volumes, disposable compose project, port 8090 (another process held 8000 on the test machine; the web
lane does not need 8000). Receipt: [`evidence/acceptance-receipt.md`](evidence/acceptance-receipt.md).
Later commits on the branch change documentation and evidence only.

| Phase | Result |
|---|---|
| Build from clean volumes, healthy; smoke test | 8 checks passed |
| Journey in real Chrome: one Start click, 12 steps in order, before/after, audit, reload, second run, owner goal untouched | passed |
| `docker compose restart app` → after-restart (new process id, same state) | passed |
| `docker compose down` + `up -d` (volumes kept) → after-restart | passed |
| Recorded walkthrough (storyboard + video, RECORDED banner) | passed |
| `ALIVE_DEMO_MODE=false`: tab refuses, 403, a refused request adds no rows | passed |
| Teardown | nothing left behind |

Screenshots: `evidence/01-ready.png`, `02-journey-completed.png`, `03-after-reload.png`,
`04-second-run.png`, `05-after-restart.png`, `06-disabled.png`. **Recorded fallback (labelled RECORDED):**
`evidence/recorded/RECORDED-*.png` and `evidence/recorded/RECORDED-walkthrough.webm` (5.6 MB; drop it
from the PR if repository size matters, it regenerates with `-Record`).

Several acceptance runs were needed. The failures were defects in my own driver or spec (a busy port, an
ambiguous locator, a wrong disabled-phase assertion, and missing ffmpeg), found and fixed; none was a
product defect. The last run is the one reported.

## Reproduce from a fresh clone

```powershell
git clone --branch feat/alive-demo-integration-01 https://github.com/ernanhughes/alive.git
cd alive
docker compose up --build -d          # app on http://localhost:8000, local fixture only
# open http://localhost:8000, enter alive-dev-token-replace-for-local-use-000, Demonstration, Start
```

Scripted, on clean volumes under a disposable project (needs Docker, uv, Node, Chrome):

```powershell
pwsh scripts/demo-acceptance.ps1 -Record            # add -Port 8090 if 8000 is busy
```

## Limitations

* **Fixture, not inference.** The comparison is deterministic output bound to two pinned pages. Nothing
  here is evidence of semantic capability. A live comparison needs a separate owner authorisation and
  spend cap, and the tour has no code path to one.
* **Pacing is cosmetic.** Steps are revealed progressively, but each is already persisted when shown.
* **Withdrawal is retirement, not erasure.** Originals stay as retired rows for audit; the audit view
  says so and shows no source text.
* **The run log is the tour's own row.** Every id in it resolves to an ordinary row, but the log itself
  is a summary the tour wrote.
* **Offline fonts.** `style.css` `@import`s Google Fonts (pre-existing); offline it falls back to system
  fonts. Nothing else is fetched from the network.
* **Token entry.** The dashboard asks for the local token once (compose default is in the README).
* **Windows + Chrome only verified.** Linux Docker host and other browsers were not run. The Docker
  image itself is Linux and was built from the fresh clone.
* **Extension lane** (host Chrome) is unchanged and was not re-run here; it is not proof of one-click
  Docker behaviour.

## Not done / needs the owner

* `scripts/test_select.py` full-mode defect: **separate PR**, per the prompt; not started in this branch.
* Hosted CI result and independent review are not claimed.
* Hugo notebook content was **not** shipped: it would add a runtime dependency and the notebook's
  provenance model targets `:1313`; pinned fixtures were used for deterministic identities.
