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

## Retention and who can read it (F9)

`persistence` in a manifest means one thing: **whether the capability may create a
`workflow_result` artifact through the existing writer.** It never meant "no output is stored".

- The runner always keeps each stage's output in the database (the `workflow.stage.result`
  event) because dependent stages, hashing and replay need it. For `repository.inspect` that
  includes the approved file content. Treat run history as owner-internal evidence with the same
  sensitivity as the repository content that was approved.
- The generic event feed (`GET /api/v1/events`, the `/api/v1/events/stream` WebSocket and the
  live publish) now carries only `{run_id, stage_id, output_withheld: true}` for that event type
  and is scoped to the current instance. Before this change it returned raw payloads for every
  instance. The observatory projections already withheld outputs.
- Not changed, and worth a separate decision: other event types still carry their payloads on the
  generic feed (for example the fixture context event), the feed is not role-scoped (any holder
  of the API token reads it), and no retention period or deletion path exists for run history.

## Implementation identity (F2, F18)

The fingerprint covers an implementation's id, interface, kind, side effects, adapter reference,
legacy binding, permission ceiling, traits, source-file list and the normalised bytes of those
files. It is **not transitive**: code reached through imports is covered only if listed. The
legacy implementations now list `alive/workflows/context.py` (record uses `digest` and `bounded`)
along with `adapters.py`, `society.py` and `cognitive_schema.py`. Still outside it: `alive/models.py`
(`now`), `alive/pi/*`, `alive/cognition.py` and the interpreter and third-party packages. A change
there does not change an implementation's identity. The review boundary is the listed files.

## POSIX capture (F3)

Files are opened `O_NONBLOCK | O_NOFOLLOW | O_NOCTTY`, so a FIFO or device is refused by the
regular-file check instead of blocking capture, for requested paths and for `.gitignore`. A
`.gitignore` that is oversize or not a regular file fails capture closed with a named reason,
because skipping it could expose files it hides. Linux regression tests use a real FIFO in a child
process with a hard timeout (a hang fails the test). Windows reserved device names are refused as
paths on every platform.

## Decisions taken on review findings

- **F14 (stale disable entry stops startup): accepted as designed.** Ignoring an unknown id
  would let a typo leave a capability enabled while the operator believes it disabled. The error
  now names the entry and the remedy.
- **F17 (repository capabilities get a narrower context): accepted.** `ReadCapabilityContext`
  deliberately omits the kernel, cognition and ledger. A source capability that also needs its
  stage inputs needs a documented `repository-context/v1`; that belongs to PI-03B.
- **F19 (no production snapshot approval): unchanged.** PI-03B prerequisite.

## Known limitations

1. **No production grant path.** Owner grants are minted by the controlled fixture owner for the
   synthetic lab. There is no operator approval UI or configured way to approve a repository
   snapshot; `create_app(capability_registry=...)` is the only way to supply snapshots.
2. **Configuration changes fail runs closed; they do not migrate them.** The grant pins a policy
   hash covering the effective limits.
3. **Fingerprints are not transitive** (see above).
4. **Version rules are conventions.** The registry enforces identity and hash, not semver.
5. **Two shipped definitions use the PI-02 contract**, by exact hash, until re-issued.
6. **No retention period or deletion path for run history.**
7. **Downgrading migration 0011 discards the retained bindings and snapshots by design.** The
   executions, runs and definitions survive; the runs are then read as unlabelled history.
