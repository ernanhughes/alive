"""Container healthcheck: process + DB-backed readiness, no side effects."""

import json
import sys
import urllib.request

try:
    with urllib.request.urlopen("http://127.0.0.1:8000/api/v1/health", timeout=5) as response:
        body = json.loads(response.read().decode())
    if response.status == 200 and body.get("status") == "ok":
        print("healthy: backend ok")
        sys.exit(0)
    print(f"unhealthy: health payload {body!r}")
    sys.exit(1)
except Exception as exc:  # noqa: BLE001 - healthcheck must report, not raise
    print(f"unhealthy: {type(exc).__name__}: {exc}")
    sys.exit(1)
