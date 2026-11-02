import hashlib
from datetime import datetime

import pytest

from alive.browser import Browsers


class Settings:
    alive_browser_origins = ["http://127.0.0.1:8000"]


class Kernel:
    settings = Settings()

    def __init__(self):
        self.observations = []

    async def ingest(self, observation):
        self.observations.append(observation)


class Page:
    def __init__(self, url, text="A green light appeared in the habitat."):
        self.url = url
        self.text = text

    async def title(self):
        return "First Contact habitat"

    async def evaluate(self, script, selector):
        return self.text


class RedirectingPage(Page):
    async def evaluate(self, script, selector):
        self.url = "https://example.com/unrelated"
        return self.text


def test_relative_navigation_resolves_against_the_first_allowed_origin():
    browsers = Browsers(Kernel())
    assert browsers.resolve("/world/lab-1") == "http://127.0.0.1:8000/world/lab-1"
    assert browsers.resolve("http://127.0.0.1:8000/demo") == "http://127.0.0.1:8000/demo"


async def test_managed_chrome_observation_carries_source_and_integrity_metadata():
    kernel = Kernel()
    browsers = Browsers(kernel)
    text = "A green light appeared in the habitat."
    browsers.pages["session-1"] = (
        None,
        Page("http://127.0.0.1:8000/demo?secret=value#fragment", text),
    )

    payload = await browsers.observe("session-1", "browser.page_opened")

    assert payload["url"] == "http://127.0.0.1:8000/demo"
    assert payload["source_kind"] == "managed_chrome_dom"
    assert payload["trust_level"] == "observed_page_text_not_verified_fact"
    assert payload["permission_scope"] == "ALIVE_BROWSER_ORIGINS exact-origin allowlist"
    assert payload["permission_origin"] == "http://127.0.0.1:8000"
    assert payload["permission_read_only"] is True
    assert payload["selector"] == "body"
    assert payload["text_sha256"] == hashlib.sha256(text.encode()).hexdigest()
    assert payload["text_chars"] == len(text)
    assert datetime.fromisoformat(payload["observed_at"]).tzinfo is not None
    assert len(kernel.observations) == 1
    event = kernel.observations[0]
    assert event.source == "user"
    assert str(event.event_id) == payload["observation_id"]
    assert event.payload["observation_id"] == payload["observation_id"]


async def test_managed_chrome_observation_rejects_page_outside_allowlist():
    kernel = Kernel()
    browsers = Browsers(kernel)
    browsers.pages["session-1"] = (None, Page("https://example.com/unrelated"))

    with pytest.raises(PermissionError, match="not authorised"):
        await browsers.observe("session-1", "browser.page_opened")

    assert kernel.observations == []


async def test_managed_chrome_observation_rejects_origin_change_during_read():
    kernel = Kernel()
    browsers = Browsers(kernel)
    browsers.pages["session-1"] = (
        None,
        RedirectingPage("http://127.0.0.1:8000/demo"),
    )

    with pytest.raises(PermissionError, match="left the authorised origin"):
        await browsers.observe("session-1", "browser.page_opened")

    assert kernel.observations == []
