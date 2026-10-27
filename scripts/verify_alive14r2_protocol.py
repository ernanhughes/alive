"""Verify the frozen ALIVE-14-R2 successor protocol hash."""

import hashlib
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PROTOCOL = ROOT / "archives/ALIVE-14-R2/protocol/relationship-experiment-v2.json"
EXPECTED = "bd08e2e6b9e7f4804af16daaca5b5a12a2d07d83eb19ae082527ef1da2add5dc"


def main():
    data = PROTOCOL.read_bytes().replace(b"\r\n", b"\n")
    actual = hashlib.sha256(data).hexdigest()
    if actual != EXPECTED:
        raise SystemExit(f"R2 protocol hash changed: {actual}")
    print(f"VERIFIED ALIVE-14-R2 protocol canonical LF hash {actual}")


if __name__ == "__main__":
    main()
