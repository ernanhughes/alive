import time
from collections.abc import AsyncIterator
from dataclasses import dataclass, field
from typing import Protocol

import httpx


@dataclass
class Generation:
    text: str
    usage: dict = field(default_factory=dict)
    latency_ms: float = 0


class ModelProvider(Protocol):
    provider_id: str
    model_id: str

    def capabilities(self) -> dict: ...
    async def generate(self, prompt: str) -> Generation: ...
    async def decide(self, prompt: str) -> dict: ...
    def stream(self, prompt: str) -> AsyncIterator[str]: ...


class MockProvider:
    provider_id = "mock"
    model_id = "deterministic-v1"

    def capabilities(self):
        return {"text": True, "structured": True, "vision": False, "streaming": True}

    async def generate(self, prompt):
        return Generation(
            f"Observation examined: {prompt.strip()}\nFollow-up: verify this observation."
        )

    async def decide(self, prompt):
        return {"action": "propose_goal", "reason": prompt[:200]}

    async def stream(self, prompt):
        yield (await self.generate(prompt)).text


class MetaProvider:
    """Configurable OpenAI-compatible Meta gateway; no assumed endpoint/model."""

    provider_id = "meta"

    def __init__(self, settings):
        self.settings = settings
        self.model_id = settings.alive_meta_model

    def capabilities(self):
        return {
            "text": True,
            "structured": True,
            "vision": False,
            "streaming": False,
            "configured": bool(
                self.settings.alive_meta_url and self.model_id and self.settings.alive_meta_api_key
            ),
        }

    async def generate(self, prompt):
        if not self.capabilities()["configured"]:
            raise RuntimeError("Meta gateway is not configured")
        started = time.monotonic()
        async with httpx.AsyncClient(timeout=60) as client:
            response = await client.post(
                self.settings.alive_meta_url,
                headers={"Authorization": f"Bearer {self.settings.alive_meta_api_key}"},
                json={"model": self.model_id, "messages": [{"role": "user", "content": prompt}]},
            )
            if response.is_error:
                raise RuntimeError(f"Meta gateway returned HTTP {response.status_code}")
            data = response.json()
            return Generation(
                data["choices"][0]["message"]["content"],
                data.get("usage", {}),
                (time.monotonic() - started) * 1000,
            )

    async def decide(self, prompt):
        import json

        return json.loads((await self.generate(prompt + "\nReturn a JSON object only.")).text)

    async def stream(self, prompt):
        # Explicit buffered fallback; capabilities never advertises native streaming.
        yield (await self.generate(prompt)).text
