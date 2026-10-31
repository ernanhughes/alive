"""Offline checks of the supported provider's actual destination and redirect policy."""

import asyncio

import httpx
import pytest

from alive.model_contracts import ApprovedModelDestination
from alive.providers import (
    MetaProvider,
    ProviderError,
    meta_endpoint_host,
    meta_endpoint_url,
)


@pytest.mark.parametrize("status", [301, 302, 303, 307, 308])
def test_redirect_never_discloses_source_to_a_second_destination(settings, status):
    settings.alive_meta_api_key = "scripted-key"
    settings.alive_meta_url = "https://approved.example/v2/completions"
    seen = []

    def respond(request):
        seen.append(request)
        return httpx.Response(status, headers={"location": "https://unapproved.example/collect"})

    async def run():
        with pytest.raises(ProviderError) as caught:
            await MetaProvider(settings).structured(
                "Analyze untrusted source",
                {"source": "SOURCE_CANARY"},
                {"type": "object"},
                transport=httpx.MockTransport(respond),
            )
        assert len(seen) == 1, "redirects must never forward source to another destination"
        assert caught.value.category == "redirect_refused"
        assert caught.value.response_received is True
        assert caught.value.campaign_fatal is True

    asyncio.run(run())
    assert len(seen) == 1
    assert str(seen[0].url) == meta_endpoint_url(settings)
    assert meta_endpoint_host(settings) == "approved.example"
    assert b"SOURCE_CANARY" in seen[0].content


@pytest.mark.parametrize("tamper", ["pinned_endpoint", "built_request"])
def test_authority_binds_the_actual_http_request(settings, monkeypatch, tamper):
    settings.alive_meta_api_key = "synthetic-key"
    settings.alive_meta_url = "https://approved.example:8443/v2/completions"
    approved = ApprovedModelDestination("admission", "a" * 64, settings.alive_meta_url)
    seen = []

    def respond(request):
        seen.append(str(request.url))
        return httpx.Response(200, json={"choices": [{"message": {"content": "{}"}}]})

    async def request():
        return await MetaProvider(settings).structured(
            "Synthetic",
            {"source": "SOURCE_CANARY"},
            {},
            transport=httpx.MockTransport(respond),
            destination=approved,
        )

    assert asyncio.run(request()).text == "{}"
    assert seen == [approved.endpoint]
    seen.clear()
    if tamper == "pinned_endpoint":
        settings.alive_meta_url = "https://attacker.example/collect"
    else:
        original = httpx.AsyncClient.build_request

        def substituted(self, method, url, **kwargs):
            return original(self, method, "https://attacker.example/collect", **kwargs)

        monkeypatch.setattr(httpx.AsyncClient, "build_request", substituted)
    with pytest.raises(ProviderError, match="destination_mismatch"):
        asyncio.run(request())
    assert seen == [], "no source bytes may leave on an endpoint mismatch"
