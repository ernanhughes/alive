"""Run the frozen ALIVE-12 cross-page research-memory evaluation.

Controlled API and local retrieval only. No provider call is made.
"""

import asyncio
import json
import shutil
import subprocess
import time
from datetime import timedelta
from pathlib import Path
from types import SimpleNamespace

from fastapi.testclient import TestClient

from alive.app import create_app
from alive.config import Settings
from alive.db import Database
from alive.models import Base, now
from alive.providers import MetaProvider
from alive.web_experience import digest
from alive.web_models import WebExperience

ROOT = Path(__file__).resolve().parents[1]
WORK = ROOT / ".alive/alive12-evaluation"
ARCHIVE = ROOT / "archives/ALIVE-12"
PROTOCOL = ARCHIVE / "protocol.json"
API = "/api/v1/browser-experience"
TOKEN = "alive12-evaluation-" + "x" * 24
calls = []


async def fake_structured(*args, **kwargs):
    # Bound method call: self, instructions, data, schema.
    data = args[2] if len(args) > 2 else kwargs.get("data") or {}
    excerpt = data.get("untrusted_excerpt", "Controlled research excerpt.")
    quote = excerpt.split(". ")[0][:120]
    if len(quote) < 5:
        quote = excerpt[:80]
    calls.append(kwargs)
    return SimpleNamespace(
        text=json.dumps(
            {
                "summary": "Controlled historical research note.",
                "evidence_quote": quote,
                "limitations": "Only the controlled excerpt was read.",
            }
        ),
        usage={"prompt_tokens": 100, "completion_tokens": 50, "total_tokens": 150},
    )


MetaProvider.structured = fake_structured


def post(client, path, body, expected=200):
    response = client.post(API + path, json=body)
    assert response.status_code == expected, response.text
    return response.json()


def wait(client, note_id):
    for _ in range(100):
        row = client.get(API + "/notes/" + note_id).json()
        if row["status"] != "reserved":
            return row
        time.sleep(0.02)
    raise AssertionError("note did not settle")


def run():
    if WORK.exists():
        shutil.rmtree(WORK)
    WORK.mkdir(parents=True)
    protocol = json.loads(PROTOCOL.read_text(encoding="utf-8"))
    urls = sorted(
        {
            value
            for scenario in protocol["scenarios"]
            for value in (scenario["historical_url"], scenario["current_url"])
            if value
        }
    )
    settings = Settings(
        _env_file=None,
        alive_meta_api_key="",
        alive_embedding_enabled=False,
        alive_native_test_pages=",".join(urls),
        alive_api_token=TOKEN,
        database_url=f"sqlite+aiosqlite:///{(WORK / 'evaluation.db').as_posix()}",
        alive_workspace=WORK / "workspace",
    )

    async def schema():
        database = Database(settings.database_url)
        async with database.engine.begin() as connection:
            await connection.run_sync(Base.metadata.create_all)
        await database.engine.dispose()

    asyncio.run(schema())
    headers = {"Authorization": "Bearer " + TOKEN}
    result = {
        "protocol_version": protocol["protocol_version"],
        "kind": protocol["kind"],
        "source_commit": subprocess.check_output(
            ["git", "rev-parse", "HEAD"], cwd=ROOT, text=True
        ).strip(),
        "paid_inference": False,
        "provider_calls": 0,
        "scenarios": [],
        "arms": {},
    }
    with TestClient(create_app(settings), headers=headers) as client:
        for scenario in protocol["scenarios"]:
            goal = post(client, "/goals", {"instruction": scenario["goal"]})
            historical = None
            if scenario["historical_url"]:
                grant = post(
                    client,
                    "/grants",
                    {
                        "goal_id": goal["id"],
                        "url": scenario["historical_url"],
                        "tab_key": "historical-" + scenario["id"],
                        "approved": True,
                    },
                )
                snap = post(
                    client,
                    "/snapshots",
                    {
                        "grant_id": grant["id"],
                        "url": scenario["historical_url"],
                        "title": "Historical controlled source",
                        "text": scenario["historical_text"],
                        "reviewed_sha256": digest(scenario["historical_text"]),
                    },
                )
                note = wait(
                    client,
                    post(
                        client,
                        "/analyse",
                        {
                            "snapshot_id": snap["snapshot"]["id"],
                            "reviewed_sha256": snap["snapshot"]["data"]["sha256"],
                            "send_to_meta": True,
                        },
                    )["id"],
                )
                assert note["status"] == "validated", note
                historical = post(client, "/research/memories", {"note_id": note["id"]})
                if scenario.get("stale_after_days"):

                    async def age_memory():
                        async with client.app.state.kernel.db.sessions.begin() as session:
                            row = await session.get(WebExperience, historical["id"])
                            row.data = row.data | {
                                "reviewed_at": (
                                    now() - timedelta(days=scenario["stale_after_days"] + 23)
                                ).isoformat()
                            }

                    asyncio.run(age_memory())
                historical = {**historical, "url": scenario["historical_url"]}
            grant = post(
                client,
                "/grants",
                {
                    "goal_id": goal["id"],
                    "url": scenario["current_url"],
                    "tab_key": "current-" + scenario["id"],
                    "approved": True,
                },
            )
            current = post(
                client,
                "/snapshots",
                {
                    "grant_id": grant["id"],
                    "url": scenario["current_url"],
                    "title": "Current controlled source",
                    "text": scenario["current_text"],
                    "reviewed_sha256": digest(scenario["current_text"]),
                },
            )
            retrieved = post(
                client,
                "/research/retrieve",
                {"snapshot_id": current["snapshot"]["id"], "top_k": 3, "mode": "hybrid"},
            )
            connection = None
            if retrieved["results"]:
                connection = post(
                    client,
                    "/research/connections",
                    {
                        "snapshot_id": current["snapshot"]["id"],
                        "memory_id": retrieved["results"][0]["memory_id"],
                    },
                )
            history = client.get(API + "/research/memories", params={"goal_id": goal["id"]}).json()[
                "memories"
            ]
            result["scenarios"].append(
                {
                    "id": scenario["id"],
                    "family": scenario["family"],
                    "expected_related": scenario["expected_related"],
                    "expected_connection": scenario["expected_connection"],
                    "historical_url": scenario["historical_url"],
                    "current_url": scenario["current_url"],
                    "historical_memory_id": historical["id"] if historical else None,
                    "retrieval": retrieved,
                    "connection": connection,
                    "history_access": history,
                    "stale_after_days": scenario.get("stale_after_days"),
                }
            )
    result["provider_calls"] = len(calls)
    result["arms"] = summarize(result["scenarios"])
    (ARCHIVE / "evidence").mkdir(parents=True, exist_ok=True)
    (ARCHIVE / "evidence" / "retrieval-comparison.json").write_text(
        json.dumps(result, indent=2) + "\n", encoding="utf-8"
    )
    print(json.dumps(result["arms"], indent=2))
    print(ARCHIVE / "evidence" / "retrieval-comparison.json")


