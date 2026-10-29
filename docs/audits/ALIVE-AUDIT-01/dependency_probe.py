"""Dependency interruption in the audit-owned PR54 stack only."""
import json
import subprocess
import time
from pathlib import Path

import httpx

OUT = Path(__file__).resolve().parent / "receipts"
CWD = "C:/Projects/alive-audit-01-pr54"
COMMAND = ["docker", "compose", "-p", "alive-audit01-pr54"]

def compose(*args):
    result = subprocess.run([*COMMAND, *args], cwd=CWD, text=True, capture_output=True)
    assert result.returncode == 0, result.stderr

report = {}
try:
    compose("stop", "db")
    with httpx.Client(base_url="http://127.0.0.1:8000", timeout=5,
            headers={"Authorization": "Bearer audit-only-local-token-00000000000000"}) as client:
        for _ in range(30):
            report["health_without_db"] = client.get("/api/v1/health").json()
            if report["health_without_db"]["status"] == "degraded":
                break
            time.sleep(.5)
        report["secured_without_db_status"] = client.get("/api/v1/alive").status_code
        assert report["health_without_db"]["status"] == "degraded"
        assert report["secured_without_db_status"] == 503
finally:
    compose("start", "db")
    compose("restart", "app")
with httpx.Client(base_url="http://127.0.0.1:8000", timeout=5) as client:
    for _ in range(60):
        try:
            report["health_after_restore_restart"] = client.get("/api/v1/health").json()
            if report["health_after_restore_restart"]["status"] == "ok":
                break
        except httpx.HTTPError:
            pass
        time.sleep(.5)
assert report["health_after_restore_restart"]["status"] == "ok"
report["status"] = "PASS"
(OUT / "dependency-failure.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
print(json.dumps(report, indent=2))
