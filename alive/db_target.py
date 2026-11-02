"""Fail-closed database-target resolution for migrations and qualification.

The FINISH-01 incident happened because a process-level ``ALIVE_DSN`` (production)
overrode a worktree ``.env`` ``DATABASE_URL`` (disposable). This module resolves the
effective target and refuses before any engine is created when the sources disagree
or when a non-SQLite target was not positively identified.

Normal application startup keeps using ``Settings.database_url`` unchanged. The
guard is intentionally limited to migration and qualification entry points.

Target grammar::

    ALIVE_DB_TARGET=disposable:<database>   # local/dev/test/qualification
    ALIVE_DB_TARGET=production:<database>   # requires the explicit approval flag

``ALIVE_QUALIFICATION=1`` requires a disposable target. Production migrations also
require ``ALIVE_ALLOW_PRODUCTION_MIGRATION=1``. SQLite remains compatible without a
target so existing unit tests and local SQLite workflows keep working.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import dotenv_values
from sqlalchemy.engine import URL, make_url

TARGET_ENV = "ALIVE_DB_TARGET"
QUALIFICATION_ENV = "ALIVE_QUALIFICATION"
PRODUCTION_APPROVAL_ENV = "ALIVE_ALLOW_PRODUCTION_MIGRATION"
ALIASES = ("DATABASE_URL", "ALIVE_DSN", "database_url")
TARGET_PREFIXES = ("disposable", "production")


class DatabaseTargetError(ValueError):
    """A safe refusal. Messages never contain credentials or full URLs."""

    def __init__(self, code: str, detail: str = ""):
        self.code = code
        super().__init__(code + (f": {detail}" if detail else ""))


@dataclass(frozen=True)
class _Candidate:
    source: str
    value: str


def _truthy(value: object) -> bool:
    return str(value or "").strip().lower() in {"1", "true", "yes", "on"}


def _file_values(env_file: str | Path) -> dict[str, str]:
    path = Path(env_file)
    if not path.is_file():
        return {}
    try:
        values = dotenv_values(path)
    except (OSError, ValueError):
        raise DatabaseTargetError("database_configuration_unreadable") from None
    return {str(key): str(value) for key, value in values.items() if value is not None}


def _candidates(env_file: str | Path) -> list[_Candidate]:
    file_values = _file_values(env_file)
    found: list[_Candidate] = []
    for name in ALIASES:
        for source, mapping in (("environment", os.environ), (".env", file_values)):
            value = str(mapping.get(name) or "").strip()
            if value:
                found.append(_Candidate(f"{source}:{name}", value))
    return found


def _url(value: str) -> URL:
    try:
        return make_url(value)
    except Exception:
        raise DatabaseTargetError("invalid_database_target") from None


def _default_port(backend: str) -> int | None:
    return {"postgresql": 5432, "mysql": 3306}.get(backend)


def _canonical(url: URL) -> tuple[object, ...]:
    backend = url.get_backend_name()
    if backend == "sqlite":
        database = url.database or ":memory:"
        if database == ":memory:":
            return ("sqlite", ":memory:")
        return ("sqlite", os.path.normcase(os.path.normpath(database)))
    return (
        backend,
        (url.host or "").lower(),
        url.port or _default_port(backend),
        (url.database or "").lower(),
    )


def _safe_target(url: URL) -> str:
    backend = url.get_backend_name()
    if backend == "sqlite":
        database = url.database or ":memory:"
        name = database if database == ":memory:" else Path(database).name
        return f"sqlite:{name}"
    return (
        f"{backend}://{url.host or '?'}:{url.port or _default_port(backend)}/{url.database or '?'}"
    )


def _source_detail(candidates: list[_Candidate]) -> str:
    # Source names only. Never include the values or credentials.
    return ", ".join(sorted({candidate.source for candidate in candidates}))


def _target_values(env_file: str | Path) -> list[_Candidate]:
    file_values = _file_values(env_file)
    found: list[_Candidate] = []
    for source, mapping in (("environment", os.environ), (".env", file_values)):
        value = str(mapping.get(TARGET_ENV) or "").strip()
        if value:
            found.append(_Candidate(f"{source}:{TARGET_ENV}", value))
    return found


def _explicit_target(settings) -> tuple[str, str] | None:
    value = str(getattr(settings, "alive_db_target", "") or "").strip()
    if not value:
        return None
    prefix, separator, name = value.partition(":")
    name = name.strip()
    if not separator or prefix.lower() not in TARGET_PREFIXES or not name:
        raise DatabaseTargetError("invalid_database_target")
    return prefix.lower(), name


def _matches_target(url: URL, name: str) -> bool:
    backend = url.get_backend_name()
    if backend == "sqlite":
        actual = url.database or ":memory:"
        if actual == ":memory:":
            return name == ":memory:"
        expected = os.path.normcase(os.path.normpath(name))
        full = os.path.normcase(os.path.normpath(actual))
        return expected == full or expected == os.path.basename(full)
    return name.lower() == (url.database or "").lower()


def resolve_database_target(
    settings,
    *,
    env_file: str | Path = ".env",
    qualification: bool | None = None,
) -> str:
    """Return the effective URL or raise ``DatabaseTargetError`` before any connection.

    ``qualification=True`` (or ``ALIVE_QUALIFICATION`` on the settings) requires an
    explicit disposable target. Every non-SQLite target requires an explicit target,
    so an inherited production DSN cannot silently authorize a migration.
    """
    candidates = _candidates(env_file)
    effective = _url(str(settings.database_url))
    effective_key = _canonical(effective)

    distinct = {_canonical(_url(candidate.value)) for candidate in candidates}
    if len(distinct) > 1:
        raise DatabaseTargetError(
            "conflicting_database_targets",
            f"sources disagree ({_source_detail(candidates)}); refusing before connection",
        )
    if distinct and effective_key not in distinct:
        raise DatabaseTargetError(
            "database_target_override",
            f"resolved target differs from its sources ({_source_detail(candidates)})",
        )

    target_sources = _target_values(env_file)
    target_identities = {
        tuple(part.strip().lower() for part in candidate.value.partition(":")[::2])
        for candidate in target_sources
    }
    if len(target_identities) > 1:
        raise DatabaseTargetError(
            "conflicting_database_targets",
            f"explicit target sources disagree ({_source_detail(target_sources)})",
        )
    explicit = _explicit_target(settings)
    in_qualification = (
        bool(qualification)
        if qualification is not None
        else bool(getattr(settings, "alive_qualification", False))
    )

    if explicit is None:
        if in_qualification:
            raise DatabaseTargetError(
                "qualification_database_target_required",
                "set ALIVE_DB_TARGET=disposable:<database>",
            )
        if effective.get_backend_name() == "sqlite":
            return str(settings.database_url)
        raise DatabaseTargetError(
            "migration_database_target_required",
            f"non-SQLite migration target {_safe_target(effective)} needs "
            "ALIVE_DB_TARGET=disposable:<database> or production:<database>",
        )

    prefix, name = explicit
    if not _matches_target(effective, name):
        raise DatabaseTargetError(
            "database_target_mismatch",
            f"ALIVE_DB_TARGET does not identify the effective target {_safe_target(effective)}",
        )
    if in_qualification and prefix != "disposable":
        raise DatabaseTargetError(
            "qualification_requires_disposable_target",
            "qualification runs may not use a production target",
        )
    if prefix == "production" and not bool(
        getattr(settings, "alive_allow_production_migration", False)
    ):
        raise DatabaseTargetError(
            "production_migration_requires_approval",
            f"set {PRODUCTION_APPROVAL_ENV}=1 only for an approved production migration",
        )
    return str(settings.database_url)


def migration_database_url(settings, *, env_file: str | Path = ".env") -> str:
    """Resolve the target for an Alembic migration. No connection is opened here."""
    return resolve_database_target(settings, env_file=env_file)


def qualification_database_url(settings, *, env_file: str | Path = ".env") -> str:
    """Resolve a qualification target, requiring an explicit disposable identity."""
    return resolve_database_target(settings, env_file=env_file, qualification=True)


__all__ = [
    "DatabaseTargetError",
    "migration_database_url",
    "qualification_database_url",
    "resolve_database_target",
]
