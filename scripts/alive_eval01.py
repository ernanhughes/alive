"""Offline trusted-custody CLI (ALIVE-EVAL-01). Never executes a model."""

import argparse
import json
from pathlib import Path

from scripts.alive_eval01_custodian import (
    CUSTODIAN_POLICY_PATH,
    EVAL01_VERSION,
    evaluate,
    load_custodian_policy,
    strict_json_load,
)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=["verify", "evaluate"])
    parser.add_argument("--package", type=Path)
    parser.add_argument("--gold", type=Path)
    parser.add_argument("--outputs", type=Path)
    parser.add_argument("--custody", type=Path)
    parser.add_argument("--policy", type=Path)
    parser.add_argument("--contract", type=Path)
    parser.add_argument("--protocol-dir", type=Path)
    parser.add_argument("--request", type=Path)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    if args.command == "verify":
        policy = load_custodian_policy(args.policy or CUSTODIAN_POLICY_PATH)
        print(
            json.dumps(
                {
                    "evaluator": EVAL01_VERSION,
                    "policy": policy.get("version"),
                    "status": "POLICY_VALID",
                },
                indent=2,
            )
        )
        return 0
    if args.command == "evaluate":
        for name in ("package", "gold", "outputs", "contract", "protocol_dir", "request"):
            if getattr(args, name) is None:
                raise ValueError(f"evaluate requires --{name.replace('_', '-')}")
        request = strict_json_load(args.request)
        receipt = evaluate(
            request,
            {
                "package_dir": args.package,
                "gold_dir": args.gold,
                "outputs_path": args.outputs,
                "custody_dir": args.custody,
                "output_path": args.output,
                "policy_path": args.policy or CUSTODIAN_POLICY_PATH,
                "contract_path": args.contract,
            },
        )
        print(
            json.dumps(
                {k: v for k, v in receipt.items() if k not in ("metrics", "uncertainty")}, indent=2
            )
        )
        return 0
    raise ValueError("unknown command")


if __name__ == "__main__":
    raise SystemExit(main())
