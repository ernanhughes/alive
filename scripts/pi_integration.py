"""ALIVE-PI-01B integration: a real cognition investigation through the REAL Pi, no paid inference.

    Cognition -> ModelGateway -> PiGateway -> PiRunner -> real Pi -> ALIVE egress
        -> DirectMetaGateway -> (real HTTP) -> this script's scripted Meta-compatible provider

The provider is a throwaway server on 127.0.0.1 that answers with the deterministic mock role
outputs. The "credential" is a throwaway string. Nothing leaves the machine. The script exits 0 only
if every claim below holds, and prints each one.

Locally:   uv run python -m scripts.pi_integration
In Docker: docker run --rm -e PYTHONPATH=/app \
               -v "$PWD/scripts/pi_integration.py:/tmp/pi_integration.py:ro" \
               --entrypoint python <image> /tmp/pi_integration.py
"""

import json
import sys
import tempfile
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

from fastapi.testclient import TestClient

from alive.app import create_app
from alive.config import Settings
from alive.models import Base
from alive.society import mock_role, role_prompt

FAKE_KEY = "scripted-provider-credential-not-real"
TOKEN = "integration-token-0123456789-0123456789"
ROLES = ("observer", "proposer", "critic", "evaluator")
USAGE = {"prompt_tokens": 11, "completion_tokens": 7, "total_tokens": 18}
provider_requests = []


class Provider(BaseHTTPRequestHandler):
    def log_message(self, *args):
        pass

    def reply(self, payload):
        data = json.dumps(payload).encode()
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def do_GET(self):
        self.reply({"data": [{"id": "muse-spark-1.3"}]})

    def do_POST(self):
        body = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
        provider_requests.append(
            {
                "path": self.path,
                "authorization": self.headers.get("Authorization"),
                "request_id": self.headers.get("X-Request-Id"),
                "model": body.get("model"),
                "stream": body.get("stream"),
                "tools": "tools" in body,
            }
        )
        instructions, payload = body["messages"][0]["content"], body["messages"][1]["content"]
        role = next(r for r in ROLES if role_prompt(r) == instructions)
        content = mock_role(role, json.loads(payload)).model_dump_json()
        self.reply(
            {
                "choices": [{"message": {"content": content}, "finish_reason": "stop"}],
                "usage": USAGE,
            }
        )


def settings_for(work, port):
    return Settings(
        _env_file=None,
        alive_meta_api_key=FAKE_KEY,
        alive_meta_base_url=f"http://127.0.0.1:{port}/v1",
        alive_model_transport="pi",
        alive_pi_run_deadline=90,
        database_url=f"sqlite+aiosqlite:///{work}/integration.db",
        alive_api_token=TOKEN,
        alive_heartbeat_seconds=0.1,
        alive_workspace=work / "workspace",
    )


def create_schema(settings):
    import asyncio

    from alive.db import Database

    async def go():
        db = Database(settings.database_url)
        async with db.engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
        await db.engine.dispose()

    asyncio.run(go())


def wait_for(client, path, predicate, timeout=180):
    deadline = time.monotonic() + timeout
    value = None
    while time.monotonic() < deadline:
        value = client.get("/api/v1" + path).json()
        if predicate(value):
            return value
        time.sleep(0.25)
    raise SystemExit(f"timed out waiting for {path}: {value}")


def main():
    server = ThreadingHTTPServer(("127.0.0.1", 0), Provider)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    work = Path(tempfile.mkdtemp(prefix="alive-pi-integration-"))
    settings = settings_for(work, server.server_address[1])
    create_schema(settings)
    checks = []

    def check(name, ok, detail=""):
        checks.append(ok)
        print(("PASS  " if ok else "FAIL  ") + name + (f"  [{detail}]" if detail else ""))

    with TestClient(create_app(settings), headers={"Authorization": f"Bearer {TOKEN}"}) as client:
        started = client.post(
            "/api/v1/cognition/control", json={"command": "start", "provider": "meta"}
        )
        check(
            "cognition starts on the scripted Meta-compatible provider", started.status_code == 200
        )
        lab = client.post("/api/v1/lab", json={"scenario": "relevant", "seed": 13}).json()
        view = client.post(f"/api/v1/lab/{lab['id']}/inject", json={}).json()
        event = {
            "event_type": "browser.dom_changed",
            "payload": {"url": f"http://127.0.0.1:8000/world/{lab['id']}", "text": view["text"]},
        }
        client.post("/api/v1/events", json=event)
        rows = wait_for(
            client,
            "/cognition/investigations",
            lambda r: r and r[0]["state"] in {"COMPLETED", "ABSTAINED", "FAILED", "CANCELLED"},
        )
        run = client.get("/api/v1/cognition/investigations/" + rows[0]["id"]).json()
        calls = run["invocations"]
        check(
            "the investigation completed", run["state"] in {"COMPLETED", "ABSTAINED"}, run["state"]
        )
        check(
            "every model call validated",
            bool(calls) and all(c["status"] == "validated" for c in calls),
        )
        listing = client.get("/api/v1/pi/runs?limit=100").json()
        receipts = [client.get(f"/api/v1/pi/runs/{r['run_id']}").json() for r in listing]
        check("one Pi run per model call", len(receipts) == len(calls) == len(provider_requests))
        check("every Pi run settled", all(r["state"] == "SETTLED" for r in receipts))
        check(
            "exactly one provider request per Pi run, none retried",
            all(
                r["requests"]["counts"]["settled"] == 1 and r["requests"]["admitted"] == 1
                for r in receipts
            ),
        )
        check(
            "Pi 1.4.0 observed under its local alias only",
            all(
                r["pi"]["version"] == "1.4.0"
                and r["identity"]["matches_expected_alias"]
                and r["identity"]["pi_observed"]["model"] == "alive-approved"
                for r in receipts
            ),
        )
        check(
            "the provider saw ALIVE's credential, correlation and model; never Pi's token",
            all(
                p["authorization"] == f"Bearer {FAKE_KEY}"
                and p["model"] == settings.alive_meta_model
                and p["path"] == "/v1/chat/completions"
                and p["request_id"] in {c["id"] for c in calls}
                for p in provider_requests
            ),
        )
        check(
            "no provider request carried tools or streaming",
            not any(p["tools"] or p["stream"] for p in provider_requests),
        )
        check(
            "cost is unknown, not zero",
            all(
                r["cost"]["usd"] is None and r["requests"]["items"][0]["usage"] == USAGE
                for r in receipts
            ),
        )
        check(
            "every process tree was confirmed gone",
            all(r["settlement"]["cleanup_confirmed"] is True for r in receipts),
        )
        events = [client.get(f"/api/v1/pi/runs/{r['run_id']}/events").json() for r in receipts]
        blob = json.dumps(receipts) + json.dumps(events)
        check("no credential appears in any receipt or event", FAKE_KEY not in blob)
        denied = TestClient(client.app).get("/api/v1/pi/runs")
        check("receipts require authentication", denied.status_code == 401)
    server.shutdown()
    print(
        f"\n{sum(checks)}/{len(checks)} checks passed; "
        f"{len(provider_requests)} scripted provider calls"
    )
    return 0 if all(checks) else 1


if __name__ == "__main__":
    sys.exit(main())
