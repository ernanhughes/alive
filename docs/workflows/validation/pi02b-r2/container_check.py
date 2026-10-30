"""Qualification only: restart the task-owned Docker app and compare retained API bytes."""

import json
import os
import subprocess
import time
from pathlib import Path

import httpx


def command(*args):
    return subprocess.check_output(args, text=True).strip()


def counts():
    tables = (
        "workflow_runs",
        "workflow_stage_runs",
        "workflow_executions",
        "model_invocations",
        "pi_runs",
        "pi_provider_requests",
        "cognitive_messages",
        "intelligence_learning_updates",
    )
    query = " union all ".join(f"select '{name}', count(*) from {name}" for name in tables)
    return command(
        "docker",
        "exec",
        "alive-pi02b-r2-db",
        "psql",
        "-U",
        "pi02br2",
        "-d",
        "pi02br2_docker",
        "-Atc",
        query,
    )


def main():
    receipt = json.loads(Path(".r2-docker-workflows-lf.log").read_text(encoding="utf-8-sig"))
    headers = {"Authorization": "Bearer " + os.environ["ALIVE_API_TOKEN"]}
    with httpx.Client(base_url="http://127.0.0.1:18049", headers=headers) as client:

        def views():
            result = []
            for workflow in receipt["workflows"]:
                run_id = workflow["run"]["id"]
                for suffix in ("", "/stages", "/artifacts/record"):
                    response = client.get(f"/api/v1/workflow-runs/{run_id}{suffix}")
                    response.raise_for_status()
                    result.append(response.content)
            return result

        before = views()
        before_counts = counts()
        command("docker", "restart", "alive-pi02b-r2-app")
        for _ in range(60):
            try:
                if client.get("/api/v1/health").json().get("status") == "ok":
                    break
            except (httpx.HTTPError, ValueError):
                pass
            time.sleep(0.5)
        else:
            raise AssertionError("container did not become ready")
        for _ in range(3):
            assert views() == before
        assert counts() == before_counts
    print(
        json.dumps(
            {
                "status": "PASS",
                "actual_container_restart": True,
                "unchanged_api_bodies": len(before),
                "replay_passes": 3,
                "durable_counts": before_counts.splitlines(),
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
