"""Qualification-aware evaluation CLI (ALIVE-EVAL-02). Never executes a model."""

import argparse
import json
from pathlib import Path

from scripts.alive_eval01_custodian import CUSTODIAN_POLICY_PATH
from scripts.alive_eval02_custodian import (
    EVAL02_VERSION,
    TRUST_ANCHORS_PATH,
    evaluate_v2,
    is_qualified_progress,
    load_pinned_bootstrap,
    load_trust_anchors,
    verify_receipt,
)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=["verify", "evaluate", "verify-receipt"])
    parser.add_argument("--package", type=Path)
    parser.add_argument("--gold", type=Path)
    parser.add_argument("--outputs", type=Path)
    parser.add_argument("--custody", type=Path)
    parser.add_argument("--policy", type=Path)
    parser.add_argument("--contract", type=Path)
    parser.add_argument("--protocol-dir", type=Path)
    parser.add_argument("--request", type=Path)
    parser.add_argument("--output", type=Path)
    parser.add_argument("--receipt", type=Path)
    parser.add_argument("--trust-anchors", type=Path)
    parser.add_argument("--pinned-bootstrap", type=Path)
    parser.add_argument("--sealed-root", type=Path)
    args = parser.parse_args()
    extra = {
        "trust_anchors_path": args.trust_anchors,
        "pinned_path": args.pinned_bootstrap,
        "sealed_root": args.sealed_root,
    }
    if args.command == "verify":
        policy = load_pinned_bootstrap(args.pinned_bootstrap) if args.pinned_bootstrap else None
        anchors = load_trust_anchors(args.trust_anchors or TRUST_ANCHORS_PATH)
        print(
            json.dumps(
                {
                    "evaluator": EVAL02_VERSION,
                    "status": "POLICY_VALID",
                    "pinned_bootstrap": policy,
                    "independent_custodians": anchors["independent_custodians"],
                    "qualified_reachable": bool(anchors["independent_custodians"]),
                },
                indent=2,
            )
        )
        return 0
    if args.command == "evaluate":
        for name in ("package", "gold", "outputs", "contract", "protocol_dir", "request"):
            if getattr(args, name) is None:
                raise ValueError(f"evaluate requires --{name.replace('_', '-')}")
        from scripts.alive_eval01_custodian import strict_json_load

        request = strict_json_load(args.request)
        receipt = evaluate_v2(
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
            **extra,
        )
        print(
            json.dumps(
                {k: v for k, v in receipt.items() if k not in ("metrics", "uncertainty")},
                indent=2,
            )
        )
        return 0
    if args.command == "verify-receipt":
        if args.receipt is None:
            raise ValueError("verify-receipt requires --receipt")
        for name in ("package", "gold", "outputs", "contract", "protocol_dir", "request"):
            if getattr(args, name) is None:
                raise ValueError(f"verify-receipt requires --{name.replace('_', '-')}")
        from scripts.alive_eval01_custodian import strict_json_load

        receipt = strict_json_load(args.receipt)
        request = strict_json_load(args.request)
        valid = verify_receipt(
            receipt,
            request,
            {
                "package_dir": args.package,
                "gold_dir": args.gold,
                "outputs_path": args.outputs,
                "custody_dir": args.custody,
                "policy_path": args.policy or CUSTODIAN_POLICY_PATH,
                "contract_path": args.contract,
            },
            **extra,
        )
        print(
            json.dumps(
                {
                    "valid": valid,
                    "qualified_progress": is_qualified_progress(receipt),
                    "custody_state": receipt.get("custody_state"),
                    "verdict": receipt.get("verdict"),
                },
                indent=2,
            )
        )
        return 0
    raise ValueError("unknown command")


if __name__ == "__main__":
    raise SystemExit(main())
