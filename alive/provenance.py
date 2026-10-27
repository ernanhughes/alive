"""Authenticated runtime identity without credentials or absolute local paths."""

import hashlib
import json
import subprocess
import uuid
from pathlib import Path
from urllib.parse import urlsplit


def file_digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def runtime_identity(database, settings):
    root = Path(__file__).resolve().parents[1]
    modules = {
        str(path.relative_to(root)).replace("\\", "/"): file_digest(path)
        for path in sorted((root / "alive").rglob("*.py"))
    }
    try:
        commit = subprocess.check_output(
            ["git", "rev-parse", "HEAD"],
            cwd=root,
            text=True,
            stderr=subprocess.DEVNULL,
            timeout=3,
        ).strip()
    except (OSError, subprocess.SubprocessError):
        commit = None
    url = database.engine.url
    identity = (
        str(Path(url.database).resolve())
        if url.get_backend_name() == "sqlite"
        else (f"{url.get_backend_name()}:{url.host}:{url.port}:{url.database}")
    )
    endpoint = urlsplit(settings.alive_meta_url or settings.alive_meta_base_url)
    return {
        "protocol_version": 1,
        "runtime_instance": str(uuid.uuid4()),
        "source_commit": commit,
        "module_sha256": modules,
        "runtime_sha256": hashlib.sha256(json.dumps(modules, sort_keys=True).encode()).hexdigest(),
        "database": {
            "dialect": url.get_backend_name(),
            "fingerprint": hashlib.sha256(identity.encode()).hexdigest(),
        },
        "provider_origin": f"{endpoint.scheme}://{endpoint.hostname}"
        + (f":{endpoint.port}" if endpoint.port else ""),
    }
