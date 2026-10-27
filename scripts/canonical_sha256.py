"""Print the canonical LF SHA-256 for a checked-in text file."""

import argparse
import hashlib
from pathlib import Path


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("path")
    data = Path(parser.parse_args().path).read_bytes().replace(b"\r\n", b"\n")
    print(hashlib.sha256(data).hexdigest())


if __name__ == "__main__":
    main()
