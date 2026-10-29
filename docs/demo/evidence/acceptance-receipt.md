# Clean-clone acceptance receipt

> Recorded at `ac33075`, **before #59** removed compose's shared default token. The flow as documented
> now was re-run on `main`: see [`acceptance-receipt-main-33c7796.md`](acceptance-receipt-main-33c7796.md).

* Commit under test: `ac330758bda5d1642ca5421e8bfca3636e5b3e05` (a fresh `git clone` of the pushed branch; no local changes).
  Later commits on the branch touch documentation and evidence only; no runtime file changed after this SHA.
* Command: `pwsh scripts/demo-acceptance.ps1 -Port 8090 -Record` (disposable compose project, clean volumes,
  torn down afterwards; port 8090 because another process held 8000 on the test machine).
* Provider credentials: none set. External provider calls: none possible from the tour.

| Phase | Result |
|---|---|
| Clean volumes, `docker compose up --build -d`, healthy | pass |
| `scripts/docker-smoke-test.py` | 8 checks passed |
| Journey in real Chrome: one Start click, all 12 steps in order, before/after table, audit view, reload, second run, owner goal untouched | 1 passed |
| `docker compose restart app`, then after-restart checks (new process id, same persisted state, no finding, audit rows retained) | 1 passed |
| `docker compose down` then `up -d` (volumes kept), after-restart checks again | 1 passed |
| Install Playwright ffmpeg (user cache), recorded walkthrough with RECORDED banner (storyboard + video) | 1 passed |
| `ALIVE_DEMO_MODE=false`: tab refuses, Start disabled, API returns 403, a refused request adds no rows | 1 passed |
| Teardown of the disposable project | no containers or volumes left |

Screenshots: `01-ready` … `06-disabled`. Recorded fallback: `recorded/RECORDED-*.png` and
`recorded/RECORDED-walkthrough.webm`; every frame carries "RECORDED WALKTHROUGH — NOT LIVE".
Not verified here: Linux Docker host, browsers other than Chrome, the host-Chrome extension lane.
