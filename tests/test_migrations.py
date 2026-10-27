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
        assert connection.execute("SELECT version_num FROM alembic_version").fetchone()[0] == "0006"
