"""Run the frozen ALIVE-13 distractor-rich research-retrieval evaluation.

Controlled local API and retrieval only. Note generation uses a synthetic local fixture;
no external provider is called and no paid inference is performed.
"""

import asyncio
import hashlib
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
from alive.memory import ALL_MEMORY_TYPES
from alive.models import Base, Memory, now, uid
from alive.providers import MetaProvider
from alive.web_experience import digest
from alive.web_models import WebExperience

ROOT = Path(__file__).resolve().parents[1]
WORK = ROOT / ".alive/alive13-evaluation"
ARCHIVE = ROOT / "archives/ALIVE-13"
PROTOCOL = ARCHIVE / "protocol.json"
API = "/api/v1/browser-experience"
TOKEN = "alive13-evaluation-" + "x" * 24
SYNTHETIC_CALLS = []


async def fake_structured(*args, **kwargs):
    data = args[2] if len(args) > 2 else kwargs.get("data") or {}
    excerpt = data.get("untrusted_excerpt", "Controlled research excerpt.")
    quote = excerpt[:120].strip()
    if len(quote) < 5:
        quote = excerpt[:80]
    SYNTHETIC_CALLS.append(1)
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
    for _ in range(200):
        row = client.get(API + "/notes/" + note_id).json()
        if row["status"] != "reserved":
            return row
        time.sleep(0.02)
    raise AssertionError("note did not settle")


def corpus_id_for(rows, actual_id):
    return rows.get(actual_id)


def arm_result(rows, raw):
    return [
        {
            "memory_id": rows.get(item["memory_id"]),
            "actual_memory_id": item["memory_id"],
            "source_url": item.get("source_url"),
            "sha256": item.get("sha256"),
            "rank": item.get("rank"),
            "score": item.get("retrieval_score"),
        }
        for item in raw
    ]


