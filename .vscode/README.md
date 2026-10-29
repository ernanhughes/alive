# VS Code workspace

Shared configuration for ALIVE developers. Everything here is committed; it contains no
machine-specific paths or secrets. Keep personal preferences in your user settings,
because changes here affect every contributor. Open the repository root as the workspace
folder.

## First open

1. Install the recommended extensions when VS Code prompts.
2. Copy `.env.example` to the ignored `.env` and configure the database and token.
   **Setup: generate API token** prints a random token if you need one.
3. Run **Tasks: Run Task** -> **Setup: bootstrap**. It runs `uv sync --locked`, `npm ci`
   and `alembic upgrade head`.
4. If the interpreter is not selected, run **Python: Select Interpreter** and choose
   `.venv`. `python.defaultInterpreterPath` points at the folder, which resolves to
   `Scripts/python.exe` on Windows and `bin/python` elsewhere.

## Daily workflow

- **Dev: full stack (Windows scripts/dev.ps1)** wraps the documented hidden-process
  launcher. **Dev: backend (uvicorn)** and **Dev: dashboard (Vite)** are the
  cross-platform foreground equivalents. Use **Dev: stop** after the full-stack task.
- The dashboard is at <http://127.0.0.1:5173>; the API docs are at
  <http://127.0.0.1:8000/docs>. If ALIVE generated a token, read it locally from
  `.alive/token` or run **Dev: show local token**.
- Press **F5** and choose **Backend: FastAPI (uvicorn)** for a debuggable backend.
  **Dashboard: Chrome** debugs the React app; start the Vite task first. The compound
  configuration launches the backend and Chrome together, but does not start Vite itself.
- Use the Testing view for focused pytest runs. The tasks mirror the documented tiers:
  **Test: quick** and **Test: affected** call `scripts/test_run.py` and are not
  full-suite passes; **Test: full suite** is the pre-merge gate. **Test: Docker tier**
  runs the deployment-sensitive container checks; use its dry-run variant first.
- **Verify: all** runs the main local gates: Ruff check, Ruff format check, full pytest,
  dashboard Vitest, extension Node tests and the dashboard build. The archive,
  notebook and Hugo jobs from CI remain separate; **Verify: evidence archive** checks one
  archive manifest at a time.
- **Demo: First Contact** and **Demo: First Thought** own their backend process. Stop
  normal development servers first and do not point them at a database you are unwilling
  to append experience to. **Demo: extension smoke** uses a disposable Chrome profile.
- Docker and site tasks are optional and require Docker Desktop or Hugo respectively.

## CI mapping

| CI job | Local task coverage |
| --- | --- |
| backend | **Verify: backend** for Ruff and pytest; **Verify: evidence archive** for one archive manifest |
| dashboard | **Verify: dashboard** for Vitest, extension Node tests and the production build |
| first-contact-postgresql | **Demo: First Contact (mock)**, or **Test: Docker tier** for the container workflow |
| notebook | **Site: build**, **Site: verify notebook** and **Test: notebook capture** |

The archive protocol scripts, the full notebook chain and paid-provider runs remain
CI or qualification activities rather than everyday editor tasks.

## Settings notes

- Ruff is the only configured Python linter and formatter. Conflicting Python linters
  are listed as unwanted recommendations. Formatting and import organization run on
  explicit save, with a 100-column ruler matching `pyproject.toml`.
- `.alive`, caches, `node_modules` and build output are excluded from search and file
  watching. `.alive` remains visible in Explorer so you can open the local token and
  evidence files.
- Python terminals load `.env` through `python.terminal.useEnvFile`. Unit tests use
  temporary SQLite databases, so they do not touch the configured development database.
- Compose files and GitHub workflows get schema validation when the Red Hat YAML
  extension is installed.
- The backend task deliberately runs one worker without auto-reload, matching
  [the development guide](../docs/DEVELOPMENT.md).

## Platform notes

- Windows is the primary target. The `scripts/*.ps1` tasks are Windows-only. On Linux
  and macOS use the foreground backend and dashboard tasks.
- The PowerShell tasks use `-ExecutionPolicy Bypass` only to run this repository's
  scripts. They do not change the machine-wide policy.
- If a task cannot find `uv`, `npm`, `node`, `docker` or `hugo`, install it and reopen
  the workspace. The tasks use the tools on `PATH`; no paths are hard-coded.

## Security

Never commit `.env`, `.alive/token`, browser profiles, observations or local evidence.
Live acceptance and paid-provider runs require the explicit setup and authorization
described in the project documentation; the default tasks use mock providers and
temporary databases.
