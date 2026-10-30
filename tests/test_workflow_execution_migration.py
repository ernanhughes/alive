import os
import sqlite3
import subprocess
import sys


def test_upgrade_requires_review_of_old_dangling_pi_references(tmp_path):
    path = tmp_path / "historical.db"
    environment = os.environ | {"DATABASE_URL": f"sqlite+aiosqlite:///{path}"}
    command = [sys.executable, "-B", "-m", "alembic"]
    subprocess.run(command + ["upgrade", "0009"], env=environment, check=True, capture_output=True)
    # A deliberately unqualified historical PI-02A reference. The migration must refuse
    # before any new DDL and must never rewrite the historical claim into a real receipt.
    with sqlite3.connect(path) as connection:
        connection.execute("""INSERT INTO workflow_stage_runs
            (id, run_id, stage_id, attempt, stage_type, operation, state, pi_run_id,
             evidence_refs, validation_status, uncertainty, created_at)
            VALUES ('old-stage', 'historical-run', 'reason', 1, 'pi_agent', 'cognition.role',
                    'PENDING', 'unresolved-receipt', '[]', 'not_run', 'none', CURRENT_TIMESTAMP)""")
    result = subprocess.run(
        command + ["upgrade", "head"], env=environment, capture_output=True, text=True
    )
    assert result.returncode != 0
    assert "Reconcile historical dangling workflow Pi references" in result.stderr
    with sqlite3.connect(path) as connection:
        assert connection.execute("SELECT version_num FROM alembic_version").fetchone()[0] == "0009"
        assert (
            connection.execute("SELECT pi_run_id FROM workflow_stage_runs").fetchone()[0]
            == "unresolved-receipt"
        )
        assert not connection.execute(
            "SELECT name FROM sqlite_master WHERE name='workflow_executions'"
        ).fetchall()
