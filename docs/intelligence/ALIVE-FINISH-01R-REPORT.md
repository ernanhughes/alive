# ALIVE-FINISH-01R — Database Target Isolation Hardening

**Status:** implemented and focused-tested; branch pushed for independent review.  
**Decision:** **PASS** — the demonstrated database-target failure is now refused before a
connection or migration. FINISH-02 may proceed; production migration remains a separate
owner-controlled deployment step.  
**Baseline:** `29a44837e7dfa8bb8f202b928b8762f390273310` (`main`, including merged FINISH-01).  
**Tested implementation SHA:** `cbcb034bcd1d4b92141d5caced57dcb8d13af907`.  
**Branch:** `alive-finish-01r-database-guard`.  
**Report date:** 2 November 2026.

No production database was contacted or modified during this milestone. No model calls were
made. The report commit is the final branch HEAD; its exact SHA is recorded in the draft PR.

---

## Executive decision

FINISH-01R closes the specific safety failure that occurred during FINISH-01.

- The effective database target is resolved before Alembic creates an engine.
- Conflicting `DATABASE_URL` / `ALIVE_DSN` sources are refused.
- An inherited environment variable that overrides the worktree `.env` is refused.
- Qualification runs require an explicit disposable target.
- PostgreSQL migrations require an explicit target; production additionally requires an
  approval flag.
- SQLite legacy migrations remain compatible.
- Refusals contain source names and safe target descriptions only; passwords and full URLs
  are never printed.
- The exact inherited-DSN incident is reproduced by a subprocess test and refused before the
  SQLite target file is created.

Focused results:

- **15 database-target guard tests passed.**
- **40 migration/configuration tests passed; 2 opt-in PostgreSQL tests skipped.**
- **157 fast-suite tests passed; 1,836 deselected.**
- Ruff check and format check passed for every changed Python file.

The production database remains at its prior state and was not migrated. FINISH-02 may proceed
on a separate branch; production deployment remains blocked until the owner performs the
separate `0006` → `0015` migration with backup and verification.

---

## Original failure mechanism

During FINISH-01, the worktree `.env` contained a disposable `DATABASE_URL`, but the shell
also inherited `ALIVE_DSN` pointing at the production `alive` database.

The relevant chain was:

1. `alive/config.py` accepts both `DATABASE_URL` and `ALIVE_DSN` as aliases for
   `Settings.database_url`.
2. Process environment values take precedence over values from `.env`.
3. `migrations/env.py` called `Settings().database_url` directly and passed the result to
   `create_async_engine`.
4. Alembic therefore connected to production and applied `0006` → `0015`.
5. Production was manually downgraded back to `0006`; new tables were empty and existing
   retained counts were unchanged.

This milestone makes the resolution step explicit, fail-closed and testable rather than
relying on operator memory or a clean shell.

---

## Files changed

### Production code

| File | Change |
|---|---|
| `alive/db_target.py` | New resolver: source conflict detection, explicit target grammar, qualification/production policy, credential-safe errors |
| `alive/config.py` | New `ALIVE_DB_TARGET`, `ALIVE_QUALIFICATION`, `ALIVE_ALLOW_PRODUCTION_MIGRATION` settings |
| `migrations/env.py` | Resolve and refuse before `create_async_engine`; print safe refusal and exit |

### Configuration and documentation

| File | Change |
|---|---|
| `.env.example` | Adds local disposable target and production-migration guidance |
| `compose.yaml` / `compose.e2e.yaml` | Local composed databases explicitly identify themselves as disposable targets |
| `README.md` | Migration commands now explain the explicit target requirement |
| `docs/DEVELOPMENT.md` | Local and production migration setup |
| `docs/ENVIRONMENT.md` | Migration target safety contract |
| `scripts/intelligence_check.py`, `scripts/workflows_check.py` | Usage text requires an explicit disposable target |

### Tests

