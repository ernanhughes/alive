"""Qualification-aware evaluation CLI (ALIVE-EVAL-02 R2). Never executes a model.

Trust roots are evaluator-pinned constants. This CLI accepts no
--trust-anchors, --pinned-bootstrap, or --sealed-root overrides: qualification
paths must not be redirectable by callers.
"""

import argparse
import json
from pathlib import Path

from scripts.alive_eval01_custodian import CUSTODIAN_POLICY_PATH
from scripts.alive_eval02_custodian import (
    EVAL02_VERSION,
    SEALED_ROOT,
    evaluate_v2,
    is_qualified_progress,
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
    args = parser.parse_args()
    if args.command == "verify":
        anchors = load_trust_anchors()
        sealed_present = any(SEALED_ROOT.glob("*.json")) if SEALED_ROOT.is_dir() else False
        blockers = []
        if not anchors["custodians"]:
            blockers.append("no independent custodians registered")
        if not sealed_present:
            blockers.append("no sealed custody artifacts")
        blockers.append("signature verification backend unavailable")
        print(
            json.dumps(
                {
                    "evaluator": EVAL02_VERSION,
                    "status": "POLICY_VALID",
                    "independent_custodians": sorted(anchors["custodians"]),
                    "qualified_reachable": False,
                    "qualified_blockers": blockers,
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
        verified = verify_receipt(
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
        )
        print(
            json.dumps(
                {
                    "valid": True,
                    "qualified_progress": is_qualified_progress(verified),
                    "custody_state": verified.receipt.get("custody_state"),
                    "verdict": verified.receipt.get("verdict"),
                },
                indent=2,
            )
        )
        return 0
    raise ValueError("unknown command")


if __name__ == "__main__":
    raise SystemExit(main())
