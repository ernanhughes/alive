"""Verify a SHA-256 archive manifest and reject unlisted payloads."""

import argparse
import hashlib
import json
from pathlib import Path


def verify(archive):
    archive = Path(archive)
    manifest = json.loads((archive / "manifest.json").read_text(encoding="utf-8"))
    errors = []
    for name, expected in manifest["files"].items():
        path = archive / name
        if not path.is_file():
            errors.append(f"missing: {name}")
            continue
        payload = path.read_bytes()
        if len(payload) != expected["bytes"]:
            errors.append(f"size mismatch: {name}")
        if hashlib.sha256(payload).hexdigest() != expected["sha256"]:
            errors.append(f"hash mismatch: {name}")
    listed = set(manifest["files"]) | {"manifest.json"}
    for path in sorted(archive.rglob("*")):
        if path.is_file():
            name = path.relative_to(archive).as_posix()
            if name not in listed:
                errors.append(f"unlisted: {name}")
    if errors:
        raise SystemExit("\n".join(errors))
    print(
        f"VERIFIED {len(manifest['files'])} payloads and no unlisted files in {archive.as_posix()}"
    )


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("archive", nargs="?", default="archives/ALIVE-13")
    verify(parser.parse_args().archive)