| File | Change |
|---|---|
| `tests/test_database_target.py` | New 15-test guard battery, including exact subprocess incident reproduction |
| `tests/conftest.py` | `database_env()` isolates subprocess migrations from inherited DSNs; guard test added to fast set |
| `tests/test_migrations.py`, `tests/test_intelligence_migration.py`, `tests/test_workflow_execution_migration.py` | Use isolated subprocess database environments |
| `tests/test_capability_postgres.py`, `tests/test_source_postgres.py` | Identify their opt-in test database as disposable when invoking Alembic |
| `tests/test_docker_config.py` | Asserts compose migrations identify a disposable target |

No intelligence, model, provider, approval, migration-content or production-data code was
changed.

---

## Protective behavior

### Target sources and conflict detection

The resolver reads all supported URL aliases from both the process environment and the
worktree `.env`:

- `DATABASE_URL`
- `ALIVE_DSN`
- `database_url`

Each source is normalized to a credential-free identity (backend, host, port, database; or
normalized SQLite path). If the sources disagree, the resolver raises
`conflicting_database_targets` before creating an engine. Source names are reported; values and
credentials are not.

This catches the FINISH-01 case: an inherited production `ALIVE_DSN` and a worktree disposable
`DATABASE_URL` cannot both be treated as authoritative.

### Explicit target grammar

```text
ALIVE_DB_TARGET=disposable:<database>
ALIVE_DB_TARGET=production:<database>
```

- `disposable:` is the normal local/dev/test/qualification target.
- `production:` is allowed only when
  `ALIVE_ALLOW_PRODUCTION_MIGRATION=1` is also set.
- The named database must match the effective resolved target.
- `ALIVE_QUALIFICATION=1` requires a `disposable:` target and rejects `production:`. The
  reusable `qualification_database_url()` helper applies the same rule for future
  qualification entry points.

### Fail-closed policy

| Situation | Result |
|---|---|
| SQLite target, no conflict, no explicit target | Allowed for legacy local/test compatibility |
| Non-SQLite target, no explicit target | Refused: `migration_database_target_required` |
| Conflicting environment aliases | Refused: `conflicting_database_targets` |
| Conflicting environment and worktree `.env` | Refused before connection |
| Qualification without an explicit target | Refused: `qualification_database_target_required` |
| Qualification with a production target | Refused: `qualification_requires_disposable_target` |
| Production target without the approval flag | Refused: `production_migration_requires_approval` |
| Production target with exact name and approval | Allowed explicitly |
| Invalid or mismatched target | Refused |

### Credential safety

Refusal messages contain only:

- source names such as `environment:ALIVE_DSN` and `.env:DATABASE_URL`;
- a safe target description such as `postgresql://prod.invalid:5432/alive` without username,
  password, query string or fragment.

The tests include a password-bearing fake URL and assert that the password never appears in
the exception or subprocess stderr.

### Compatibility trade-off

PostgreSQL migrations now require `ALIVE_DB_TARGET`; this is a deliberate, documented safety
change. SQLite migrations remain compatible without a target. Local compose identifies its
database as disposable, so the normal demo path keeps working. A real production migration
must explicitly opt in with both the exact `production:<database>` target and
`ALIVE_ALLOW_PRODUCTION_MIGRATION=1`.

`ALIVE_DSN` remains supported for ordinary application configuration and legacy SQLite
migrations. It is no longer silently authoritative for an unidentified PostgreSQL migration.

---

## Adversarial test results

Command:

```powershell
C:\Projects\alive\.venv\Scripts\python.exe -m pytest -q -o addopts="" `
  tests/test_database_target.py `
  tests/test_migrations.py `
  tests/test_intelligence_migration.py `
  tests/test_workflow_execution_migration.py `
  tests/test_docker_config.py `
  tests/test_capability_postgres.py `
  tests/test_source_postgres.py
