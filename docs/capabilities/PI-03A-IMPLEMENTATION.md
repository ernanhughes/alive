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
   ceiling, adapter name and source files. This is a code review, not a configuration step.
3. Write the manifest as above, with matching permissions.
4. Add tests for the contract and, if it reads or writes anything, for each bound.

### Upgrading, disabling, removing

- Upgrade: add `<id>@<new version>.yaml`. A definition keeps the capability version and hash it resolved when it
  was registered; to use the new one, register a new definition version (or pin the stage).
- Disable: add the id (or `id@version`) to `ALIVE_DISABLED_CAPABILITIES`; pinned runs fail closed.
- Remove: delete the file. History stays readable from the retained snapshot.

## Test commands (fast loop)

```bash
uv run pytest -q tests/test_capability_manifests.py tests/test_capability_registry.py
uv run pytest -q tests/test_capability_repository.py tests/test_capability_contract_enforcement.py
uv run pytest -q tests/test_capability_repository_execution.py tests/test_capability_catalog_api.py
uv run pytest -q tests/test_capability_cli.py
npm --prefix dashboard test -- src/capabilities/
npm --prefix dashboard run build
uv run python scripts/capability_mutations.py
```

`tests/test_capability_repository_execution.py` is the end-to-end demonstration: a hostile
fixture repository, a registered workflow, an exact owner grant, the real `WorkflowRunner`, no
model call, refusal without the grant, refusal after a tampered or disabled catalogue, and
history that remains readable afterwards.
