"""Freeze or execute the simulation-only ALIVE-03-P2 learning qualification."""

import argparse
import json

from alive.learning.experiment import freeze, run, verify


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=["freeze", "verify", "run"])
    args = parser.parse_args()
    result = (
        freeze() if args.command == "freeze" else verify() if args.command == "verify" else run()
    )
    if args.command == "run":
        result = {k: result[k] for k in ["freeze_id", "policies", "paired_intervals", "meta_calls"]}
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
