import os
import sqlite3
import subprocess
import sys


def test_migration_execution_and_repeat(tmp_path):
    db = tmp_path / "migration.db"
    env = os.environ | {"DATABASE_URL": f"sqlite+aiosqlite:///{db}"}
    for _ in range(2):
        subprocess.run(
            [sys.executable, "-m", "alembic", "upgrade", "head"],
            env=env,
            check=True,
            capture_output=True,
        )
    with sqlite3.connect(db) as connection:
        tables = {
            row[0]
            for row in connection.execute("SELECT name FROM sqlite_master WHERE type='table'")
        }
        assert {
            "alive_instances",
            "events",
            "memories",
            "goals",
            "agent_runs",
            "browser_sessions",
            "runtime_state",
        } <= tables
        assert "web_experiences" in tables
        assert {
            "pi_runs",
            "pi_provider_requests",
            "workflow_capability_bindings",
            "bespoke_recommendations",
            "source_captures",
            "source_approvals",
        } <= tables
        assert connection.execute("SELECT version_num FROM alembic_version").fetchone()[0] == "0013"


def test_pi_migration_downgrades_cleanly_to_0006(tmp_path):
    db = tmp_path / "downgrade.db"
    env = os.environ | {"DATABASE_URL": f"sqlite+aiosqlite:///{db}"}
    for command in (["upgrade", "head"], ["downgrade", "0006"]):
        subprocess.run(
            [sys.executable, "-m", "alembic", *command], env=env, check=True, capture_output=True
        )
    with sqlite3.connect(db) as connection:
        tables = {
            row[0]
            for row in connection.execute("SELECT name FROM sqlite_master WHERE type='table'")
        }
        assert "pi_runs" not in tables and "pi_provider_requests" not in tables
        assert "web_experiences" in tables  # earlier work is untouched
        assert connection.execute("SELECT version_num FROM alembic_version").fetchone()[0] == "0006"


def test_workflow_tables_match_the_models_and_the_migration_downgrades(tmp_path):
    from alive.models import Base
    from alive.workflows import models as workflow_models  # noqa: F401  (registers the tables)

    db = tmp_path / "workflows.db"
    env = os.environ | {"DATABASE_URL": f"sqlite+aiosqlite:///{db}"}

    def alembic(*args):
        subprocess.run(
            [sys.executable, "-m", "alembic", *args], env=env, check=True, capture_output=True
        )

    alembic("upgrade", "head")
    names = ("workflow_definitions", "workflow_runs", "workflow_stage_runs", "workflow_executions")
    with sqlite3.connect(db) as connection:
        for name in names:
            columns = {row[1]: row[3] for row in connection.execute(f"PRAGMA table_info({name})")}
            model = Base.metadata.tables[name]
            assert set(columns) == {c.name for c in model.columns}, name
            # NOT NULL in the migration must match nullability in the model.
            assert {c: bool(notnull) for c, notnull in columns.items() if c != "id"} == {
                c.name: not c.nullable for c in model.columns if c.name != "id"
            }, name
            indexes = {row[1] for row in connection.execute(f"PRAGMA index_list({name})")}
            declared = {i.name for i in model.indexes} | {
                f"ix_{name}_{c.name}" for c in model.columns if c.index
            }
            assert {i for i in declared if i} <= indexes, (name, declared - indexes)
        foreign = {
            (row[2], row[3], row[6])
            for row in connection.execute("PRAGMA foreign_key_list(workflow_runs)")
        }
        assert ("workflow_definitions", "definition_id", "RESTRICT") in foreign
        schema = connection.execute(
            "SELECT sql FROM sqlite_master WHERE name = 'workflow_stage_runs'"
        ).fetchone()[0]
        assert "uq_workflow_stage_attempt" in schema and "ck_workflow_stage_state" in schema
    alembic("downgrade", "0007")
    with sqlite3.connect(db) as connection:
        remaining = {
            row[0]
            for row in connection.execute("SELECT name FROM sqlite_master WHERE type='table'")
        }
        assert not set(names) & remaining
        assert "pi_runs" in remaining  # the previous migration is untouched
        assert connection.execute("SELECT version_num FROM alembic_version").fetchone()[0] == "0007"
    alembic("upgrade", "head")  # and it comes back
