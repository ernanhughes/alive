"""Offline checks of the supported provider's actual destination and redirect policy."""

import asyncio

import httpx
import pytest

from alive.providers import MetaProvider, ProviderError, meta_endpoint_host, meta_endpoint_url


@pytest.mark.parametrize("status", [301, 302, 303, 307, 308])
def test_redirect_never_discloses_source_to_a_second_destination(settings, status):
    settings.alive_meta_api_key = "scripted-key"
    settings.alive_meta_url = "https://approved.example/v2/completions"
    seen = []

    def respond(request):
        seen.append(request)
        return httpx.Response(status, headers={"location": "https://unapproved.example/collect"})

    async def run():
        with pytest.raises(ProviderError, match="redirect_refused") as caught:
            await MetaProvider(settings).structured(
                "Analyze untrusted source",
                {"source": "SOURCE_CANARY"},
                {"type": "object"},
                transport=httpx.MockTransport(respond),
            )
        assert caught.value.response_received is True
        assert caught.value.campaign_fatal is True

    asyncio.run(run())
    assert len(seen) == 1
    assert str(seen[0].url) == meta_endpoint_url(settings)
    assert meta_endpoint_host(settings) == "approved.example"
    assert b"SOURCE_CANARY" in seen[0].content