def run():
    if WORK.exists():
        shutil.rmtree(WORK)
    WORK.mkdir(parents=True)
    protocol = json.loads(PROTOCOL.read_text(encoding="utf-8"))
    urls = sorted(
        {m["url"] for m in protocol["memories"]} | {q["url"] for q in protocol["queries"]}
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
    protocol_sha256 = hashlib.sha256(PROTOCOL.read_bytes()).hexdigest()
    result = {
        "protocol_version": protocol["protocol_version"],
        "protocol_sha256": protocol_sha256,
        "kind": protocol["kind"],
        "source_commit": subprocess.check_output(
            ["git", "rev-parse", "HEAD"], cwd=ROOT, text=True
        ).strip(),
        "paid_inference": False,
        "paid_calls": 0,
        "synthetic_note_calls": 0,
        "ordinary_memory_distractors": protocol["design"]["ordinary_memory_distractors"],
        "memories": [],
        "queries": [],
        "arms": {},
        "classification": None,
        "criteria": {},
    }
    with TestClient(create_app(settings), headers=headers) as client:
        k = client.app.state.kernel
        configured = client.post(
            "/api/v1/cognition/configuration",
            json={
                "session_calls": 200,
                "session_tokens": 1000000,
                "experiment_calls": 500,
                "experiment_tokens": 2000000,
                "investigation_tokens": 100000,
                "request_tokens": 30000,
            },
        )
        assert configured.status_code == 200, configured.text
        goal_rows = {}
        for goal in protocol["goals"]:
            goal_rows[goal["id"]] = post(client, "/goals", {"instruction": goal["instruction"]})

        async def seed_ordinary():
            template = protocol["design"]["ordinary_distractor_text"]
            async with k.db.sessions.begin() as session:
                for index in range(protocol["design"]["ordinary_memory_distractors"]):
                    session.add(
                        Memory(
                            id=uid(),
                            instance_id=k.instance_id,
                            content=template.format(index=index),
                            memory_type="experience",
                        )
                    )

        client.portal.call(seed_ordinary)

        memory_rows = {}
        memory_by_id = {m["id"]: m for m in protocol["memories"]}
        for memory_id in protocol["save_order"]:
            memory = memory_by_id[memory_id]
            goal = goal_rows[memory["goal_id"]]
            grant = post(
                client,
                "/grants",
                {
                    "goal_id": goal["id"],
                    "url": memory["url"],
                    "tab_key": "historical-" + memory_id,
                    "approved": True,
                },
            )
            snap = post(
                client,
                "/snapshots",
                {
                    "grant_id": grant["id"],
                    "url": memory["url"],
                    "title": memory["title"],
                    "text": memory["text"],
                    "reviewed_sha256": digest(memory["text"]),
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
                        "owner_correction": True,
                    },
                )["id"],
            )
            assert note["status"] == "validated", note
            saved = post(client, "/research/memories", {"note_id": note["id"]})
            memory_rows[memory_id] = saved
            if memory.get("stale_days"):

                async def age_memory(row_id=saved["id"], days=memory["stale_days"]):
                    async with k.db.sessions.begin() as session:
                        row = await session.get(WebExperience, row_id)
                        row.data = row.data | {
                            "reviewed_at": (now() - timedelta(days=days)).isoformat()
                        }

                client.portal.call(age_memory)
        result["synthetic_note_calls"] = len(SYNTHETIC_CALLS)

        async def reviewed_rows():
            async with k.db.sessions() as session:
                return {
                    row.id: row.data.get("reviewed_at")
                    for row in await client.app.state.research.web.rows(session, "research_memory")
                }

        reviewed = client.portal.call(reviewed_rows)
        result["memories"] = [
            {
                "corpus_id": memory_id,
                "actual_id": saved["id"],
                "goal_id": memory_by_id[memory_id]["goal_id"],
                "url": memory_by_id[memory_id]["url"],
                "stale_days": memory_by_id[memory_id].get("stale_days"),
                "reviewed_at": reviewed.get(saved["id"]),
            }
            for memory_id, saved in memory_rows.items()
        ]
        actual_to_corpus = {saved["id"]: memory_id for memory_id, saved in memory_rows.items()}

        async def scoped_rows(goal_id, current_url, current_sha):
            async with k.db.sessions() as session:
                rows = await client.app.state.research._eligible_research_rows(session, goal_id)
                return [
                    row
                    for row in rows
                    if row.data.get("url") != current_url and row.data.get("sha256") != current_sha
                ]

        async def recency_arm(goal_id, current_url, current_sha):
            rows = await scoped_rows(goal_id, current_url, current_sha)
            rows.sort(key=lambda row: (row.data.get("reviewed_at") or "", row.id), reverse=True)
            return [
                {
                    "memory_id": row.id,
                    "source_url": row.data.get("url"),
                    "sha256": row.data.get("sha256"),
                    "rank": index + 1,
                    "reviewed_at": row.data.get("reviewed_at"),
                }
                for index, row in enumerate(rows[:3])
            ]

        async def full_history(goal_id, current_url, current_sha):
            rows = await scoped_rows(goal_id, current_url, current_sha)
            rows.sort(key=lambda row: (row.data.get("reviewed_at") or "", row.id), reverse=True)
            return [
                {
                    "memory_id": row.id,
                    "source_url": row.data.get("url"),
                    "sha256": row.data.get("sha256"),
                    "rank": index + 1,
                }
                for index, row in enumerate(rows)
            ]

        async def alive12_arm(snapshot_id):
            research = client.app.state.research
            web = research.web
            async with research.k.db.sessions() as session:
                snapshot = await web.get(session, snapshot_id, "snapshot")
                goal = await web.get(session, snapshot.data["goal_id"], "goal")
                goal_id = goal.id
                current_url = snapshot.data["url"]
                current_sha = snapshot.data["sha256"]
                query = goal.data["instruction"] + " " + snapshot.data["text"][:1200]
                active = {
                    row.id: row
                    for row in await web.rows(session, "research_memory")
                    if row.status == "active" and row.data["goal_id"] == goal_id
                }
            # Frozen ALIVE-12 query and ordering. ALL_MEMORY_TYPES disables the
            # ALIVE-13 general-memory allowlist so the old candidate set is reproduced.
            retrieved = await research.memory.retrieve(
                query, mode="hybrid", top_k=15, memory_types=ALL_MEMORY_TYPES
            )
            results, seen = [], set()
            for item in retrieved.get("results", []):
                metadata = item.get("metadata") or {}
                research_id = metadata.get("research_memory_id")
                if (
                    item.get("memory_type") != "research_memory"
                    or item.get("instance_id") != research.k.instance_id
                    or metadata.get("goal_id") != goal_id
                    or metadata.get("url") == current_url
                    or metadata.get("sha256") == current_sha
                    or research_id not in active
                    or metadata.get("sha256") in seen
                ):
                    continue
                row = active[research_id]
                seen.add(metadata.get("sha256"))
                results.append(
                    {
                        "memory_id": row.id,
                        "source_url": row.data.get("url"),
                        "sha256": row.data.get("sha256"),
                        "rank": len(results) + 1,
                        "score": item.get("retrieval_score"),
                    }
                )
                if len(results) >= 3:
                    break
            return {
                "candidate_mode": retrieved.get("mode"),
                "candidate_count": len(retrieved.get("results", [])),
                "results": results,
            }

        def timed_sync(factory, repeats=3):
            values, output = [], None
            for _ in range(repeats):
                started = time.perf_counter()
                output = factory()
                values.append((time.perf_counter() - started) * 1000)
            values.sort()
            return output, values[len(values) // 2]

        def timed_portal(factory, repeats=3):
            values, output = [], None
            for _ in range(repeats):
                started = time.perf_counter()
                output = client.portal.call(factory)
                values.append((time.perf_counter() - started) * 1000)
            values.sort()
            return output, values[len(values) // 2]

        for query in protocol["queries"]:
            goal = goal_rows[query["goal_id"]]
            grant = post(
                client,
                "/grants",
                {
                    "goal_id": goal["id"],
                    "url": query["url"],
                    "tab_key": "current-" + query["id"],
                    "approved": True,
                },
            )
            current = post(
                client,
                "/snapshots",
                {
                    "grant_id": grant["id"],
                    "url": query["url"],
                    "title": "Current controlled source",
                    "text": query["text"],
                    "reviewed_sha256": digest(query["text"]),
                },
            )
            snapshot_id = current["snapshot"]["id"]
            corrected, corrected_latency = timed_sync(
                lambda: client_app_post(
                    client,
                    "/research/retrieve",
                    {
                        "snapshot_id": snapshot_id,
                        "top_k": 3,
                        "mode": "hybrid",
                    },
                )
            )
            recency, recency_latency = timed_portal(
                lambda: recency_arm(goal["id"], query["url"], current["snapshot"]["data"]["sha256"])
            )
            full, full_latency = timed_portal(
                lambda: full_history(
                    goal["id"], query["url"], current["snapshot"]["data"]["sha256"]
                )
            )
            old, old_latency = timed_portal(lambda: alive12_arm(snapshot_id))
            connection = None
            if corrected["results"]:
                connection = client_app_post(
                    client,
                    "/research/connections",
                    {
                        "snapshot_id": snapshot_id,
                        "memory_id": corrected["results"][0]["memory_id"],
                    },
                )
            result["queries"].append(
                {
                    "id": query["id"],
                    "goal_id": query["goal_id"],
                    "relevant": query["relevant"],
                    "label_rationale": query["label_rationale"],
                    "current_url": query["url"],
                    "snapshot_id": snapshot_id,
                    "arms": {
                        "A_recency": {
                            "results": arm_result(actual_to_corpus, recency),
                            "latency_ms": round(recency_latency, 3),
                        },
                        "B_alive12_unscoped": {
                            "results": arm_result(actual_to_corpus, old["results"]),
                            "latency_ms": round(old_latency, 3),
                            "candidate_count": old["candidate_count"],
                            "candidate_mode": old["candidate_mode"],
                        },
                        "C_corrected_scoped_lexical": {
                            "results": arm_result(actual_to_corpus, corrected["results"]),
                            "latency_ms": round(corrected_latency, 3),
                            "candidate_count": corrected.get("candidate_count"),
                            "scoped_count": corrected.get("scoped_count"),
                            "candidate_limit": corrected.get("candidate_limit"),
                        },
                        "D_full_history_access": {
                            "results": arm_result(actual_to_corpus, full),
                            "latency_ms": round(full_latency, 3),
                            "history_size": len(full),
                        },
                    },
                    "connection": connection,
                }
            )

    result["arms"] = summarize(result["queries"], protocol)
    result["criteria"] = criteria(result["arms"])
    result["classification"] = (
        "RETRIEVAL_ADVANTAGE_DEMONSTRATED"
        if all(result["criteria"].values())
        else "NO_RETRIEVAL_ADVANTAGE_DEMONSTRATED"
    )
    evidence = ARCHIVE / "evidence"
    evidence.mkdir(parents=True, exist_ok=True)
    (evidence / "retrieval-comparison.json").write_text(
        json.dumps(result, indent=2) + "\n", encoding="utf-8"
    )
    print(json.dumps(result["arms"], indent=2))
    print(json.dumps(result["criteria"], indent=2))
    print(result["classification"])
    print(evidence / "retrieval-comparison.json")


def client_app_post(client, path, body):
    response = client.post(API + path, json=body)
    assert response.status_code == 200, response.text
    return response.json()


def summarize(queries, protocol):
    memory_urls = {memory["id"]: memory["url"] for memory in protocol["memories"]}

    def top3(results):
        return [row["memory_id"] for row in results[:3]]

    def score(name, extract):
        positive = [q for q in queries if q["relevant"]]
        negative = [q for q in queries if not q["relevant"]]
        per_query = []
        for query in queries:
            results = extract(query)
            ids = top3(results)
            relevant = set(query["relevant"])
            rank = next(
                (index + 1 for index, memory_id in enumerate(ids) if memory_id in relevant),
                None,
            )
            per_query.append(
                {
                    "id": query["id"],
                    "retrieved": ids,
                    "relevant": query["relevant"],
                    "rank_of_first_relevant": rank,
                    "raw_results": results[:3],
                }
            )
        precision = sum(
            len(set(item["retrieved"]) & set(item["relevant"])) / 3
            for item in per_query
            if item["relevant"]
        ) / len(positive)
        recall = sum(
            len(set(item["retrieved"]) & set(item["relevant"])) / len(item["relevant"])
            for item in per_query
            if item["relevant"]
        ) / len(positive)
        mrr = sum(
            1 / item["rank_of_first_relevant"]
            for item in per_query
            if item["relevant"] and item["rank_of_first_relevant"]
        ) / len(positive)
        hit1 = sum(
            1 for item in per_query if item["relevant"] and item["rank_of_first_relevant"] == 1
        ) / len(positive)
        false_results = sum(
            1
            for item in per_query
            for memory_id in item["retrieved"]
            if memory_id not in item["relevant"]
        )
        false_queries = sum(
            1
            for item in per_query
            if any(memory_id not in item["relevant"] for memory_id in item["retrieved"])
        )
        total_results = sum(len(item["retrieved"]) for item in per_query)
        latencies = [query["arms"][name]["latency_ms"] for query in queries]
        latencies.sort()
        return {
            "positive_queries": len(positive),
            "negative_queries": len(negative),
            "precision_at_3": round(precision, 4),
            "recall_at_3": round(recall, 4),
            "mean_reciprocal_rank": round(mrr, 4),
            "relevant_at_rank_1": round(hit1, 4),
            "false_positive_results": false_results,
            "false_positive_queries": false_queries,
            "correct_abstentions": sum(
                1
                for query in negative
                for item in per_query
                if item["id"] == query["id"] and not item["retrieved"]
            ),
            "decoy_rate": round(false_results / total_results, 4) if total_results else None,
            "source_attribution_accuracy": round(
                sum(
                    1
                    for item in per_query
                    for row in item["raw_results"]
                    if row["memory_id"] in item["relevant"]
                    and row["source_url"] == memory_urls.get(row["memory_id"])
                )
                / max(
                    1,
                    sum(
                        1
                        for item in per_query
                        for row in item["raw_results"]
                        if row["memory_id"] in item["relevant"]
                    ),
                ),
                4,
            ),
            "missing_memory_failures": sum(
                1
                for item in per_query
                if item["relevant"] and not (set(item["retrieved"]) & set(item["relevant"]))
            ),
            "latency_ms_p50": round(latencies[len(latencies) // 2], 3),
            "per_query": per_query,
        }

    arms = {
        "A_recency": score("A_recency", lambda q: q["arms"]["A_recency"]["results"]),
        "B_alive12_unscoped": score(
            "B_alive12_unscoped", lambda q: q["arms"]["B_alive12_unscoped"]["results"]
        ),
        "C_corrected_scoped_lexical": score(
            "C_corrected_scoped_lexical",
            lambda q: q["arms"]["C_corrected_scoped_lexical"]["results"],
        ),
    }
    positive = [q for q in queries if q["relevant"]]
    arms["D_full_history_access"] = {
        "positive_queries": len(positive),
        "mean_history_size": round(
            sum(len(q["arms"]["D_full_history_access"]["results"]) for q in queries) / len(queries),
            2,
        ),
        "history_contains_relevant": round(
            sum(
                1
                for q in positive
                if set(q["relevant"])
                & {row["memory_id"] for row in q["arms"]["D_full_history_access"]["results"]}
            )
            / len(positive),
            4,
        ),
        "note": "Access control only; no result limit or ranking is applied.",
    }
    return arms


def criteria(arms):
    corrected = arms["C_corrected_scoped_lexical"]
    recency = arms["A_recency"]
    return {
        "crowding_regression": corrected["missing_memory_failures"] == 0,
        "recall_at_3_improvement_over_recency": round(
            corrected["recall_at_3"] - recency["recall_at_3"], 4
        )
        >= 0.20,
        "mrr_improvement_over_recency": round(
            corrected["mean_reciprocal_rank"] - recency["mean_reciprocal_rank"], 4
        )
        >= 0.20,
        "missing_memory_failures_not_worse_than_recency": (
            corrected["missing_memory_failures"] <= recency["missing_memory_failures"]
        ),
        "negative_queries_abstain": (
            corrected["correct_abstentions"] == corrected["negative_queries"]
        ),
    }


if __name__ == "__main__":
    run()
