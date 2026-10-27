"""One focused P3 diagnostic; no paid inference or live browser control."""

import argparse
import json

from alive.learning.history_diagnostic import freeze, run, verify


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=["freeze", "verify", "run"])
    command = parser.parse_args().command
    result = freeze() if command == "freeze" else verify() if command == "verify" else run()
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
