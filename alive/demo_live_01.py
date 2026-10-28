"""Pinned source identity for the explicitly local ALIVE-DEMO-LIVE-01 mirrors.

Matching bytes/provenance establish a mirror's identity, never semantic truth.
Unknown URLs, formats, text or entry maps do not inherit trusted source metadata.
"""

import hashlib
import json
from pathlib import Path
from urllib.parse import urlsplit

DIRECTORY = Path(__file__).resolve().parents[1] / "fixtures/demo_live_01"


def manifest():
    return json.loads((DIRECTORY / "manifest.json").read_text(encoding="utf-8"))


def identify(url, text, entries, version):
    if version != 2:
        return None
    parsed = urlsplit(url)
    if parsed.scheme != "http" or parsed.hostname not in ("127.0.0.1", "localhost"):
        return None
    if parsed.query or parsed.fragment:
        return None
    sha = hashlib.sha256(text.encode()).hexdigest()
    for source in manifest()["sources"]:
        if parsed.path != "/demo-live-01/" + source["file"]:
            continue
        if sha != source["captured_text_sha256"] or entries != source["capture_entries"]:
            return None
        if (
            hashlib.sha256((DIRECTORY / source["file"]).read_bytes()).hexdigest()
            != source["mirror_html_sha256"]
        ):
            return None
        if (
            source.get("source_html_file")
            and hashlib.sha256((DIRECTORY / source["source_html_file"]).read_bytes()).hexdigest()
            != source["source_html_sha256"]
        ):
            return None
        return {
            key: source.get(key)
            for key in (
                "id",
                "kind",
                "canonical_url",
                "documentation_build",
                "retrieved_at",
                "upstream_revision",
                "upstream_revision_status",
                "source_html_sha256",
                "mirror_html_sha256",
                "captured_text_sha256",
                "capture_format_version",
                "verification",
                "license",
                "attribution",
            )
        }
    return None


def fixture_page(name):
    from fastapi import HTTPException
    from fastapi.responses import FileResponse

    source = next((item for item in manifest()["sources"] if item["file"] == name), None)
    if not source:
        raise HTTPException(404, "Unknown demo mirror")
    path = DIRECTORY / source["file"]
    if hashlib.sha256(path.read_bytes()).hexdigest() != source["mirror_html_sha256"]:
        raise HTTPException(409, "Pinned demo mirror changed")
    return FileResponse(
        path,
        media_type="text/html",
        headers={
            "Content-Security-Policy": (
                "default-src 'none'; style-src 'unsafe-inline'; "
                "form-action 'none'; frame-ancestors 'none'"
            ),
            "X-Content-Type-Options": "nosniff",
        },
    )
