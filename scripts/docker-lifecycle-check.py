"""Host-runnable lifecycle check for the composed ALIVE demo (ALIVE-DOCKER-02).

Usage:
    python scripts/docker-lifecycle-check.py --phase run
    docker compose restart app
    python scripts/docker-lifecycle-check.py --phase after-restart --goal-id <printed id>
    python scripts/docker-lifecycle-check.py --phase expect-refused   # demo mode off

Drives the real HTTP API of the running container through the deterministic local fixture
provider (`local_fixture_claim`): save and anchor a source, authorise the exact payload, see a
meaningful change on the 3.12 mirror and an honest abstention on the synthetic no-change mirror,
then withdraw the source. No inference and no paid provider is involved; the output is a
deterministic fixture result, not model reasoning and not source truth.

The mirror URLs below are identifiers the server allow-lists (alive.web_experience.PAGES); they
use port 8000 whatever --base-url is, because that is what the Chrome extension authorises.
"""

import argparse
import hashlib
import json
import os
import sys
from pathlib import Path

import httpx

ROOT = "/api/v1/browser-experience"
FIXTURES = Path(__file__).resolve().parents[1] / "fixtures" / "demo_live_01"
IDENTITY_HOST = "http://127.0.0.1:8000/demo-live-01/"
BEHAVIOR = "Return the current UTC date and time, with tzinfo None."
DEPRECATION = "Deprecated since version 3.12: Use datetime.now() with UTC instead."


def env_file_token():
    env_path = Path(__file__).resolve().parents[1] / ".env"
    if not env_path.exists():
        return ""
    for line in env_path.read_text(encoding="utf-8").splitlines():
        if line.strip().startswith("ALIVE_API_TOKEN="):
            value = line.split("=", 1)[1].strip()
            return value.strip('"').strip("'")
    return ""


def post(client, path, body, expected=200):
    response = client.post(ROOT + path, json=body)
    assert response.status_code == expected, (
        f"POST {path} HTTP {response.status_code}: {response.text[:300]}"
    )
    return response.json()


def capture(name):
    return json.loads((FIXTURES / (name + ".capture.json")).read_text(encoding="utf-8"))


def setup(client, newer):
    goal = post(client, "/goals", {"instruction": f"Docker lifecycle check: utcnow vs {newer}"})
    snapshots = []
    for name in ("python-3.11", newer):
        data = capture(name)
        url = IDENTITY_HOST + name + ".html"
        permission = post(
            client,
            "/grants",
            {"goal_id": goal["id"], "url": url, "tab_key": "docker-check-tab", "approved": True},
        )
        snapshots.append(
            post(
                client,
                "/snapshots",
                {
                    "grant_id": permission["id"],
                    "url": url,
                    "title": name,
                    **data,
                    "reviewed_sha256": hashlib.sha256(data["text"].encode()).hexdigest(),
                },
            )["snapshot"]
        )
    saved = post(client, "/research/memories", {"snapshot_id": snapshots[0]["id"]})
    post(
        client,
        f"/research/memories/{saved['id']}/anchor",
        {
            "quote": BEHAVIOR,
            "expected_sha256": saved["data"]["sha256"],
            "expected_revision": 0,
            "occurrence_start": saved["data"]["excerpt"].index(BEHAVIOR),
        },
    )
    request = {
        "snapshot_id": snapshots[1]["id"],
        "research_id": saved["id"],
        "analysis_mode": "claim_comparison",
        "provider": "local_fixture_claim",
    }
    return goal, saved, request


def authorise_and_analyse(client, request):
    consent = post(client, "/research/outbound/preview", request)
    provider = consent.get("provider") or {}
    assert provider.get("id") == "local_fixture_claim", f"unexpected provider {provider}"
    assert provider.get("external") is False, "fixture provider must not be external"
    post(
        client,
        "/research/outbound/authorize",
        {
            "consent_id": consent["id"],
            "payload_sha256": consent["payload_sha256"],
            "approved": True,
        },
    )
    return post(client, "/research/relationships", {"consent_id": consent["id"]})


def run(client):
    for name in ("python-3.11", "python-3.12", "synthetic-no-change"):
        page = client.get(f"/demo-live-01/{name}.html")
        assert page.status_code == 200, f"mirror {name} HTTP {page.status_code}"
    assert client.get("/demo-live-01/does-not-exist.html").status_code == 404
    print("PASS mirrors: three pinned mirrors served, unknown mirror 404")

    goal, saved, request = setup(client, "python-3.12")
    result = authorise_and_analyse(client, request)
    assert result["analysis"]["status"] == "validated", result
    candidate = result["connection"]
    assert candidate["status"] == "candidate"
    assert candidate["data"]["historical_quote_retained_in_current"] is True
    assert candidate["data"]["supersession_basis_quote"] == DEPRECATION
    print("PASS change: fixture comparison found a standing change; behaviour retained")

    post(client, f"/research/memories/{saved['id']}/withdraw", {})
    listed = client.get(ROOT + "/research/relationships", params={"goal_id": goal["id"]}).json()
    assert listed["connections"] == [], "withdrawn source must not leave a connection"
    print("PASS withdrawal: dependent finding removed from ordinary reads")

    goal2, _, request2 = setup(client, "synthetic-no-change")
    result2 = authorise_and_analyse(client, request2)
    assert result2["analysis"]["data"]["validation"]["relationship"] == "insufficient_evidence"
    assert result2["connection"] is None and result2["abstained"]
    print("PASS abstention: no-change mirror leaves an honest abstention, no connection")
    print(
        "\nRUN OK. After `docker compose restart app` run: "
        f"--phase after-restart --goal-id {goal['id']}"
    )
    return 0


def after_restart(client, goal_id):
    listed = client.get(ROOT + "/research/relationships", params={"goal_id": goal_id}).json()
    assert listed["connections"] == [], "finding reappeared after restart"
    print("PASS restart: withdrawn finding is still absent after the container restarted")
    return 0


def expect_refused(client):
    goal, saved, request = setup(client, "python-3.12")
    response = client.post(ROOT + "/research/outbound/preview", json=request)
    assert response.status_code >= 400, "fixture provider must be refused when demo mode is off"
    print(
        f"PASS refused: fixture provider rejected (HTTP {response.status_code}) with demo mode off"
    )
    return 0


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--base-url", default=os.environ.get("ALIVE_BASE_URL", "http://localhost:8000")
    )
    parser.add_argument("--token", default=os.environ.get("ALIVE_API_TOKEN") or env_file_token())
    parser.add_argument(
        "--phase", choices=["run", "after-restart", "expect-refused"], default="run"
    )
    parser.add_argument("--goal-id", default="")
    args = parser.parse_args()
    if not args.token.strip():
        parser.error("--token, ALIVE_API_TOKEN, or ALIVE_API_TOKEN in .env is required")
    headers = {"Authorization": f"Bearer {args.token.strip()}"}
    with httpx.Client(base_url=args.base_url.rstrip("/"), timeout=60, headers=headers) as client:
        if args.phase == "run":
            return run(client)
        if args.phase == "after-restart":
            assert args.goal_id, "--goal-id is required for --phase after-restart"
            return after_restart(client, args.goal_id)
        return expect_refused(client)


if __name__ == "__main__":
    try:
        sys.exit(main())
    except AssertionError as exc:
        print(f"FAIL {exc}")
        sys.exit(1)
    except httpx.HTTPError as exc:
        print(f"FAIL transport: {exc}")
        sys.exit(1)
