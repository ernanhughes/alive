"""FINISH-01R: migration targets fail closed before any database connection."""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

import pytest

from alive.config import Settings
from alive.db_target import (
    DatabaseTargetError,
    migration_database_url,
    qualification_database_url,
)

ROOT = Path(__file__).resolve().parents[1]
ALIASES = (
    "DATABASE_URL",
    "ALIVE_DSN",
    "database_url",
    "ALIVE_DB_TARGET",
    "ALIVE_QUALIFICATION",
    "ALIVE_ALLOW_PRODUCTION_MIGRATION",
)


def clear_env(monkeypatch):
    for name in ALIASES:
        monkeypatch.delenv(name, raising=False)


def settings_for(url, monkeypatch, **overrides):
    clear_env(monkeypatch)
    return Settings(_env_file=None, database_url=url, **overrides)


def test_sqlite_disposable_is_allowed_without_a_target(tmp_path, monkeypatch):
    db = tmp_path / "legacy.db"
    settings = settings_for(f"sqlite+aiosqlite:///{db.as_posix()}", monkeypatch)
    assert (
        migration_database_url(settings, env_file=tmp_path / "missing.env") == settings.database_url
    )


def test_conflicting_environment_aliases_are_refused_without_credentials(tmp_path, monkeypatch):
    disposable = f"sqlite+aiosqlite:///{(tmp_path / 'disposable.db').as_posix()}"
    monkeypatch.setenv("DATABASE_URL", disposable)
    monkeypatch.setenv("ALIVE_DSN", "postgresql://owner:s3cret@prod.invalid:5432/alive")
    settings = Settings(_env_file=None)

    with pytest.raises(DatabaseTargetError, match="conflicting_database_targets") as refused:
        migration_database_url(settings, env_file=tmp_path / "missing.env")
    message = str(refused.value)
    assert "s3cret" not in message
    assert "prod.invalid" not in message


def test_same_target_under_both_aliases_is_allowed(tmp_path, monkeypatch):
    db = tmp_path / "same.db"
    url = f"sqlite+aiosqlite:///{db.as_posix()}"
    clear_env(monkeypatch)
    monkeypatch.setenv("DATABASE_URL", url)
    monkeypatch.setenv("ALIVE_DSN", url)
    settings = Settings(_env_file=None)
    assert migration_database_url(settings, env_file=tmp_path / "missing.env") == url


def test_worktree_file_and_inherited_environment_conflict_is_refused(tmp_path, monkeypatch):
    disposable = f"sqlite+aiosqlite:///{(tmp_path / 'disposable.db').as_posix()}"
    env_file = tmp_path / ".env"
    env_file.write_text(f"DATABASE_URL={disposable}\n", encoding="utf-8")
    monkeypatch.setenv("ALIVE_DSN", "postgresql://owner:s3cret@prod.invalid:5432/alive")
    monkeypatch.setenv("ALIVE_QUALIFICATION", "1")

    settings = Settings(_env_file=env_file)
    with pytest.raises(DatabaseTargetError, match="conflicting_database_targets") as refused:
        qualification_database_url(settings, env_file=env_file)
    assert "s3cret" not in str(refused.value)


def test_qualification_requires_an_explicit_disposable_target(tmp_path, monkeypatch):
    db = tmp_path / "qual.db"
    settings = settings_for(
        f"sqlite+aiosqlite:///{db.as_posix()}",
        monkeypatch,
        alive_qualification=True,
    )
    with pytest.raises(DatabaseTargetError, match="qualification_database_target_required"):
        qualification_database_url(settings, env_file=tmp_path / "missing.env")


def test_qualification_rejects_a_production_target(tmp_path, monkeypatch):
    settings = settings_for(
        "postgresql://owner:s3cret@prod.invalid:5432/alive",
        monkeypatch,
        alive_db_target="production:alive",
        alive_allow_production_migration=True,
        alive_qualification=True,
    )
    with pytest.raises(DatabaseTargetError, match="qualification_requires_disposable_target"):
        qualification_database_url(settings, env_file=tmp_path / "missing.env")


def test_production_requires_explicit_approval_then_allows(tmp_path, monkeypatch):
    url = "postgresql://owner:s3cret@prod.invalid:5432/alive"
    settings = settings_for(url, monkeypatch, alive_db_target="production:alive")
    with pytest.raises(DatabaseTargetError, match="production_migration_requires_approval"):
        migration_database_url(settings, env_file=tmp_path / "missing.env")

    approved = settings_for(
        url,
        monkeypatch,
        alive_db_target="production:alive",
        alive_allow_production_migration=True,
    )
    assert (
        migration_database_url(approved, env_file=tmp_path / "missing.env") == approved.database_url
    )


def test_disposable_target_must_match_the_effective_database(tmp_path, monkeypatch):
    url = "postgresql://owner:s3cret@prod.invalid:5432/alive_finish01r"
    settings = settings_for(url, monkeypatch, alive_db_target="disposable:other_database")
    with pytest.raises(DatabaseTargetError, match="database_target_mismatch"):
        migration_database_url(settings, env_file=tmp_path / "missing.env")

    matching = settings_for(url, monkeypatch, alive_db_target="disposable:alive_finish01r")
    assert (
        migration_database_url(matching, env_file=tmp_path / "missing.env") == matching.database_url
    )


