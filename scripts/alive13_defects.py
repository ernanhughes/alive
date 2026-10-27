"""Reproduce the ALIVE-12 defects used as the ALIVE-13 starting evidence.

The old retrieval path is reconstructed by invoking the shared MemoryService with the
ALIVE-13 type allowlist disabled. No external provider is called.
"""

import asyncio
import json
import shutil
import time
from pathlib import Path
from types import SimpleNamespace

from fastapi.testclient import TestClient

from alive.app import create_app
from alive.config import Settings
from alive.db import Database
from alive.memory import ALL_MEMORY_TYPES
from alive.models import Base, Memory, uid
from alive.providers import MetaProvider
from alive.web_experience import digest

ROOT = Path(__file__).resolve().parents[1]
WORK = ROOT / ".alive/alive13-defects"
ARCHIVE = ROOT / "archives/ALIVE-13"
API = "/api/v1/browser-experience"
TOKEN = "alive13-defects-" + "x" * 24
HISTORICAL = "http://127.0.0.1:9310/historical/target"
CURRENT = "http://127.0.0.1:9310/current/query"
GOAL = "Find Python memory management research about reference counting and cycle collection"
QUERY = "Python memory management reference counting cycle collector"
TARGET_TEXT = (
    "Python memory management research target uses reference counting and a cycle collector."
)
SENTINEL = "RESEARCH_SENTINEL_ALPHA"

CALLS = []


