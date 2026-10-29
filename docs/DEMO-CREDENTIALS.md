# Demo credentials

ALIVE uses one local bearer token per checkout. The token is not a user account and it is
not shared between checkouts, worktrees, or a local process and a Docker container.

## One-command setup

From the checkout that will run the demo:

```powershell
./scripts/init.ps1
```

The script:

- creates `.env` from `.env.example` when needed;
- keeps an existing valid `ALIVE_API_TOKEN` in `.env`;
- otherwise reuses a valid `.alive/token`;
- otherwise generates a new URL-safe token;
- writes the same value to `.env` and `.alive/token`;
- applies an owner-only Windows ACL to both files;
- copies the token to the clipboard without printing it.

Then start one environment from that same checkout:

```powershell
./scripts/demo.ps1      # Docker on http://127.0.0.1:8000
./scripts/dev.ps1       # local backend on :8000 and dashboard on :5173
```

Paste the clipboard token once into the dashboard or extension. The dashboard keeps it in
`sessionStorage` for the tab; the extension keeps it in `chrome.storage.local`.

## Preflight check

```powershell
uv run python scripts/verify_demo_credentials.py
```

The verifier checks, without printing any token value:

- `.env` and `.alive/token` exist, are valid, and agree;
- both have private permissions/ACLs;
- the application loader resolves the same token;
- `docker compose config` resolves the same token;
- every running ALIVE container is reported, including containers from other checkouts,
  other tokens, and other published ports;
- the live endpoint rejects no token and a wrong token, and accepts the configured token.

It exits with status 1 on a failure. Useful forms:

```powershell
# Check a server you are about to demo against (for example a worktree on :8080)
uv run python scripts/verify_demo_credentials.py --base-url http://127.0.0.1:8080 --require-live

# Check another checkout without changing it
uv run python scripts/verify_demo_credentials.py --root C:\Projects\alive-worktrees\alive-pi-01a-r2

# Create/sync the token first, then verify
uv run python scripts/verify_demo_credentials.py --fix --require-live
```

`scripts/demo.ps1` and `scripts/dev.ps1` run the same preflight automatically before they
report that the demo is ready.

## Do not mix checkouts

A token from `C:\Projects\alive\.alive/token` does not authenticate a container started from
`C:\Projects\alive-worktrees\alive-pi-01a-r2`, even if both are running on this machine. Each
checkout has its own `.env` and token. Run `scripts/init.ps1` in the checkout that launches the
demo, or use `scripts/demo.ps1` / `scripts/dev.ps1` from that checkout.

The composed app no longer falls back to a shared default token. If `.env` has no
`ALIVE_API_TOKEN`, `docker compose up` fails with a message to run `scripts/init.ps1` instead of
silently starting with a credential that does not match the one you are reading.

## Changing or rotating the token

```powershell
./scripts/init.ps1 -Rotate
```

Restart a running local app, or recreate a running compose stack, after rotating. Existing
dashboard tabs and extension sessions must be reconnected with the new value.

## Scope

This is a local, single-owner credential boundary. It does not protect against another process
running as the same user, a privileged local administrator, a compromised host, or a token that
was copied into logs or chat. The `.env` ACL is best-effort setup protection; the application
itself enforces the generated `.alive/token` DACL when it creates that file.
