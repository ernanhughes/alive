"""Reproduce ALIVE-REVIEW-10 defects against the merged ALIVE-14-R3 code.

Run before the R4 corrections. Uses temporary databases, a local provider and no
external calls. The revocation case deliberately exercises the runner's grant
re-activation path after an owner revocation made while a grant is in the
restart-suspended state.
"""

import json
import os
import shutil
from pathlib import Path

import scripts.alive14r3_experiment as runner
from alive.providers import ProviderError
from alive.research_relationships import MetaProvider

ROOT = Path(__file__).resolve().parents[1]
WORK = ROOT / ".alive/alive14r4-prefix"
EVIDENCE = ROOT / "archives/ALIVE-14-R4/evidence/review10-prefix.json"


def make_approval(state):
    return {
        "run_id": state["run_id"],
        "protocol_sha256": state["protocol_sha256"],
        "provider": "meta",
        "model": state["model"],
        "task_count": len(state["tasks"]),
        "calls": state["totals"]["calls"],
        "payload_sha256s": {row["task_id"]: row["payload_sha256s"] for row in state["tasks"]},
        "max_input_tokens": state["totals"]["reserved_tokens"],
        "max_output_tokens": 1536,
        "max_usd": 0.45,
        "no_retries": True,
        "human_approval": True,
        "approved_by": "prefix-reproduction",
        "approved_at": state["created_at"],
    }


def revocation_reproduction():
    synthetic_root = WORK / "revocation"
    runner.RUNS = synthetic_root / "runs"
    runner.ARCHIVE = synthetic_root / "archive"
    state = runner.prepare("synthetic")
    runner.approve("synthetic", synthetic=True)
    directory = runner.run_dir("synthetic", runner.verify_protocol_identity())
    token = (directory / "api-token.txt").read_text(encoding="utf-8").strip()
    settings = runner.build_settings(
        "synthetic", runner.verify_protocol_identity(), directory, token
    )
    task = state["tasks"][0]
    # A fresh client represents a restart: startup moves active grants to
    # revoked_restart. The owner then revokes while the grant is suspended.
    with runner.Client(settings, token) as client:
        runner.call(client, "POST", f"/grants/{task['grant_id']}/revoke", {})
        inventory = runner.call(client, "GET", "/research/blind/runs")

        async def status():
            async with client.app.state.kernel.db.sessions() as session:
                grant = await session.get(runner.WebExperience, task["grant_id"])
                return grant.status, grant.data

        status_after_revoke, grant_data = client.portal.call(status)
    # Execution opens a new client (another restart) and re-activates the grant.
    result = runner.execute("synthetic")
    with runner.Client(settings, token) as client:

        async def status_after_execute():
            async with client.app.state.kernel.db.sessions() as session:
                grant = await session.get(runner.WebExperience, task["grant_id"])
                return grant.status, grant.data

        status_after_execute_value, execute_data = client.portal.call(status_after_execute)
    return {
        "grant_id": task["grant_id"],
        "status_after_explicit_owner_revoke": status_after_revoke,
        "owner_revoked_flag": grant_data.get("owner_revoked"),
        "status_after_runner_execute": status_after_execute_value,
        "reactivated_for_run": execute_data.get("reactivated_for_run"),
        "execution_phase": result["phase"],
        "explicit_revocation_survived": status_after_revoke == "revoked",
        "defect_confirmed": (
            status_after_revoke != "revoked"
            and execute_data.get("reactivated_for_run") == state["run_id"]
        ),
        "runner_completed_all_cells_after_revoke": result["phase"]
        in ("awaiting_ratings", "staged"),
        "blind_runs_visible_before_ratings": len(inventory["runs"]),
    }


def provider_failure_reproduction():
    failure_root = WORK / "provider"
    runner.RUNS = failure_root / "runs"
    runner.ARCHIVE = failure_root / "archive"
    os.environ["ALIVE_META_API_KEY"] = "prefix-no-network"
    state = runner.prepare("real")
    directory = runner.run_dir("real", runner.verify_protocol_identity())
    approval_path = directory / "prefix-approval.json"
    approval_path.write_text(json.dumps(make_approval(state), indent=2), encoding="utf-8")
    runner.approve("real", approval_file=str(approval_path))
    calls = []

    async def fail_401(self, *args, **kwargs):
        calls.append(kwargs.get("correlation"))
        raise ProviderError("authentication", 401)

    original = MetaProvider.structured
    MetaProvider.structured = fail_401
    try:
        result = runner.execute("real")
    finally:
        MetaProvider.structured = original
    outputs = runner.read_jsonl(directory / "outputs.jsonl")
    return {
        "attempted_calls": len(calls),
        "total_cells": len(state["tasks"]) * 2,
        "undispatched_cells": len(state["tasks"]) * 2 - len(calls),
        "phase": result["phase"],
        "outputs_recorded": len(outputs),
        "all_cells_recorded_as_failed": all(row["status"] == "failed" for row in outputs),
        "defect_confirmed": len(calls) == len(state["tasks"]) * 2,
    }


def main():
    if WORK.exists():
        shutil.rmtree(WORK)
    WORK.mkdir(parents=True)
    evidence = {
        "baseline": "ac11be81115f397a9bad9f5c630a74ee22bdc3d2",
        "provider": "local_stub and monkeypatched 401",
        "paid_calls": 0,
        "defects": {},
    }
    evidence["defects"]["owner_revocation_durability"] = revocation_reproduction()
    # Reset module globals before the second reproduction.
    evidence["defects"]["systematic_provider_failure"] = provider_failure_reproduction()
    EVIDENCE.parent.mkdir(parents=True, exist_ok=True)
    EVIDENCE.write_text(json.dumps(evidence, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(evidence, indent=2))
    print(EVIDENCE)


if __name__ == "__main__":
    main()
