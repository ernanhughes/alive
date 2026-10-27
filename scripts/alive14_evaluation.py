"""Run the frozen ALIVE-14 held-out retrieval comparison and zero-cost consent dry-run."""

import argparse
import asyncio
import hashlib
import json
import shutil
import statistics
import subprocess
import time
from pathlib import Path

from fastapi.testclient import TestClient

from alive.app import create_app
from alive.config import Settings
from alive.db import Database
from alive.models import Base, uid
from alive.web_experience import digest
from alive.web_models import WebExperience

ROOT = Path(__file__).resolve().parents[1]
ARCHIVE = ROOT / "archives/ALIVE-14"
PROTOCOL = ARCHIVE / "protocol.json"
API = "/api/v1/browser-experience"
TOKEN = "alive14-evaluation-" + "x" * 24


def post(client, path, body, expected=200):
    response = client.post(API + path, json=body)
    assert response.status_code == expected, response.text
    return response.json()


def seed_memories(client, goal_rows, memories):
    async def seed():
        async with client.app.state.kernel.db.sessions.begin() as session:
            for memory in memories:
                text = memory["text"]
                session.add(
                    WebExperience(
                        id=uid(),
                        instance_id=client.app.state.kernel.instance_id,
                        kind="research_memory",
                        status="active",
                        data={
                            "goal_id": goal_rows[memory["goal_id"]]["id"],
                            "url": memory["url"],
                            "title": memory.get("title", "Held-out research"),
                            "excerpt": text,
                            "sha256": digest(text),
                            "reviewed_at": memory.get("reviewed_at", "2026-10-27T18:00:00+00:00"),
                            "source_kind": "reviewed_browser_excerpt",
                        },
                    )
                )

    client.portal.call(seed)


def scoped_rows(client, goal_id, current_url, current_sha):
    async def load():
        async with client.app.state.kernel.db.sessions() as session:
            rows = await client.app.state.research._eligible_research_rows(session, goal_id)
            return [
                row
                for row in rows
                if row.data.get("url") != current_url and row.data.get("sha256") != current_sha
            ]

    return client.portal.call(load)


def row_result(row, rank):
    return {
        "actual_memory_id": row.id,
        "source_url": row.data["url"],
        "sha256": row.data["sha256"],
        "rank": rank,
    }


def recency(client, goal_id, current_url, current_sha):
    rows = scoped_rows(client, goal_id, current_url, current_sha)
    rows.sort(key=lambda row: (row.data.get("reviewed_at") or "", row.id), reverse=True)
    return [row_result(row, index + 1) for index, row in enumerate(rows[:3])]


def full_history(client, goal_id, current_url, current_sha):
    rows = scoped_rows(client, goal_id, current_url, current_sha)
    rows.sort(key=lambda row: (row.data.get("reviewed_at") or "", row.id), reverse=True)
    return [row_result(row, index + 1) for index, row in enumerate(rows)]


def summarize(queries, arm, memories):
    def top3(results):
        return [row.get("corpus_memory_id") for row in results[:3]]

    def score(extract):
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
                    "raw_results": results,
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
        total_results = sum(len(item["retrieved"]) for item in per_query)
        latencies = [query["arms"][arm]["latency_ms"] for query in queries]
        return {
            "positive_queries": len(positive),
            "negative_queries": len(negative),
            "precision_at_3": round(precision, 4),
            "recall_at_3": round(recall, 4),
            "mean_reciprocal_rank": round(mrr, 4),
            "relevant_at_rank_1": round(hit1, 4),
            "false_positive_results": false_results,
            "correct_abstentions": sum(
                1
                for query in negative
                for item in per_query
                if item["id"] == query["id"] and not item["retrieved"]
            ),
            "decoy_rate": round(false_results / total_results, 4) if total_results else None,
            "missing_memory_failures": sum(
                1
                for item in per_query
                if item["relevant"] and not (set(item["retrieved"]) & set(item["relevant"]))
            ),
            "latency_ms_p50": round(statistics.median(latencies), 3),
            "per_query": per_query,
        }

    if arm == "D_full_history":
        positive = [q for q in queries if q["relevant"]]
        return {
            "positive_queries": len(positive),
            "mean_history_size": round(
                statistics.mean(len(query["arms"][arm]["results"]) for query in queries), 2
            ),
            "history_contains_relevant": round(
                sum(
                    1
                    for query in positive
                    if set(query["relevant"])
                    & {row["actual_memory_id"] for row in query["arms"][arm]["results"]}
                )
                / len(positive),
                4,
            ),
            "per_query": [
                {
                    "id": query["id"],
                    "retrieved": [row["actual_memory_id"] for row in query["arms"][arm]["results"]],
                    "relevant": query["relevant"],
                }
                for query in queries
            ],
        }
    return score(lambda query: query["arms"][arm]["results"])


def timed(factory, repeats=3):
    values, output = [], None
    for _ in range(repeats):
        started = time.perf_counter()
        output = factory()
        values.append((time.perf_counter() - started) * 1000)
    return output, round(statistics.median(values), 3)


