# PI-03A implementation and developer guide

## Layout

| Path | Role |
| --- | --- |
| `alive/capabilities/manifest.py`, `contracts.py` | Restricted YAML loader, typed manifest, bounded schema subset, canonical hash. |
| `alive/capabilities/manifests/*.yaml` | Built-in declarations (legacy operations plus `repository.inspect`). |
| `alive/capabilities/trusted.py` | Reviewed implementation allowlist, permission ceilings, fingerprints. |
| `alive/capabilities/registry.py` | Immutable catalogue, binding, grant checks, configuration policy. |
| `alive/capabilities/bindings.py` | Durable retained contracts and authorization verification. |
| `alive/capabilities/execution.py` | Invocation and result checks used by `WorkflowRunner`. |
| `alive/capabilities/repository.py` | Host capture and the constrained reader. |
| `alive/capabilities/api.py`, `cli.py` | Read-only catalogue API; authoring CLI. |
| `dashboard/src/capabilities/` | Generic catalogue pane. |
| `migrations/versions/0011_capability_bindings.py` | Retained binding and execution snapshot columns. |

Settings: `ALIVE_CAPABILITY_DIRECTORY` (an extra directory of YAML only),
`ALIVE_DISABLED_CAPABILITIES`, `ALIVE_CAPABILITY_LIMITS` (can only narrow). Changes take effect
on restart.

## Adding a Capability to ALIVE

### A. Reuse an installed implementation (YAML only)

1. Copy `docs/capabilities/capability.template.yaml` to `<id>@<version>.yaml`.
2. Set the identity, description and contracts. Keep `kind`, `side_effects` and `permissions`
   equal to the chosen implementation's; the registry refuses a mismatch.
3. Validate without running anything:

   ```bash
   uv run python -m alive.capabilities validate path/to/context.review@1.0.0.yaml
   ```

   It reports the canonical hash, status, implementation state and whether a workflow can use
   it. A different manifest reusing an existing id and version is reported as a duplicate.
4. Put the file in the directory named by `ALIVE_CAPABILITY_DIRECTORY` and restart ALIVE.
5. Confirm it with `uv run python -m alive.capabilities list` and in the dashboard
   **Capabilities** tab.
6. Reference the operation id from a workflow stage. Optionally pin `capability_version` and
   `capability_sha256` on the stage. No runner, router or dashboard edit is needed.
7. Run it only after an owner grant pins the registered binding.
8. Inspect results in the Workflows observatory; each stage links to its retained identity.

### B. Add new behaviour (needs reviewed code)

1. Write an async function taking the stage context and returning `StageResult`.
2. Register a `TrustedImplementation` in `trusted.py` with its kind, side effects, permission
   ceiling, the `module:function` adapter reference, source files and any traits. The reference
   is part of the implementation's fingerprint. If other code relies on what the implementation
   *is* (a result writer, a model role, an independent validator), express that as a trait and
   check the trait of the stage's retained implementation, never an operation id. This is a code
   review, not a configuration step.
3. Write the manifest as above, with matching permissions.
4. Add tests for the contract and, if it reads or writes anything, for each bound.

### Upgrading, disabling, removing

- Upgrade: add `<id>@<new version>.yaml`. A definition keeps the capability version and hash it resolved when it
  was registered; to use the new one, register a new definition version (or pin the stage).
- Disable: add the id (or `id@version`) to `ALIVE_DISABLED_CAPABILITIES`; pinned runs fail closed.
- Remove: delete the file. History stays readable from the retained snapshot.

## Test commands (fast loop)

```bash
uv run pytest -q tests/test_capability_manifests.py tests/test_capability_registry.py tests/test_capability_hardening.py
uv run pytest -q tests/test_capability_repository.py tests/test_capability_contract_enforcement.py
uv run pytest -q tests/test_capability_resolution.py tests/test_capability_legacy_adoption.py
uv run pytest -q tests/test_capability_registry_authority.py tests/test_capability_reuse_lifecycle.py
uv run pytest -q tests/test_capability_repository_execution.py tests/test_capability_catalog_api.py
uv run pytest -q tests/test_capability_cli.py
npm --prefix dashboard test -- src/capabilities/
npm --prefix dashboard run build
uv run python scripts/capability_mutations.py          # all mutants; --only C1 F9a --merge for a few
```

Platform and database checks (opt in; none run in the fast loop):

```bash
# The pinned Pi must be installed for the Pi-backed workflow suites.
npm ci --ignore-scripts --prefix pi-runtime

# PostgreSQL: a DISPOSABLE EMPTY database (the test refuses one that has tables).
docker run --rm -d --name alive-pg-check -p 55433:5432 -e POSTGRES_PASSWORD=check -e POSTGRES_USER=check -e POSTGRES_DB=check pgvector/pgvector:pg16
ALIVE_TEST_POSTGRES_URL=postgresql+asyncpg://check:check@127.0.0.1:55433/check uv run pytest -q tests/test_capability_postgres.py

# POSIX filesystem behaviour (FIFOs) on Linux, with the repository mounted read-only.
docker run --rm -v "$PWD:/review:ro" -w /review --entrypoint /bin/sh <image> -c "uv pip install --python /app/.venv/bin/python pytest && /app/.venv/bin/python -m pytest -q tests/test_capability_repository.py"
```

`tests/test_capability_repository_execution.py` is the end-to-end demonstration: a hostile
fixture repository, a registered workflow, an exact owner grant, the real `WorkflowRunner`, no
model call, refusal without the grant, refusal after a tampered, disabled or loosened
configuration, history that remains readable, and the event-feed retention checks.
`tests/test_capability_reuse_lifecycle.py` runs every reusable implementation, including the
pinned Pi against a scripted provider, under different capability ids.

Fault injection in tests uses `replace_adapters` (tests/workflow_execution_helpers.py), which
patches the registry class for one test. Production has no override.
