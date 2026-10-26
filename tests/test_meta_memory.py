import json

import httpx
import pytest

from alive.providers import MetaProvider, ProviderError


async def test_meta_structured_output_usage_and_safe_errors(settings):
    settings.alive_meta_api_key = "private-test-key-never-returned"
    assert settings.alive_meta_api_key not in repr(settings)
    seen = {}

    def handle(request):
        seen.update(json.loads(request.content))
        assert request.headers["Authorization"] == "Bearer private-test-key-never-returned"
        return httpx.Response(
            200,
            json={
                "choices": [{"message": {"content": '{"summary":"ok"}'}, "finish_reason": "stop"}],
                "usage": {"prompt_tokens": 10, "completion_tokens": 8, "total_tokens": 18},
            },
        )

    result = await MetaProvider(settings).structured(
        "schema",
        {"observation": "x"},
        {"type": "object", "properties": {"summary": {"type": "string"}}},
        transport=httpx.MockTransport(handle),
    )
    assert json.loads(result.text)["summary"] == "ok" and result.usage["total_tokens"] == 18
    assert seen["model"] == "muse-spark-1.3" and seen["max_completion_tokens"] <= 4096
    assert "private-test-key" not in str(seen)
    for status, category in [(401, "authentication"), (429, "rate_limit"), (500, "server_error")]:
        transport = httpx.MockTransport(
            lambda _: httpx.Response(status, json={"error": "SENSITIVE_RAW_UPSTREAM"})
        )
        with pytest.raises(ProviderError) as error:
            await MetaProvider(settings).structured("x", {}, {}, transport=transport)
        assert error.value.category == category and "SENSITIVE" not in str(error.value)


def test_history_preview_approval_dedup_and_revocation(client):
    entries = {
        "entries": [
            {
                "url": "https://example.org/research?token=secret",
                "title": "Battery report",
                "content": "Battery endurance measured for 12 hours. password=secret",
            }
        ]
    }
    row = client.post("/api/v1/history/preview", json=entries).json()
    assert row["status"] == "preview" and "secret" not in json.dumps(row)
    assert client.get("/api/v1/memories").json() == []
    approved = client.post(
        "/api/v1/history/" + row["id"] + "/decision", json={"approved": True}
    ).json()
    assert len(approved["memory_ids"]) == 1
    assert len(client.get("/api/v1/memories").json()) == 1
    row2 = client.post("/api/v1/history/preview", json=entries).json()
    again = client.post(
        "/api/v1/history/" + row2["id"] + "/decision", json={"approved": True}
    ).json()
    assert again["memory_ids"] == []
    assert client.delete("/api/v1/history/" + row["id"]).json()["deleted"] == 1
    assert client.get("/api/v1/memories").json() == []
    assert (
        client.post(
            "/api/v1/history/preview",
            json={
                "entries": [{"url": "https://example.org/login", "title": "no", "content": "no"}]
            },
        ).status_code
        == 409
    )


def test_hybrid_fallback_is_explicit(client):
    client.post(
        "/api/v1/events",
        json={"event_type": "browser.dom_changed", "payload": {"text": "Battery endurance report"}},
    )
    result = client.post(
        "/api/v1/memories/search", json={"query": "battery", "mode": "hybrid"}
    ).json()
    assert result["mode"] == "sqlite_substring" and result["embedding"] is None
    assert result["results"][0]["source_event_id"]


def test_embedding_model_space_and_dimension_guard(client):
    class ControlledEmbedding:
        available = True
        model_id = "controlled-vector-fixture"
        revision = "fixture-v1"
        dimension = 384

        async def embed(self, texts):
            return [
                [
                    1.0 if i == (0 if "battery" in text.lower() else 1) else 0.0
                    for i in range(self.dimension)
                ]
                for text in texts
            ]

    embedding = ControlledEmbedding()
    client.app.state.memory.embedding = embedding
    preview = client.post(
        "/api/v1/history/preview",
        json={
            "entries": [
                {
                    "url": "https://example.org/battery",
                    "title": "battery",
                    "content": "battery endurance",
                },
                {
                    "url": "https://example.org/coolant",
                    "title": "coolant",
                    "content": "coolant temperature",
                },
            ]
        },
    ).json()
    approved = client.post(
        "/api/v1/history/" + preview["id"] + "/decision", json={"approved": True}
    ).json()
    assert client.post("/api/v1/memories/index", json={}).json()["indexed"] == 2
    result = client.post(
        "/api/v1/memories/search", json={"query": "battery", "mode": "vector"}
    ).json()
    assert result["results"][0]["id"] == approved["memory_ids"][0]
    assert result["results"][0]["metadata"]["url"] == "https://example.org/battery"
    embedding.revision = "fixture-v2"
    assert (
        client.post("/api/v1/memories/search", json={"query": "battery", "mode": "vector"}).json()[
            "results"
        ]
        == []
    )
    embedding.dimension = 383
    assert client.post("/api/v1/memories/index", json={}).status_code == 409
    assert client.delete("/api/v1/history/" + preview["id"]).json()["deleted"] == 2
