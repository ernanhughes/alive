"""Execute the owner-authorized, unchanged 120-task experiment once, without retries."""

import argparse
import json
import subprocess
import time
from pathlib import Path

import httpx

from alive.config import Settings, prepare_local
from alive.experiment.freeze import ROOT, file_hash, verify


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--execute-authorized", action="store_true", required=True)
    parser.parse_args()
    archived = Path("archives/ALIVE-03-P1")
    frozen = json.loads((archived / "freeze-final.json").read_text())
    verify(frozen["freeze_id"])
    for name in [
        "freeze-final.json",
        "policy-configuration.json",
        "evaluation.sealed.json",
        "calibration.json",
        "split-manifest.json",
        "calibration-evidence.json",
    ]:
        assert file_hash(ROOT / name) == file_hash(archived / name), name
    c = httpx.Client(
        base_url="http://127.0.0.1:8000/api/v1",
        timeout=60,
        headers={"Authorization": "Bearer " + prepare_local(Settings())},
    )

    def get(path):
        r = c.get(path)
        r.raise_for_status()
        return r.json()

    def post(path, data):
        r = c.post(path, json=data)
        r.raise_for_status()
        return r.json()

    assert not get("/experiments/review-pack")["full_run_executed"], "No automatic second run"
    before = get("/cognition")["control"]
    post("/cognition/control", {"command": "pause"})
    cfg = before["configuration"] | {
        "session_calls": 180,
        "session_tokens": 500000,
        "experiment_calls": before["spent"].get("experiment_calls", 0) + 350,
        "experiment_tokens": before["spent"].get("experiment_tokens", 0) + 500000,
    }
    post("/cognition/configuration", cfg)
    plan = {
        "owner_authorized": True,
        "maximum_usd": 1.0,
        "maximum_calls": 350,
        "maximum_tokens": 500000,
        "freeze_id": frozen["freeze_id"],
        "execution_commit": subprocess.check_output(
            ["git", "rev-parse", "HEAD"], text=True
        ).strip(),
        "execution_overlay": {
            p: file_hash(p)
            for p in ["alive/experiment_budget.py", "alive/app.py", "scripts/run_frozen03.py"]
        },
        "budget_before": before["spent"],
        "governor_configuration": cfg,
        "experimental_specification_changed": False,
        "pricing_source": "https://dev.meta.ai/docs/pricing-rate-limits",
        "retry_policy": "No retries; preserve errors and stop at the first applicable ceiling",
    }
    plan_path = Path(".alive/full-evaluation-plan.json")
    plan_path.write_text(json.dumps(plan, indent=2))
    authorization = post(
        "/experiments/authorize-full",
        {
            "freeze_id": frozen["freeze_id"],
            "confirmation": "AUTHORIZE FROZEN 120 TASK META EVALUATION",
            "max_calls": 350,
            "max_tokens": 500000,
            "session_plan": "TWO_60_TASK_SESSIONS",
        },
    )
    plan["authorization"] = authorization
    plan_path.write_text(json.dumps(plan, indent=2))
    run = post(
        "/experiments/runs",
        {
            "phase": "full",
            "provider": "meta",
            "freeze_id": frozen["freeze_id"],
            "max_calls": 350,
            "max_tokens": 500000,
            "authorization_id": authorization["id"],
        },
    )
    plan["run_id"] = run["id"]
    plan_path.write_text(json.dumps(plan, indent=2))
    print("Started full evaluation", run["id"], flush=True)
    last = -1
    while True:
        result = get("/experiments/runs/" + run["id"])
        data = result["data"]
        if data["completed_tasks"] != last:
            last = data["completed_tasks"]
            print(
                f"{last}/120 tasks; {data['physical_calls']} calls; "
                f"{data['charged_tokens']} charged/reserved tokens",
                flush=True,
            )
        if result["status"] != "running":
            Path(".alive/full-evaluation-result.json").write_text(json.dumps(result, indent=2))
            print("Final status:", result["status"], "error:", data.get("error"), flush=True)
            break
        time.sleep(1)


if __name__ == "__main__":
    main()
