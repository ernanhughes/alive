"""Reconcile the frozen ALIVE-14 protocol's CRLF evidence hash with its LF Git blob."""

import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PROTOCOL = ROOT / "archives/ALIVE-14/protocol.json"
EVIDENCE = ROOT / "archives/ALIVE-14/evidence/retrieval-comparison-held_out.json"
MANIFEST = ROOT / "archives/ALIVE-14/manifest.json"
LF_HASH = "01165f12a54e2ec2c60a6e9d39fcd19054a69ae3e3278740bf4de47991492d9b"
CRLF_HASH = "56a85e66219425387ca42465ad2f3435be0b9af1652ba484fd7e5836cf54baf5"
CRLF_BYTES = 14349


def main():
    data = PROTOCOL.read_bytes()
    lf = data.replace(b"\r\n", b"\n")
    crlf = lf.replace(b"\n", b"\r\n")
    lf_hash = hashlib.sha256(lf).hexdigest()
    crlf_hash = hashlib.sha256(crlf).hexdigest()
    evidence = json.loads(EVIDENCE.read_text(encoding="utf-8"))
    manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
    errors = []
    if lf_hash != LF_HASH:
        errors.append("committed-blob LF hash changed")
    if crlf_hash != CRLF_HASH:
        errors.append("original CRLF representation hash changed")
    if evidence["protocol_sha256"] != CRLF_HASH:
        errors.append("recorded evidence hash does not match original CRLF representation")
    entry = manifest["files"]["protocol.json"]
    if entry["sha256"] != CRLF_HASH or entry["bytes"] != CRLF_BYTES:
        errors.append("original manifest no longer represents the CRLF evidence")
    if errors:
        raise SystemExit("\n".join(errors))
    print(
        "VERIFIED ALIVE-14 protocol reconciliation: "
        f"git-blob-LF={lf_hash} original-CRLF={crlf_hash}; "
        "original archive manifest/evidence preserved"
    )


if __name__ == "__main__":
    main()
