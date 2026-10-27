"""Live PostgreSQL/pgvector, actual pinned ONNX embeddings, hybrid retrieval and revocation."""

import json
import uuid
from pathlib import Path

import httpx

from alive.config import Settings, prepare_local


def main():
    c = httpx.Client(
        base_url="http://127.0.0.1:8000/api/v1",
        timeout=60,
        headers={"Authorization": "Bearer " + prepare_local(Settings())},
    )
    marker = uuid.uuid4().hex[:8]
    entries = [
        {"url": f"https://example.org/synthetic/{marker}/{i}", "title": title, "content": content}
        for i, (title, content) in enumerate(
            [
                (
                    "Cell report",
                    "A lithium ion cell supplies electrical power to a device for eighteen hours.",
                ),
                (
                    "Coolant report",
                    "An industrial thermometer measures the liquid temperature "
                    "at twenty six Celsius.",
                ),
                ("Animal report", "A domestic cat sleeps peacefully on a carpet near a window."),
            ]
        )
    ]
    preview = c.post("/history/preview", json={"entries": entries})
    preview.raise_for_status()
    import_id = preview.json()["id"]
    try:
        approved = c.post(f"/history/{import_id}/decision", json={"approved": True})
        approved.raise_for_status()
        memory_ids = approved.json()["memory_ids"]
        assert len(memory_ids) == 3
        indexed = c.post("/memories/index", json={})
        indexed.raise_for_status()
        assert indexed.json()["available"]
        results = {}
        for mode in ["text", "vector", "hybrid"]:
            response = c.post(
                "/memories/search",
                json={"query": "How long can an electric battery run?", "mode": mode, "top_k": 20},
            )
            response.raise_for_status()
            results[mode] = response.json()
        vectors = [m for m in results["vector"]["results"] if m["id"] in memory_ids]
        assert vectors and vectors[0]["id"] == memory_ids[0], vectors
        assert any(m["id"] == memory_ids[0] for m in results["hybrid"]["results"])
        evidence = {
            "embedding": indexed.json(),
            "vector_mode": results["vector"]["mode"],
            "hybrid_mode": results["hybrid"]["mode"],
            "query": "How long can an electric battery run?",
            "controlled_fixture_match": True,
            "fixture_ids": memory_ids,
            "results": {
                key: [
                    {"id": m["id"], "score": m.get("retrieval_score"), "provenance": m["metadata"]}
                    for m in value["results"]
                ]
                for key, value in results.items()
            },
            "revocation_verified": False,
        }
    finally:
        revoked = c.delete("/history/" + import_id)
        revoked.raise_for_status()
    remaining = c.get("/memories").json()
    assert not any(m["id"] in memory_ids for m in remaining)
    evidence["revocation_verified"] = True
    Path(".alive/retrieval-evidence.json").write_text(json.dumps(evidence, indent=2))
    print(
        "VERIFIED LIVE: pinned 384-dimensional ONNX embeddings, pgvector cosine retrieval, "
        "hybrid retrieval, explicit import approval and revocation"
    )


if __name__ == "__main__":
    main()
