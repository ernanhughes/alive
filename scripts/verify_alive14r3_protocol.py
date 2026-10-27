"""Verify the frozen ALIVE-14-R3 protocol and sealed answer key."""

import hashlib
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PROTOCOL = ROOT / "archives/ALIVE-14-R3/protocol/relationship-experiment-v3.json"
ANSWER_KEY = ROOT / "archives/ALIVE-14-R3/protocol/answer-key-v3.json"
EXPECTED_PROTOCOL_SHA256 = "85fe891cee31bf93d178c4cba2102642b8f4b5e666a0ee426186d5735eb5a71b"
EXPECTED_ANSWER_KEY_SHA256 = "255e706dd569634d1710a50831f65a6dd6eb7dabc5ee56e1cd763b382554b43d"


def canonical_sha256(path):
    return hashlib.sha256(path.read_bytes().replace(b"\r\n", b"\n")).hexdigest()


def main():
    for path, expected, label in (
        (PROTOCOL, EXPECTED_PROTOCOL_SHA256, "protocol"),
        (ANSWER_KEY, EXPECTED_ANSWER_KEY_SHA256, "answer-key"),
    ):
        actual = canonical_sha256(path)
        if actual != expected:
            raise SystemExit(f"ALIVE-14-R3 {label} hash changed: {actual}")
        print(f"VERIFIED ALIVE-14-R3 {label} canonical LF hash {actual}")


if __name__ == "__main__":
    main()