def run(dataset):
    if dataset == "development":
        work = ROOT / ".alive/alive14-development"
        evidence_dir = work / "evidence"
    else:
        work = ROOT / ".alive/alive14-evaluation"
        evidence_dir = ARCHIVE / "evidence"
    if work.exists():
        shutil.rmtree(work)
    work.mkdir(parents=True)
    evidence_dir.mkdir(parents=True, exist_ok=True)
    protocol = json.loads(PROTOCOL.read_text(encoding="utf-8"))
    if dataset == "development":
        data = protocol["design"]["development_cases"]
    else:
        data = {
            "goals": protocol["goals"],
            "memories": protocol["memories"],
            "queries": protocol["queries"],
        }
    all_urls = sorted({m["url"] for m in data["memories"]} | {q["url"] for q in data["queries"]})
    settings = Settings(
        _env_file=None,
        alive_meta_api_key="",
        alive_embedding_enabled=False,
        alive_native_test_pages=",".join(all_urls),
        alive_api_token=TOKEN,
        database_url=f"sqlite+aiosqlite:///{(work / 'evaluation.db').as_posix()}",
        alive_workspace=work / "workspace",
    )

    async def schema():
        database = Database(settings.database_url)
        async with database.engine.begin() as connection:
            await connection.run_sync(Base.metadata.create_all)
        await database.engine.dispose()

    asyncio.run(schema())
    protocol_sha256 = hashlib.sha256(PROTOCOL.read_bytes()).hexdigest()
    source_commit = subprocess.check_output(
        ["git", "rev-parse", "HEAD"], cwd=ROOT, text=True
    ).strip()
    protocol_commit = subprocess.check_output(
        ["git", "log", "-1", "--format=%H", "--", str(PROTOCOL.relative_to(ROOT))],
        cwd=ROOT,
        text=True,
    ).strip()
    result = {
        "protocol_version": protocol["protocol_version"],
        "protocol_sha256": protocol_sha256,
        "protocol_commit": protocol_commit,
        "dataset": dataset,
        "source_commit": source_commit,
        "paid_inference": False,
        "paid_calls": 0,
        "queries": [],
        "arms": {},
        "criteria": {},
        "classification": None,
    }
    with TestClient(create_app(settings), headers={"Authorization": "Bearer " + TOKEN}) as client:
        goal_rows = {
            goal["id"]: post(client, "/goals", {"instruction": goal["instruction"]})
            for goal in data["goals"]
        }
        seed_memories(client, goal_rows, data["memories"])
        actual_to_corpus = {}
        for memory in data["memories"]:
            actual_to_corpus[digest(memory["text"])] = memory["id"]
        for query in data["queries"]:
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
            current_sha = current["snapshot"]["data"]["sha256"]

            def api_arm(ranker):
                return lambda: post(
                    client,
                    "/research/retrieve",
                    {
                        "snapshot_id": snapshot_id,
                        "top_k": 3,
                        "mode": "hybrid",
                        "ranker": ranker,
                    },
                )

            old, old_latency = timed(api_arm("alive13-scoped-lexical-v1"))
            new, new_latency = timed(api_arm("alive14-bm25-v1"))
            replay = post(
                client,
                "/research/retrieve",
                {
                    "snapshot_id": snapshot_id,
                    "top_k": 3,
                    "mode": "hybrid",
                    "ranker": "alive14-bm25-v1",
                },
            )
            deterministic = [row["memory_id"] for row in replay["results"]] == [
                row["memory_id"] for row in new["results"]
            ]
            recency_results, recency_latency = timed(
                lambda: recency(client, goal["id"], query["url"], current_sha)
            )
            history_results, history_latency = timed(
                lambda: full_history(client, goal["id"], query["url"], current_sha)
            )

            def map_results(payload):
                return [
                    {
                        "actual_memory_id": row["memory_id"],
                        "source_url": row["source_url"],
                        "sha256": row["sha256"],
                        "rank": row["rank"],
                        "score": row.get("retrieval_score"),
                    }
                    for row in payload["results"]
                ]

            result["queries"].append(
                {
                    "id": query["id"],
                    "goal_id": query["goal_id"],
                    "snapshot_id": snapshot_id,
                    "deterministic": deterministic,
                    "relevant": query["relevant"],
                    "label_rationale": query.get("label_rationale"),
                    "arms": {
                        "A_recency": {
                            "results": [
                                {
                                    **row,
                                    "actual_memory_id": actual_to_corpus.get(row["sha256"]),
                                }
                                for row in recency_results
                            ],
                            "latency_ms": recency_latency,
                        },
                        "B_alive13": {
                            "results": map_results(old),
                            "latency_ms": old_latency,
                            "ranking_version": old["ranking_version"],
                            "candidate_count": old["candidate_count"],
                        },
                        "C_alive14_bm25": {
                            "results": map_results(new),
                            "latency_ms": new_latency,
                            "ranking_version": new["ranking_version"],
                            "candidate_count": new["candidate_count"],
                            "qualified_count": new["qualified_count"],
                        },
                        "D_full_history": {
                            "results": [
                                {
                                    **row,
                                    "actual_memory_id": actual_to_corpus.get(row["sha256"]),
                                }
                                for row in history_results
                            ],
                            "latency_ms": history_latency,
                        },
                    },
                }
            )
        # Map actual IDs to corpus labels for the metric reader.
        for query in result["queries"]:
            for arm in query["arms"].values():
                for row in arm["results"]:
                    row["corpus_memory_id"] = actual_to_corpus.get(row.get("sha256"))
        result["arms"] = {
            "A_recency": summarize(result["queries"], "A_recency", data["memories"]),
            "B_alive13": summarize(result["queries"], "B_alive13", data["memories"]),
            "C_alive14_bm25": summarize(result["queries"], "C_alive14_bm25", data["memories"]),
            "D_full_history": summarize(result["queries"], "D_full_history", data["memories"]),
        }
        if dataset == "held_out":
            result["criteria"] = criteria(result, data)
            result["classification"] = (
                "RETRIEVAL_ADVANTAGE_DEMONSTRATED"
                if all(result["criteria"].values())
                else "NO_RETRIEVAL_ADVANTAGE_DEMONSTRATED"
            )
            result["relationship_dry_run"] = relationship_dry_run(client, result, data)
        else:
            result["criteria"] = {"development_run": True}
            result["classification"] = "DEVELOPMENT_ONLY"

    (evidence_dir / f"retrieval-comparison-{dataset}.json").write_text(
        json.dumps(result, indent=2) + "\n", encoding="utf-8"
    )
    print(json.dumps(result["arms"], indent=2))
    print(json.dumps(result["criteria"], indent=2))
    print(result["classification"])
    print(evidence_dir / f"retrieval-comparison-{dataset}.json")