def test_conflicting_explicit_targets_are_refused(tmp_path, monkeypatch):
    url = "postgresql://owner:s3cret@prod.invalid:5432/alive_finish01r"
    env_file = tmp_path / ".env"
    env_file.write_text("ALIVE_DB_TARGET=production:alive_finish01r\n", encoding="utf-8")
    monkeypatch.setenv("DATABASE_URL", url)
    monkeypatch.setenv("ALIVE_DB_TARGET", "disposable:alive_finish01r")
    monkeypatch.setenv("ALIVE_ALLOW_PRODUCTION_MIGRATION", "1")

    settings = Settings(_env_file=env_file)
    with pytest.raises(DatabaseTargetError, match="conflicting_database_targets") as refused:
        migration_database_url(settings, env_file=env_file)
    assert "s3cret" not in str(refused.value)


def test_non_sqlite_target_requires_an_explicit_identity(tmp_path, monkeypatch):
    settings = settings_for("postgresql://owner:s3cret@prod.invalid:5432/alive", monkeypatch)
    with pytest.raises(DatabaseTargetError, match="migration_database_target_required"):
        migration_database_url(settings, env_file=tmp_path / "missing.env")


def test_windows_sqlite_basename_target_matches(tmp_path, monkeypatch):
    db = tmp_path / "windows.db"
    url = f"sqlite+aiosqlite:///{db.as_posix()}"
    settings = settings_for(url, monkeypatch, alive_db_target=f"disposable:{db.name}")
    assert migration_database_url(settings, env_file=tmp_path / "missing.env") == url


def test_legacy_alive_dsn_still_configures_runtime(tmp_path, monkeypatch):
    db = tmp_path / "legacy-dsn.db"
    url = f"sqlite+aiosqlite:///{db.as_posix()}"
    clear_env(monkeypatch)
    monkeypatch.setenv("ALIVE_DSN", url)
    settings = Settings(_env_file=None)
    assert settings.database_url == url
    assert migration_database_url(settings, env_file=tmp_path / "missing.env") == url


def _alembic_config(tmp_path: Path) -> Path:
    config = tmp_path / "alembic.ini"
    config.write_text(
        "[alembic]\n"
        f"script_location = {(ROOT / 'migrations').as_posix()}\n"
        f"prepend_sys_path = {ROOT.as_posix()}\n",
        encoding="utf-8",
    )
    return config


def test_alembic_refuses_conflicting_targets_before_creating_the_database(tmp_path):
    db = tmp_path / "never-created.db"
    config = _alembic_config(tmp_path)
    env = {key: value for key, value in os.environ.items() if key not in ALIASES}
    env.update(
        {
            "DATABASE_URL": f"sqlite+aiosqlite:///{db.as_posix()}",
            "ALIVE_DSN": "postgresql://owner:s3cret@prod.invalid:5432/alive",
        }
    )
    result = subprocess.run(
        [sys.executable, "-B", "-m", "alembic", "-c", str(config), "upgrade", "head"],
        cwd=tmp_path,
        env=env,
        capture_output=True,
        text=True,
        timeout=120,
    )
    assert result.returncode != 0
    assert "conflicting_database_targets" in result.stderr
    assert "s3cret" not in result.stderr
    assert not db.exists(), "the guard must run before the engine creates the SQLite file"


def test_alembic_refuses_inherited_dsn_over_worktree_env(tmp_path):
    db = tmp_path / "worktree-disposable.db"
    (tmp_path / ".env").write_text(
        f"DATABASE_URL=sqlite+aiosqlite:///{db.as_posix()}\n", encoding="utf-8"
    )
    config = _alembic_config(tmp_path)
    env = {key: value for key, value in os.environ.items() if key not in ALIASES}
    env.update(
        {
            "ALIVE_DSN": "postgresql://owner:s3cret@prod.invalid:5432/alive",
            "ALIVE_QUALIFICATION": "1",
        }
    )
    result = subprocess.run(
        [sys.executable, "-B", "-m", "alembic", "-c", str(config), "upgrade", "head"],
        cwd=tmp_path,
        env=env,
        capture_output=True,
        text=True,
        timeout=120,
    )
    assert result.returncode != 0
    assert "conflicting_database_targets" in result.stderr
    assert "s3cret" not in result.stderr
    assert not db.exists()


def test_alembic_allows_an_explicit_disposable_target(tmp_path):
    db = tmp_path / "allowed.db"
    config = _alembic_config(tmp_path)
    env = {key: value for key, value in os.environ.items() if key not in ALIASES}
    env.update(
        {
            "DATABASE_URL": f"sqlite+aiosqlite:///{db.as_posix()}",
            "ALIVE_DB_TARGET": f"disposable:{db.name}",
            "ALIVE_QUALIFICATION": "1",
        }
    )
    result = subprocess.run(
        [sys.executable, "-B", "-m", "alembic", "-c", str(config), "upgrade", "head"],
        cwd=tmp_path,
        env=env,
        capture_output=True,
        text=True,
        timeout=120,
    )
    assert result.returncode == 0, result.stderr[-2000:]
    assert db.exists()
