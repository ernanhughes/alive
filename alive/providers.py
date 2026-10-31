import time
import uuid
from collections.abc import AsyncIterator
from dataclasses import dataclass, field
from typing import Protocol
from urllib.parse import urlsplit

import httpx

from alive.model_contracts import ApprovedModelDestination


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


def meta_endpoint_url(settings):
    """Resolve the exact dispatch endpoint without reading credentials."""
    return settings.alive_meta_url or (
        settings.alive_meta_base_url.rstrip("/") + "/chat/completions"
    )


def meta_endpoint_host(settings):
    """The host model requests are sent to, for owner disclosure. No credential is read."""
    return urlsplit(meta_endpoint_url(settings)).hostname


class MetaProvider:
    """Meta Model API chat completions; bounded native structured decoding."""

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
            "configured": bool(self.model_id and self.settings.alive_meta_api_key),
        }

    async def discover(self):
        if not self.settings.alive_meta_api_key:
            return {"status": "blocked", "reason": "credentials_not_configured", "models": []}
        try:
            async with httpx.AsyncClient(
                timeout=self.settings.alive_meta_timeout, trust_env=False, follow_redirects=False
            ) as client:
                response = await client.get(
                    self.settings.alive_meta_base_url.rstrip("/") + "/models",
                    headers={"Authorization": f"Bearer {self.settings.alive_meta_api_key}"},
                )
                if response.is_error:
                    return {
                        "status": "unavailable",
                        "http_status": response.status_code,
                        "models": [],
                    }
                return {"status": "available", "models": [x["id"] for x in response.json()["data"]]}
        except (httpx.HTTPError, ValueError, KeyError):
            return {"status": "unavailable", "reason": "discovery_failed", "models": []}

    async def structured(
        self,
        instructions,
        data,
        schema,
        *,
        model=None,
        max_output=None,
        correlation=None,
        transport=None,
        destination: ApprovedModelDestination | None = None,
    ):
        import json

        if not self.capabilities()["configured"]:
            raise ProviderError("credentials_not_configured")
        body = {
            "model": model or self.model_id,
            "messages": [
                {"role": "developer", "content": instructions},
                {"role": "user", "content": json.dumps(data, ensure_ascii=False)},
            ],
            "max_completion_tokens": max_output or self.settings.alive_meta_max_output,
            "reasoning_effort": "minimal",
            "response_format": {
                "type": "json_schema",
                "json_schema": {"name": "alive_structured_output", "schema": schema},
            },
        }
        return await self._request(body, correlation, transport, destination=destination)

    async def _request(self, body, correlation=None, transport=None, *, destination=None):
        if not self.capabilities()["configured"]:
            raise ProviderError("credentials_not_configured")
        started = time.monotonic()
        url = meta_endpoint_url(self.settings)
        if destination is not None and url != destination.endpoint:
            raise ProviderError("destination_mismatch")
        try:
            async with httpx.AsyncClient(
                timeout=self.settings.alive_meta_timeout,
                transport=transport,
                follow_redirects=False,
                trust_env=False,
            ) as client:
                request = client.build_request(
                    "POST",
                    url,
                    headers={
                        "Authorization": f"Bearer {self.settings.alive_meta_api_key}",
                        "X-Request-ID": correlation or str(uuid.uuid4()),
                    },
                    json=body,
                )
                # Use this checked request object for the send, without re-reading settings.
                # HTTPX canonicalizes URLs (e.g. default ports); both sides use that parser.
                if destination is not None and request.url != httpx.URL(destination.endpoint):
                    raise ProviderError("destination_mismatch")
                response = await client.send(request)
                if response.is_redirect:
                    raise ProviderError(
                        "redirect_refused", response.status_code, response_received=True
                    )
                if response.is_error:
                    status = response.status_code
                    body = response.text.lower()
                    if status == 401:
                        category = "authentication"
                    elif status == 403:
                        category = "access_denied"
                    elif status == 402 or "quota" in body:
                        category = "quota_exhausted"
                    elif status == 429:
                        category = "rate_limit"
                    elif status in (400, 404, 405, 422):
                        category = (
                            "unsupported_schema"
                            if "schema" in body or "response_format" in body
                            else "invalid_request"
                        )
                    elif status >= 500:
                        category = "server_error"
                    else:
                        category = "invalid_request"
                    raise ProviderError(category, status, response_received=True)
                value = response.json()
                if value["choices"][0].get("finish_reason") == "length":
                    raise ProviderError(
                        "output_truncated",
                        usage=value.get("usage", {}),
                        response_received=True,
                    )
                return Generation(
                    value["choices"][0]["message"]["content"],
                    value.get("usage", {}),
                    (time.monotonic() - started) * 1000,
                )
        except httpx.TimeoutException as exc:
            raise ProviderError("timeout") from exc
        except httpx.HTTPError as exc:
            raise ProviderError("transient_network") from exc
        except (KeyError, ValueError, TypeError) as exc:
            raise ProviderError("invalid_response", response_received=True) from exc

    async def generate(self, prompt):
        if not self.capabilities()["configured"]:
            raise RuntimeError("Meta gateway is not configured")
        return await self._request(
            {
                "model": self.model_id,
                "messages": [{"role": "user", "content": prompt}],
                "max_completion_tokens": self.settings.alive_meta_max_output,
            }
        )

    async def decide(self, prompt):
        import json

        return json.loads((await self.generate(prompt + "\nReturn a JSON object only.")).text)

    async def stream(self, prompt):
        # Explicit buffered fallback; capabilities never advertises native streaming.
        yield (await self.generate(prompt)).text


FATAL_PROVIDER_CATEGORIES = frozenset(
    {
        "authentication",
        "access_denied",
        "invalid_request",
        "unsupported_schema",
        "rate_limit",
        "quota_exhausted",
        "credentials_not_configured",
        "transient_network",
        "server_error",
        "timeout",
        "invalid_response",
        "ambiguous_settlement",
        "cancelled",
        "unknown",
        "redirect_refused",
        "destination_mismatch",
    }
)
CELL_PROVIDER_CATEGORIES = frozenset({"invalid_structured_output", "output_truncated"})


class ProviderError(RuntimeError):
    def __init__(self, category, status=None, usage=None, response_received=False):
        self.category, self.status = category, status
        self.usage = usage or {}
        self.response_received = response_received
        super().__init__(f"Meta provider: {category}" + (f" (HTTP {status})" if status else ""))

    @property
    def campaign_fatal(self):
        return self.category in FATAL_PROVIDER_CATEGORIES
