"""Host-runnable Docker smoke test for ALIVE-DOCKER-01.

Usage: python scripts/docker-smoke-test.py [--base-url http://localhost:8080]

Exercises the real composed application: static UI, fixture pages, and the
authenticated API workflow. No inference, no paid providers.
"""

import argparse
import os
import sys
import uuid

import httpx

CHECKS = []


def check(name):
    def wrap(fn):
        CHECKS.append((name, fn))
        return fn

    return wrap


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--base-url", default=os.environ.get("ALIVE_BASE_URL", "http://localhost:8080")
    )
    parser.add_argument("--token", default=os.environ.get("ALIVE_API_TOKEN", ""))
    args = parser.parse_args()
    base = args.base_url.rstrip("/")
    token = args.token.strip()
    if not token:
        print("ALIVE_API_TOKEN is required (same value as the composed app)")
        return 2
    headers = {"Authorization": f"Bearer {token}"}

    with httpx.Client(base_url=base, timeout=30) as client:
        response = client.get("/api/v1/health")
        assert response.status_code == 200, f"health HTTP {response.status_code}"
        assert response.json().get("status") == "ok", f"health payload {response.text[:200]}"
        print("PASS health: backend ok")

        index = client.get("/")
        assert index.status_code == 200, f"index HTTP {index.status_code}"
        assert 'id="root"' in index.text and "/assets/" in index.text, "dashboard bundle missing"
        print("PASS frontend: dashboard index serves bundled UI")

        demo = client.get("/demo")
        assert demo.status_code == 200 and "First Contact" in demo.text, "habitat page missing"
        print("PASS habitat: /demo serves the controlled environment")

        mirror = client.get("/demo-live-01/python-3.12.html")
        assert mirror.status_code == 200 and "LOCAL MIRROR" in mirror.text, "demo mirror missing"
        print("PASS fixtures: pinned demo mirror served offline")

        caps = client.get("/api/v1/capabilities", headers=headers)
        assert caps.status_code == 200, f"capabilities HTTP {caps.status_code}"
        assert caps.json()["database"]["backend"] == "postgresql", "not backed by PostgreSQL"
        print("PASS database: PostgreSQL backend reported")

        client.post("/api/v1/alive/start", json={}, headers=headers).raise_for_status()
        marker = "smoke observation " + uuid.uuid4().hex[:8]
        goal_title = "Smoke goal " + uuid.uuid4().hex[:8]
        goal = client.post("/api/v1/goals", json={"title": goal_title}, headers=headers)
        assert goal.status_code == 200, f"goal HTTP {goal.status_code}"
        goal_id = goal.json()["id"]
        transition = client.post(
            f"/api/v1/goals/{goal_id}/transition", json={"status": "accepted"}, headers=headers
        )
        assert transition.status_code == 200, "goal accept failed"
        bad = client.post(
            f"/api/v1/goals/{goal_id}/transition", json={"status": "completed"}, headers=headers
        )
        assert bad.status_code == 409, "invalid transition must be rejected"
        print("PASS goals: create/accept work, invalid transition rejected with 409")

        ingested = client.post(
            "/api/v1/events",
            json={
                "event_type": "browser.page_opened",
                "source": "user",
                "payload": {"url": "http://127.0.0.1:8000/demo", "text": marker},
            },
            headers=headers,
        )
        assert ingested.status_code in (200, 201), f"ingest HTTP {ingested.status_code}"
        search = client.post("/api/v1/memories/search", json={"query": marker}, headers=headers)
        assert search.status_code == 200 and search.json().get("results"), "memory not retrievable"
        assert search.json()["mode"] == "postgresql_fts", f"unexpected mode {search.json()}"
        print("PASS memory: observation ingested and retrieved via postgresql_fts")

        run = client.post(
            "/api/v1/agents/runs",
            json={"runner": "mock", "objective": f"Examine this controlled observation: {marker}."},
            headers=headers,
        )
        assert run.status_code == 200, f"agent HTTP {run.status_code}"
        run_id = run.json()["id"]
        result = client.get(f"/api/v1/agents/runs/{run_id}", headers=headers).json()
        assert result["status"] == "completed", f"mock run status {result['status']}"
        print("PASS agents: deterministic mock run completed")

        unauth = client.get("/api/v1/alive")
        assert unauth.status_code in (401, 403, 422), "unauthenticated access must fail"
        print("PASS auth: unauthenticated request rejected")

        events = client.get("/api/v1/events?limit=5", headers=headers)
        assert events.status_code == 200 and isinstance(events.json(), list), "events unreadable"
        print("PASS events: persisted timeline readable")

    print(f"\nSMOKE OK: {8} checks passed against {base}")
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except AssertionError as exc:
        print(f"FAIL {exc}")
        sys.exit(1)
    except httpx.HTTPError as exc:
        print(f"FAIL transport: {exc}")
        sys.exit(1)