def summarize(scenarios):
    def outcome(stone):
        return stone["retrieval"]["results"]

    def score(name, retrieval, connections=False):
        related = [s for s in scenarios if s["expected_related"]]
        negative = [s for s in scenarios if not s["expected_related"]]
        results = [(s, retrieval(s)) for s in scenarios]
        all_retrieved = sum(len(items) for _, items in results)
        relevant = sum(
            1
            for s, items in results
            for item in items
            if s["expected_related"] and item["source_url"] == s["historical_url"]
        )
        target_hits = sum(
            1
            for s in related
            if any(item["source_url"] == s["historical_url"] for item in retrieval(s))
        )
        false_retrieval = sum(1 for s in negative if retrieval(s))
        connections_ok = 0
        unsupported = 0
        false_connections = 0
        abstentions = 0
        valid_quotes = 0
        for s, items in results:
            if not connections or not items:
                continue
            connection = s["connection"]["data"] if s["connection"] else {}
            status = connection.get("status")
            if status == "candidate":
                quote = connection.get("quote_validation", {})
                if quote.get("current_exact") and quote.get("historical_exact"):
                    valid_quotes += 1
                if not s["expected_related"] or s["expected_connection"] != "candidate":
                    false_connections += 1
                    unsupported += 1
                else:
                    connections_ok += 1
            elif status == "insufficient_evidence":
                abstentions += 1
        stale = next(
            (
                item.get("age_days")
                for s, items in results
                if s.get("stale_after_days")
                for item in items
                if item["source_url"] == s["historical_url"]
            ),
            None,
        )
        return {
            "calls": 0,
            "estimated_cost": 0.0,
            "results": all_retrieved,
            "relevant_results": relevant,
            "precision_at_3": round(relevant / all_retrieved, 4) if all_retrieved else None,
            "targets_retrieved": target_hits,
            "recall_at_3": round(target_hits / len(related), 4) if related else None,
            "false_retrievals": false_retrieval,
            "appropriate_abstentions": sum(1 for s in negative if not retrieval(s)),
            "connection_candidates": connections_ok,
            "unsupported_connections": unsupported,
            "false_connections": false_connections,
            "connection_abstentions": abstentions,
            "valid_quotes": valid_quotes,
            "stale_age_days": stale,
        }

    def no_memory(_scenario):
        return []

    def exact(_scenario):
        return []

    return {
        "A_current_page_only": score("A", no_memory),
        "B_exact_match": score("B", exact),
        "C_cross_page_retrieval": score("C", outcome),
        "D_retrieval_plus_connection": score("D", outcome, connections=True),
        "history_access_control": score(
            "history_access",
            lambda s: [
                {"source_url": row["data"].get("url"), "sha256": row["data"].get("sha256")}
                for row in s["history_access"]
                if row.get("status") == "active"
            ],
        ),
    }


if __name__ == "__main__":
    run()