```

Result:

```text
40 passed, 2 skipped in 20.68s
```

The two skips are the opt-in PostgreSQL suites, which require an explicit disposable
`ALIVE_TEST_POSTGRES_URL`; no PostgreSQL server was contacted.

`tests/test_database_target.py` includes **15 tests**:

1. Correctly configured disposable SQLite target allowed.
2. Inherited production `ALIVE_DSN` conflicting with disposable `DATABASE_URL` refused.
3. Conflicting environment and worktree `.env` targets refused in qualification mode.
4. Missing explicit qualification target refused.
5. Explicit approved production target allowed; without approval refused.
6. Credentials never printed in refusal.
7. Legacy normal configuration remains compatible.
8. Windows SQLite basename target normalization.
9. Same target under both aliases is allowed.
10. Conflicting explicit `ALIVE_DB_TARGET` sources refused.
11. Non-SQLite target without an explicit identity refused.
12. Disposable target name mismatch refused.
13. Qualification rejects a production target.
14. **Exact incident subprocess:** worktree `.env` disposable plus inherited production
    `ALIVE_DSN` is refused and the SQLite database file is never created.
15. Explicit disposable subprocess migration succeeds to Alembic head.

The fast suite also passed:

```text
157 passed, 1836 deselected in 49.31s
```

Ruff:

```text
ruff check: All checks passed
ruff format --check: all changed files already formatted
git diff --check: clean
```

No production database was contacted by any test. The conflict tests use fake `.invalid`
hosts; the allowed migration tests use disposable temporary SQLite files.

---

## Production / qualification status

- Production was **not** contacted or altered in this milestone.
- The FINISH-01 report records production at Alembic `0006`; that remains the operator's
  separate deployment prerequisite.
- The new guard would refuse an inherited production DSN before any migration.
- A legitimate production migration now requires an exact target and an explicit approval
  flag; it is not silently permitted.
- Qualification callers should use `ALIVE_QUALIFICATION=1` and
  `ALIVE_DB_TARGET=disposable:<database>` (or the `qualification_database_url()` helper).
- Compose uses `ALIVE_DB_TARGET=disposable:<compose db>` for the local demo database. A
  production compose override must change that explicitly.

---

## Unresolved limitations

1. **No production migration performed.** This milestone deliberately does not upgrade
   production from `0006` to `0015`.
2. **The guard is at the migration/qualification entry points.** Normal application runtime
   still connects using `Settings.database_url`; that is intentional, because every app
   start should not require migration-policy configuration. Direct qualification scripts
   that bypass Alembic must call the qualification helper explicitly.
3. **SQLite remains a legacy exception.** Local SQLite migrations do not require an explicit
   target. This preserves the existing unit-test and development workflow; the incident
   involved PostgreSQL.
4. **Explicit target is an operator assertion.** The guard verifies identity matching and
   conflicts; it does not cryptographically attest that a remote host is not production.
5. **Docker was not rebuilt or run.** Compose configuration and entrypoint behavior are
   covered by static tests; a full Docker qualification is a later release gate.
6. **Opt-in PostgreSQL tests were skipped.** They require an explicitly disposable test
   database; no PostgreSQL server was contacted in this milestone.
7. **`ALIVE_DSN` remains an alias.** Runtime compatibility is preserved; the migration path
   refuses ambiguous combinations rather than removing the alias.
8. **Full CI / full backend suite was not run.** Focused configuration, migration, Docker
   configuration and fast suites passed.

---

## FINISH-02 handoff

FINISH-02 may safely proceed on a separate branch. The prerequisite for database-backed
qualification is satisfied: a conflicting inherited DSN is rejected before migration, and an
operator must positively identify the target class and database.

Before production deployment, the owner still needs to:

1. back up production;
2. set `ALIVE_DB_TARGET=production:alive` and
   `ALIVE_ALLOW_PRODUCTION_MIGRATION=1` only for the approved migration window;
3. run the migration and verify the existing data and application;
4. remove the approval flag after the migration.

No merge was performed. The branch and draft PR are ready for independent review.