def criteria(result, data):
    c = result["arms"]["C_alive14_bm25"]
    b = result["arms"]["B_alive13"]
    by_id = {q["id"]: q for q in result["queries"]}
    long_cases = {
        "Q1": "H01",
        "Q4": "H07",
        "Q7": "H13",
    }
    return {
        "long_excerpt_regression": all(
            by_id[query]["arms"]["C_alive14_bm25"]["results"]
            and by_id[query]["arms"]["C_alive14_bm25"]["results"][0].get("corpus_memory_id")
            == target
            for query, target in long_cases.items()
        ),
        "generic_overlap_abstention": all(
            not by_id[query]["arms"]["C_alive14_bm25"]["results"] for query in ("Q3", "Q6", "Q9")
        ),
        "recall_at_3_not_worse_than_alive13": c["recall_at_3"] >= b["recall_at_3"],
        "mrr_not_worse_than_alive13": c["mean_reciprocal_rank"] >= b["mean_reciprocal_rank"],
        "deterministic": all(query["deterministic"] for query in result["queries"]),
        "no_provider_call_for_retrieval": True,
    }


def relationship_dry_run(client, result, data):
    selected = [query for query in result["queries"] if query["id"] in ("Q1", "Q4", "Q7")]
    records = []
    for query in selected:
        snapshot_id = query["snapshot_id"]
        top = query["arms"]["C_alive14_bm25"]["results"][0]
        preview = post(
            client,
            "/research/outbound/preview",
            {"snapshot_id": snapshot_id, "research_id": top["actual_memory_id"]},
        )
        authorized = post(
            client,
            "/research/outbound/authorize",
            {
                "consent_id": preview["id"],
                "payload_sha256": preview["payload_sha256"],
                "approved": True,
            },
        )
        analysis = post(
            client,
            "/research/relationships",
            {"consent_id": preview["id"]},
        )
        records.append(
            {
                "query_id": query["id"],
                "consent_id": preview["id"],
                "authorized_status": authorized["status"],
                "external": preview["external"],
                "provider": preview["provider"],
                "preview_payload_sha256": preview["payload_sha256"],
                "analysis_status": analysis["analysis"]["status"],
                "validation": analysis["analysis"]["data"].get("validation"),
                "connection_relation": analysis["connection"]["data"].get("relation_type")
                if analysis.get("connection")
                else None,
                "connection_quotes_exact": (
                    analysis["connection"]["data"].get("current_quote")
                    in preview["current_source"]["excerpt"]
                    and analysis["connection"]["data"].get("historical_quote")
                    in preview["historical_source"]["excerpt"]
                    if analysis.get("connection")
                    else False
                ),
            }
        )
    return {
        "provider": "local_stub",
        "external": False,
        "paid_calls": 0,
        "conditions": {
            "A_current_only": (
                "prepared in the protocol; not scored because no owner ratings were collected"
            ),
            "B_current_plus_retrieved_history": "local-stub consent and analysis path exercised",
            "C_history_without_synthesis": "historical source remains directly inspectable",
        },
        "owner_ratings": "SCRIPTED_ONLY",
        "owner_rating_note": (
            "Only scripted plumbing feedback was exercised natively; no human owner ratings "
            "were collected."
        ),
        "records": records,
        "note": (
            "The local stub validates consent, payload binding, structured output, quotation "
            "validation and persistence. It does not measure relationship usefulness."
        ),
    }


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--dataset", choices=["development", "held_out"], default="held_out")
    run(parser.parse_args().dataset)
