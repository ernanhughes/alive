import os
import sqlite3
import subprocess
import sys

from alive.intelligence.models import IntelligenceEpisode  # registers all five tables
from alive.models import Base


def test_intelligence_migration_parity_and_reversible_upgrade(tmp_path):
    path = tmp_path / "intelligence-migration.db"
    env = os.environ | {"DATABASE_URL": f"sqlite+aiosqlite:///{path}"}

    def migrate(*args):
        subprocess.run(
            [sys.executable, "-B", "-m", "alembic", *args], env=env, check=True, capture_output=True
        )

    migrate("upgrade", "head")
    names = [name for name in Base.metadata.tables if name.startswith("intelligence_")]
    assert len(names) == 5 and IntelligenceEpisode.__tablename__ in names
    with sqlite3.connect(path) as connection:
        for name in names:
            columns = {row[1]: row[3] for row in connection.execute(f"PRAGMA table_info({name})")}
            model = Base.metadata.tables[name]
            assert set(columns) == {c.name for c in model.columns}
            assert {n: bool(v) for n, v in columns.items() if n != "id"} == {
                c.name: not c.nullable for c in model.columns if c.name != "id"
            }
        assert connection.execute("SELECT version_num FROM alembic_version").fetchone()[0] == "0015"
    migrate("downgrade", "0008")
    with sqlite3.connect(path) as connection:
        remaining = {
            r[0] for r in connection.execute("SELECT name FROM sqlite_master WHERE type='table'")
        }
        assert not set(names) & remaining
        assert "workflow_stage_runs" in remaining and "pi_runs" in remaining
    migrate("upgrade", "head")
