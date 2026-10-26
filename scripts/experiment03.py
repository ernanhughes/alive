"""ALIVE-03-P1 lifecycle. No command automatically proceeds to full paid evaluation."""

import argparse
import json
import time
from pathlib import Path

import httpx

from alive.config import Settings, prepare_local
from alive.experiment.corpus import ROOT, prepare


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "command",
        choices=[
            "prepare",
            "freeze-design",
            "calibrate",
            "freeze-policy",
            "pilot",
            "review",
            "export",
            "authorize-full",
            "full",
        ],
    )
    parser.add_argument("--provider", choices=["mock", "meta"], default="meta")
    parser.add_argument("--run-id")
    parser.add_argument("--authorization-id")
    parser.add_argument("--confirm", default="")
    parser.add_argument("--max-calls", type=int)
    parser.add_argument("--max-tokens", type=int, default=100000)
    args = parser.parse_args()
    if args.command == "prepare":
        if (ROOT / "freeze-design.json").exists():
            raise SystemExit("Corpus already frozen; refusing regeneration")
        print(json.dumps(prepare(), indent=2))
        return
    client = httpx.Client(
        base_url="http://127.0.0.1:8000/api/v1",
        timeout=60,
        headers={"Authorization": "Bearer " + prepare_local(Settings())},
    )

    def post(path, body=None):
        response = client.post(path, json=body or {})
        response.raise_for_status()
        return response.json()

    if args.command == "freeze-design":
        result = post("/experiments/freeze-design")
    elif args.command == "freeze-policy":
        if not args.run_id:
            raise SystemExit("--run-id is required")
        result = post("/experiments/runs/" + args.run_id + "/freeze-policy")
    elif args.command in ["calibrate", "pilot", "full"]:
        final = args.command != "calibrate"
        frozen = json.loads(
            (ROOT / ("freeze-final.json" if final else "freeze-design.json")).read_text()
        )
        phase = "calibration" if args.command == "calibrate" else args.command
        default_calls = {"calibration": 16, "pilot": 12, "full": 360}[phase]
        run = post(
            "/experiments/runs",
            {
                "phase": phase,
                "provider": args.provider,
                "freeze_id": frozen["freeze_id"],
                "max_calls": args.max_calls or default_calls,
                "max_tokens": args.max_tokens,
                "authorization_id": args.authorization_id,
            },
        )
        print("Started:", run["id"], phase, args.provider, flush=True)
        last = -1
        for _ in range(1800):
            response = client.get("/experiments/runs/" + run["id"])
            response.raise_for_status()
            result = response.json()
            count = result["data"]["completed_tasks"]
            if count != last:
                print(
                    "Completed tasks:",
                    count,
                    "calls:",
                    result["data"]["physical_calls"],
                    flush=True,
                )
                last = count
            if result["status"] != "running":
                break
            time.sleep(0.5)
        else:
            raise SystemExit(
                "Polling deadline reached; inspect/cancel the persisted run explicitly"
            )
        Path(".alive").mkdir(exist_ok=True)
        (Path(".alive") / f"experiment03-{phase}-{run['id']}.json").write_text(
            json.dumps(result, indent=2, default=str)
        )
        print("Status:", result["status"], "error:", result["data"].get("error"), flush=True)
        print("Summary:", json.dumps(result["data"].get("summary"), indent=2), flush=True)
        return
    elif args.command == "review":
        result = client.get("/experiments/review-pack").json()
        Path(".alive/experiment03-review-pack.json").write_text(json.dumps(result, indent=2))
    elif args.command == "export":
        if not args.run_id:
            raise SystemExit("--run-id is required")
        result = client.get("/experiments/runs/" + args.run_id).json()
        Path(f".alive/experiment03-{args.run_id}.json").write_text(json.dumps(result, indent=2))
    elif args.command == "authorize-full":
        frozen = json.loads((ROOT / "freeze-final.json").read_text())
        result = post(
            "/experiments/authorize-full",
            {
                "freeze_id": frozen["freeze_id"],
                "confirmation": args.confirm,
                "max_calls": args.max_calls or 360,
                "max_tokens": args.max_tokens,
                "session_plan": "TWO_60_TASK_SESSIONS",
            },
        )
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
