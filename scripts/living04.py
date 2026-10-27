"""Bounded two-encounter live qualification with an explicit restart boundary."""

import argparse
import json
import subprocess
import time
from pathlib import Path

import httpx

from alive.config import Settings, prepare_local
from alive.experiment.freeze import file_hash
from alive.living_policy import CONTEXT, digest

PLAN = Path(".alive/alive04-plan.json")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=["first", "second"])
    command = parser.parse_args().command
    c = httpx.Client(
        base_url="http://127.0.0.1:8000/api/v1",
        timeout=60,
        headers={"Authorization": "Bearer " + prepare_local(Settings())},
    )

    def get(path):
        r = c.get(path)
        r.raise_for_status()
        return r.json()

    def post(path, data=None):
        r = c.post(path, json=data or {})
        r.raise_for_status()
        return r.json()

    if command == "first":
        if PLAN.exists():
            raise SystemExit("Qualification plan exists; refusing reset or silent paid replay")
        state = get("/living")
        assert CONTEXT not in state["policy"].get("contexts", {}), (
            "Do not manufacture a cold policy by clearing experience"
        )
        post("/cognition/control", {"command": "pause"})
        plan = {
            "identity": get("/alive")["identity"]["id"],
            "implementation_commit": subprocess.check_output(
                ["git", "rev-parse", "HEAD"], text=True
            ).strip(),
            "source_hashes": {
                p: file_hash(p)
                for p in [
                    "alive/living.py",
                    "alive/living_policy.py",
                    "alive/living_models.py",
                    "alive/living_api.py",
                    "alive/browser.py",
                    "alive/providers.py",
                ]
            },
            "bounds": {"calls": 2, "tokens": 40000, "estimated_usd": 0.15, "browser_operations": 6},
            "initial_policy": state["policy"],
            "no_automatic_retry": True,
        }
        PLAN.write_text(json.dumps(plan, indent=2))
        row = post("/living/journeys", {"provider": "meta", "allow_controlled_read": True})
        plan["journey_id"] = row["id"]
        PLAN.write_text(json.dumps(plan, indent=2))
    else:
        plan = json.loads(PLAN.read_text())
        first = json.loads(Path(".alive/alive04-first.json").read_text())
        current = get("/living/journeys/" + plan["journey_id"])
        assert get("/alive")["identity"]["id"] == plan["identity"]
        assert current["status"] == "ready" and len(current["transitions"]) == 1
        assert len(current["data"]["ledger"]) == 1 and not get("/living")["active"]
        assert digest(current["current_policy"]) == digest(first["current_policy"])
        Path(".alive/alive04-restart-proof.json").write_text(
            json.dumps(
                {
                    "identity_retained": True,
                    "policy_retained": True,
                    "policy_hash": digest(current["current_policy"]),
                    "transition_id": current["transitions"][0]["id"],
                    "no_auto_resume_or_extra_call": True,
                },
                indent=2,
            )
        )
    for path, expected in plan["source_hashes"].items():
        assert file_hash(path) == expected, "Code changed across live qualification"
    journey = plan["journey_id"]
    post("/living/journeys/" + journey + "/advance")
    for _ in range(400):
        row = get("/living/journeys/" + journey)
        if row["status"] != "running" and not get("/living")["active"]:
            break
        time.sleep(0.3)
    else:
        raise SystemExit("Polling deadline; inspect/stop the recorded journey explicitly")
    Path(f".alive/alive04-{command}.json").write_text(json.dumps(row, indent=2))
    if row["status"] not in {"ready", "completed"}:
        raise SystemExit("Recorded run stopped/failed: " + str(row["data"].get("error")))
    transition = row["transitions"][-1]["data"]
    print(
        json.dumps(
            {
                "journey_id": journey,
                "episode": len(row["transitions"]),
                "action": transition["choice"]["action"],
                "reward": transition["reward"],
                "policy_after": row["current_policy"]["version"],
                "reported_tokens": sum(
                    call["usage"]["total_tokens"] for call in row["data"]["ledger"]
                ),
                "estimated_usd": sum(call["estimated_usd"] for call in row["data"]["ledger"]),
            },
            indent=2,
        )
    )
    if command == "second":
        first, second = (t["data"] for t in row["transitions"])
        assert first["state"]["feature_hash"] == second["state"]["feature_hash"]
        assert second["before_hash"] == first["after_hash"]
        assert first["choice"]["action"] == "monitor" and second["choice"]["action"] == "retrieve"
        assert second["initial_policy_counterfactual"]["action"] == "monitor"
        assert second["memory_ids"] == [row["transitions"][0]["id"]]
        assert first["outcome"]["safe_abstention"] and second["outcome"]["resolved"]
        assert all(
            call["provider"] == "meta"
            and call["status"] == "validated"
            and call["usage"]["total_tokens"] > 0
            for call in row["data"]["ledger"]
        )


if __name__ == "__main__":
    main()
