# Re-run receipt: documented flow and acceptance on current `main`

The first receipt (`acceptance-receipt.md`, commit `ac33075`) predates #59, which removed compose's
shared default token and made `ALIVE_API_TOKEN` required. This re-run covers the flow as documented now.

* Commit under test: `33c7796af11ed80abec5e5e269cdc53e5ce9b46f` (`origin/main`, a fresh `git clone`, no local changes).
* Host: Windows, Docker, real Chrome. Port 8090 (the web demonstration works on any free port; only the
  Chrome-extension lane needs 8000). No provider key set; no external call possible from the tour.

| Check | Result |
|---|---|
| Bare `docker compose config` with no `.env` token | refuses with "Run scripts/init.ps1 in this checkout ..." |
| `./scripts/demo.ps1` (init, then `docker compose up -d --build`) | stack healthy |
| `.env` token equals `.alive/token` (43 characters) | yes |
| Smoke test, token read from `.env` with the README's PowerShell line | 8 checks passed |
| The retired default token (`alive-dev-token-...-000`) against the app | HTTP 401 |
| Clean-volume acceptance (`scripts/demo-acceptance.ps1 -Port 8090 -Record`): journey in Chrome, `restart app`, `down` + `up` with volumes kept, recorded walkthrough, demo-mode-off refusal | all passed |
| Cleanup | no containers or volumes left |

`scripts/init.ps1` itself, checked separately in a throwaway directory on a non-elevated account: creates
`.env` from `.env.example`, writes one 43-character token to `.env` and `.alive/token`, leaves a single
owner rule on each, is idempotent, `-Rotate` changes both, `.env` is git-ignored, and the app's own token
validator accepts the value.

**Not verified:** `init.ps1` on an elevated administrator account (GitHub's Windows runner showed such
accounts can keep explicit rules that `icacls /inheritance:r` does not remove, as fixed for the app's own
token file in #60; files created by PowerShell normally inherit, so this may not apply, but it was not
tested); Linux or macOS hosts; browsers other than Chrome.

**CI on `main` at the time of writing:** dashboard, ubuntu backend, notebook and first-contact-postgresql
green; the Windows backend job was still running. Not claimed green.
