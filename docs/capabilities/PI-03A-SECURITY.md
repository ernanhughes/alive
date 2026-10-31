# PI-03A security model and honest limits

## Trust boundary

Capability implementations are **trusted, reviewed, in-process Python** registered in
`alive/capabilities/trusted.py`. ALIVE does not sandbox them. A manifest line such as
`network: none` is a declaration the registry cross-checks against the implementation's reviewed
ceiling; it does not stop arbitrary Python from opening a socket. The protection is review plus
the fingerprint pin, not isolation. Nothing in PI-03A supports untrusted third-party code, and
nothing should be described as doing so.

What a manifest cannot do:

| Attack | Control |
| --- | --- |
| Name Python to import or a shell command | `implementation.id` is an opaque key into a code-owned dict; `provider` is `builtin` only; unknown keys are refused. |
| YAML code construction, tags, aliases, merge keys, duplicates, bombs | Event-level pre-scan plus a JSON-style loader; size, depth, event and collection ceilings. |
| Interpolation or templating | `${`, `{{`, `{%` refused; no expansion exists. |
| Claim more permission than the code has | Manifest permissions must equal the implementation ceiling. |
| Make a workflow use a different capability later | Per-stage identity and hash retained at registration; grant pins it; execution rechecks it. |
| Pretend a capability is installed | Missing implementation gives `unavailable`, which no run or grant can override. |

## Authorization

Discovery, registration and the catalogue API never authorize execution. A run needs an owner
grant that pins the binding hash and, per stage, the exact identity, permissions, limits,
configuration hash and resources. A grant cannot widen a manifest limit, name an undeclared
capability, or add resources to a capability that cannot use them. The catalogue API has no
write route (tested for POST/PUT/PATCH/DELETE). No HTTP route mints grants.

## Repository inspection

- The stage receives an immutable reader over host-captured, owner-approved content. It holds no
  root path, so there is no traversal surface at execution time.
- Capture (`capture_repository`) is trusted host code and is not exposed through the catalogue.
  It refuses non-canonical paths, duplicates (case-insensitive), symlinks and junctions on the
  root and each component, hardlinked files, non-regular files, oversize files and files that
  change mid-read; omits binary and non-UTF-8 files with a stated reason; and never opens
  secret-looking or `.gitignore`d paths (a test asserts the open call is never made).
- The `.gitignore` reader supports a conservative subset and refuses negation, so a rule can only
  hide more, never re-include a secret.
- **Not an atomic snapshot.** The capture identifies the bytes read. A file may change between the
  host's first and last read; the mtime/size/inode recheck narrows but does not eliminate this.
  Outputs state `atomic_repository_snapshot: false`.
- **Platform coverage.** POSIX uses `O_NOFOLLOW` directory handles; Windows verifies the opened
  handle's final path. Only the Windows branch was exercised on the development host.
- **Retrieval is not verification.** Outputs carry `semantic_status: unverified` and the stage
  reports `validation_status: not_run`.

## Failure semantics

The runner's existing lifecycle governs timeouts, cancellation, persistence failure and the
conservative UNKNOWN state for ambiguous effects. `repository.inspect` has no external effect, so
a failure does not need to mark one possible. Output contract failure produces a failed stage,
never a successful one. Truncation is not performed: oversize output is refused.

## Known limitations (for the reviewer)

1. **No production grant path.** As in PI-02B, owner grants are minted by a controlled fixture
   owner for the synthetic lab. PI-03A does not add a production approval UI or a configured way
   for an operator to approve a repository snapshot; `create_app(capability_registry=...)` is the
   only way to supply snapshots. Without one, `repository.inspect` cannot run.
2. **Configuration changes fail runs closed; they do not migrate them.** The grant pins a
   policy hash covering the effective limits. Editing deployment limits and restarting makes
   pinned, not-yet-finished executions refuse to run; operators must re-approve.
3. **Fingerprint is source-file based.** It covers the listed implementation files, not the full
   transitive import graph or the interpreter.
4. **Version rules are conventions.** The registry enforces identity and hash, not semver
   discipline (see the manifest spec).
5. **Legacy adoption.** PI-02 definitions without pins are adopted under a compatibility path
   that checks the DAG-declared contract at registration (runtime checks both).
6. **Migration 0011** was exercised on SQLite only in this change set.
