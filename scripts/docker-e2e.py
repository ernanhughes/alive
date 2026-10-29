"""Isolated E2E runner for ALIVE-DOCKER-01 (service `e2e` in compose.e2e.yaml).

Runs the full API workflow against the real composed app over the isolated
test network, including failure-path and evidence checks. Exits nonzero on
any failure so Compose reports it via --exit-code-from e2e.
"""

import os
import time
import uuid

import httpx

BASE = os.environ.get("ALIVE_BASE_URL", "http://app:8000").rstrip("/")
TOKEN = os.environ.get("ALIVE_API_TOKEN", "").strip()
passed = 0


def step(name, fn):
    global passed
    try:
        fn()
    except Exception as exc:  # noqa: BLE001 - report every failure honestly
        print(f"FAIL {name}: {type(exc).__name__}: {exc}", flush=True)
        raise SystemExit(1)
    passed += 1
    print(f"PASS {name}", flush=True)


def main():
    if not TOKEN:
        print("FAIL ALIVE_API_TOKEN is required")
        raise SystemExit(1)
    headers = {"Authorization": f"Bearer {TOKEN}"}
    with httpx.Client(base_url=BASE, timeout=30) as client:

        def wait_healthy():
            for _ in range(60):
                try:
                    response = client.get("/api/v1/health", timeout=5)
                    if response.status_code == 200 and response.json().get("status") == "ok":
                        return
                except httpx.HTTPError:
                    pass
                time.sleep(2)
            raise RuntimeError("app never became healthy")

        def capabilities():
            response = client.get("/api/v1/capabilities", headers=headers)
            assert response.status_code == 200, response.status_code
            body = response.json()
            assert body["database"]["available"] is True
            assert body["database"]["backend"] == "postgresql"
            assert body["zeromq"]["available"] is True

        def frontend():
            index = client.get("/")
            assert index.status_code == 200, index.status_code
            assert 'id="root"' in index.text and "/assets/" in index.text
            demo = client.get("/demo")
            assert demo.status_code == 200 and "First Contact" in demo.text
            for name in ("python-3.11.html", "python-3.12.html", "synthetic-no-change.html"):
                mirror = client.get(f"/demo-live-01/{name}")
                assert mirror.status_code == 200, (name, mirror.status_code)
            unknown = client.get("/demo-live-01/does-not-exist.html")
            assert unknown.status_code == 404, unknown.status_code

        def goal_lifecycle():
            title = "E2E goal " + uuid.uuid4().hex[:8]
            created = client.post("/api/v1/goals", json={"title": title}, headers=headers)
            assert created.status_code == 200, created.text[:200]
            goal_id = created.json()["id"]
            for status in ("accepted", "active", "completed"):
                response = client.post(
                    f"/api/v1/goals/{goal_id}/transition", json={"status": status}, headers=headers
                )
                assert response.status_code == 200, (status, response.text[:200])
            assert response.json()["status"] == "completed"
            replay = client.post(
                f"/api/v1/goals/{goal_id}/transition", json={"status": "active"}, headers=headers
            )
            assert replay.status_code == 409, replay.status_code

        def evidence_workflow():
            client.post("/api/v1/alive/start", json={}, headers=headers).raise_for_status()
            marker = "e2e observation " + uuid.uuid4().hex[:8]
            ingested = client.post(
                "/api/v1/events",
                json={
                    "event_type": "browser.dom_changed",
                    "source": "user",
                    "payload": {"url": "http://app:8000/demo", "text": marker},
                },
                headers=headers,
            )
            assert ingested.status_code in (200, 201), ingested.text[:200]
            search = client.post("/api/v1/memories/search", json={"query": marker}, headers=headers)
            assert search.status_code == 200, search.text[:200]
            assert search.json()["mode"] == "postgresql_fts"
            assert search.json()["results"], "memory missing"
            run = client.post(
                "/api/v1/agents/runs",
                json={
                    "runner": "mock",
                    "objective": f"Examine this controlled observation: {marker}.",
                },
                headers=headers,
            )
            assert run.status_code == 200, run.text[:200]
            run_id = run.json()["id"]
            for _ in range(30):
                result = client.get(f"/api/v1/agents/runs/{run_id}", headers=headers).json()
                if result["status"] in ("completed", "failed"):
                    break
                time.sleep(1)
            assert result["status"] == "completed", result
            assert "Observation examined" in (result["result"] or "")
            events = client.get("/api/v1/events?limit=10", headers=headers)
            assert events.status_code == 200 and len(events.json()) >= 1

        def failure_paths():
            assert client.get("/api/v1/alive").status_code in (401, 403, 422)
            denied = client.post(
                "/api/v1/goals/00000000-0000-0000-0000-000000000000/transition",
                json={"status": "accepted"},
                headers=headers,
            )
            assert denied.status_code == 404, denied.status_code
            vector = client.post(
                "/api/v1/memories/search", json={"query": "e2e", "mode": "vector"}, headers=headers
            )
            assert vector.status_code in (200, 409), vector.status_code
            if vector.status_code == 409:
                assert "embedding" in vector.text.lower() or "semantic" in vector.text.lower()

        step("readiness", wait_healthy)
        step("capabilities", capabilities)
        step("frontend+fixtures", frontend)
        step("goal-lifecycle", goal_lifecycle)
        step("evidence-workflow", evidence_workflow)
        step("failure-paths", failure_paths)
    print(f"E2E OK: {passed} groups passed against {BASE}")


if __name__ == "__main__":
    main()
