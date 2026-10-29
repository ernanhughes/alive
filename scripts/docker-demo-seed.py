"""Idempotent deterministic demo bootstrap for the Docker deployment.

Uses the real HTTP API (no direct DB writes, no inference). Safe to run on
every container start: existing databases are never wiped; if the marker goal
and observation already exist, nothing is created.
"""

import os
import sys
import time

import httpx

BASE = os.environ.get("ALIVE_BASE_URL", "http://127.0.0.1:8000")
MARKER_TITLE = "Docker demo inquiry — Python 3.12 deprecation mirror"
MARKER_TEXT = (
    "Docker demo observation: the habitat shows a green light; next, review the "
    "pinned Python 3.12 deprecation mirror served at /demo-live-01/python-3.12.html. "
    "Fixture data for the interactive demo; no inference performed."
)


def token():
    value = os.environ.get("ALIVE_API_TOKEN", "").strip()
    if value:
        return value
    for path in ("/app/.alive/token", ".alive/token"):
        try:
            with open(path, encoding="utf-8") as handle:
                value = handle.read().strip()
        except OSError:
            continue
        if value:
            return value
    return ""


def wait_ready(client):
    for _ in range(90):
        try:
            response = client.get("/api/v1/health", timeout=5)
            if response.status_code == 200 and response.json().get("status") == "ok":
                return
        except httpx.HTTPError:
            pass
        time.sleep(2)
    print("demo seed: backend did not become ready; skipping", flush=True)
    sys.exit(0)


def main():
    auth = token()
    if not auth:
        print("demo seed: no API token available; skipping")
        return
    with httpx.Client(
        base_url=BASE, timeout=20, headers={"Authorization": f"Bearer {auth}"}
    ) as client:
        wait_ready(client)
        try:
            alive = client.get("/api/v1/alive")
            if alive.status_code == 503:
                print("demo seed: runtime degraded (migrations pending?); skipping")
                return
            alive.raise_for_status()
        except httpx.HTTPError as exc:
            print(f"demo seed: cannot reach API ({exc}); skipping")
            return
        goals = client.get("/api/v1/goals").json()
        if not any(g.get("title") == MARKER_TITLE for g in goals):
            created = client.post(
                "/api/v1/goals",
                json={
                    "title": MARKER_TITLE,
                    "description": (
                        "Deterministic Docker demo starting point (fixture data, "
                        "no inference). Open /demo-live-01/python-3.12.html to see "
                        "the pinned local mirror with its deprecation note, then "
                        "compare it with /demo-live-01/python-3.11.html. "
                        "Accept this goal to walk the genuine workflow."
                    ),
                },
            )
            created.raise_for_status()
            print(f"demo seed: created marker goal {created.json()['id']}", flush=True)
        else:
            print("demo seed: marker goal already present", flush=True)
        search = client.post("/api/v1/memories/search", json={"query": "Docker demo observation"})
        if search.status_code == 200 and search.json().get("results"):
            print("demo seed: marker observation already remembered", flush=True)
            return
        ingested = client.post(
            "/api/v1/events",
            json={
                "event_type": "browser.page_opened",
                "source": "user",
                "payload": {
                    "url": "http://127.0.0.1:8000/demo",
                    "text": MARKER_TEXT,
                },
            },
        )
        if ingested.status_code in (200, 201):
            print("demo seed: ingested marker observation", flush=True)
        else:
            print(f"demo seed: observation ingest returned {ingested.status_code}; skipping")
            return
        verify = client.post("/api/v1/memories/search", json={"query": "Docker demo observation"})
        if verify.status_code == 200 and verify.json().get("results"):
            print("demo seed: marker observation verified in memory search", flush=True)
        else:
            print("demo seed: WARNING marker observation not found in search")


if __name__ == "__main__":
    main()