async def fake_structured(*args, **kwargs):
    data = args[2] if len(args) > 2 else kwargs.get("data") or {}
    excerpt = data.get("untrusted_excerpt", "Controlled excerpt.")
    CALLS.append(1)
    return SimpleNamespace(
        text=json.dumps(
            {
                "summary": "Controlled historical note.",
                "evidence_quote": excerpt[:100],
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
    for _ in range(200):
        row = client.get(API + "/notes/" + note_id).json()
        if row["status"] != "reserved":
            return row
        time.sleep(0.02)
    raise AssertionError("note did not settle")


def old_retrieve(client, query, top_k=15):
    async def call():
        return await client.app.state.memory.retrieve(
            query, "text", top_k, memory_types=ALL_MEMORY_TYPES
        )

    return client.portal.call(call)


def run():
    if WORK.exists():
        shutil.rmtree(WORK)
    WORK.mkdir(parents=True)
    settings = Settings(
        _env_file=None,
        alive_meta_api_key="",
        alive_embedding_enabled=False,
        alive_native_test_pages=",".join([HISTORICAL, CURRENT]),
        alive_api_token=TOKEN,
        database_url=f"sqlite+aiosqlite:///{(WORK / 'defects.db').as_posix()}",
        alive_workspace=WORK / "workspace",
    )

    async def schema():
        database = Database(settings.database_url)
        async with database.engine.begin() as connection:
            await connection.run_sync(Base.metadata.create_all)
        await database.engine.dispose()

    asyncio.run(schema())
    evidence = {
        "source_base": "af12bc88c91a85558873d01579dba93fdd6b1bbf",
        "paid_inference": False,
        "synthetic_note_calls": 0,
        "method": (
            "The frozen ALIVE-12 query and post-filter are reproduced against the current "
            "database. ALL_MEMORY_TYPES disables the ALIVE-13 general-memory allowlist "
            "so the old unscoped candidate set is visible."
        ),
        "a1_unscoped_retrieval": {},
        "a2_general_cognition_isolation": {},
        "a4_relation_labels": {},
    }
    with TestClient(create_app(settings), headers={"Authorization": "Bearer " + TOKEN}) as client:
        k = client.app.state.kernel
        goal = post(client, "/goals", {"instruction": GOAL})

        async def seed_ordinary():
            async with k.db.sessions.begin() as session:
                for index in range(60):
                    session.add(
                        Memory(
                            id=uid(),
                            instance_id=k.instance_id,
                            content=(
                                "Python memory management ordinary retained note "
                                + str(index)
                                + " about garbage collection."
                            ),
                            memory_type="experience",
                        )
                    )

        client.portal.call(seed_ordinary)
        grant = post(
            client,
            "/grants",
            {
                "goal_id": goal["id"],
                "url": HISTORICAL,
                "tab_key": "defects-historical",
                "approved": True,
            },
        )
        historical = post(
            client,
            "/snapshots",
            {
                "grant_id": grant["id"],
                "url": HISTORICAL,
                "title": "Controlled historical target",
                "text": TARGET_TEXT,
                "reviewed_sha256": digest(TARGET_TEXT),
            },
        )
        note = wait(
            client,
            post(
                client,
                "/analyse",
                {
                    "snapshot_id": historical["snapshot"]["id"],
                    "reviewed_sha256": historical["snapshot"]["data"]["sha256"],
                    "send_to_meta": True,
                    "owner_correction": True,
                },
            )["id"],
        )
        saved = post(client, "/research/memories", {"note_id": note["id"]})
        current_grant = post(
            client,
            "/grants",
            {"goal_id": goal["id"], "url": CURRENT, "tab_key": "defects-current", "approved": True},
        )
        current = post(
            client,
            "/snapshots",
            {
                "grant_id": current_grant["id"],
                "url": CURRENT,
                "title": "Controlled current source",
                "text": QUERY,
                "reviewed_sha256": digest(QUERY),
            },
        )
        old = old_retrieve(client, GOAL + " " + QUERY)
        old_research = [row for row in old["results"] if row["memory_type"] == "research_memory"]
        corrected = post(
            client,
            "/research/retrieve",
            {"snapshot_id": current["snapshot"]["id"], "top_k": 3, "mode": "hybrid"},
        )
        evidence["a1_unscoped_retrieval"] = {
            "ordinary_distractors": 60,
            "old_top_k": 15,
            "old_candidates_returned": len(old["results"]),
            "old_research_candidates_returned": len(old_research),
            "old_target_found": any(row["id"] == saved["id"] for row in old_research),
            "corrected_target_found": any(
                row["memory_id"] == saved["id"] for row in corrected["results"]
            ),
            "corrected_rank": next(
                (row["rank"] for row in corrected["results"] if row["memory_id"] == saved["id"]),
                None,
            ),
            "corrected_scoped_count": corrected["scoped_count"],
            "corrected_candidate_count": corrected["candidate_count"],
            "failure_reproduced": not any(row["id"] == saved["id"] for row in old_research),
        }

        async def add_sentinel_projection():
            async with k.db.sessions.begin() as session:
                projection = await session.get(Memory, saved["data"]["memory_projection_id"])
                projection.content = "Python reference counting and cycle collector. " + SENTINEL
                session.add(
                    Memory(
                        id=uid(),
                        instance_id=k.instance_id,
                        content="Python cycle collector ordinary experience note.",
                        memory_type="experience",
                    )
                )

        client.portal.call(add_sentinel_projection)
        old_general = old_retrieve(client, "cycle collector sentinel", top_k=10)

        async def new_general():
            return await client.app.state.memory.retrieve("cycle collector sentinel", "text", 10)

        new_general_result = client.portal.call(new_general)
        evidence["a2_general_cognition_isolation"] = {
            "sentinel": SENTINEL,
            "old_general_retrieval_contains_sentinel": SENTINEL
            in json.dumps(old_general["results"], default=str),
            "new_general_retrieval_contains_sentinel": SENTINEL
            in json.dumps(new_general_result["results"], default=str),
            "new_general_retrieval_contains_ordinary_memory": any(
                "ordinary experience note" in row["content"]
                for row in new_general_result["results"]
            ),
            "new_general_types": sorted(
                {row["memory_type"] for row in new_general_result["results"]}
            ),
            "full_snapshot_regression": (
                "tests/test_research_memory.py::"
                "test_general_investigation_snapshot_excludes_research_memory_sentinel"
            ),
        }

    evidence["synthetic_note_calls"] = len(CALLS)
    evidence["a4_relation_labels"] = relation_labels()
    (ARCHIVE / "evidence").mkdir(parents=True, exist_ok=True)
    (ARCHIVE / "evidence/pre-fix-defects.json").write_text(
        json.dumps(evidence, indent=2) + "\n", encoding="utf-8"
    )
    print(json.dumps(evidence, indent=2))


def relation_labels():
    fixtures = [
        {
            "id": "contradictory",
            "historical": "Persistent memory improves agent task success in this benchmark.",
            "current": "Persistent memory does not improve agent task success in this benchmark.",
            "shared": 7,
        },
        {
            "id": "unrelated-generic",
            "historical": "The memory system stores records for later review.",
            "current": "The legal system stores records for later review.",
            "shared": 5,
        },
        {
            "id": "competing-methods",
            "historical": "A deterministic retrieval rule chooses the most recent source.",
            "current": "A learned retrieval policy selects sources from observed feedback.",
            "shared": 1,
        },
        {
            "id": "no-inspectable-overlap",
            "historical": "Quantum stabilizer codes protect logical qubits.",
            "current": "The compiler optimizes tail calls.",
            "shared": 0,
        },
    ]
    results = []
    for fixture in fixtures:
        shared = fixture["shared"]
        old = (
            "same_concept"
            if shared >= 2
            else "complementary"
            if shared == 1
            else "no_supported_connection"
        )
        new = (
            "topic_overlap_candidate"
            if shared >= 2
            else "weak_lexical_overlap"
            if shared == 1
            else "insufficient_evidence"
        )
        results.append(
            fixture
            | {
                "old_label": old,
                "new_label": new,
                "old_implication": "overstated semantic relation",
                "new_implication": "lexical overlap only; no agreement, support or contradiction",
            }
        )
    return results


if __name__ == "__main__":
    run()
