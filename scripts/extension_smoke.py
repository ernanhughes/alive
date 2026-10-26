"""Real MV3 service worker, panel, observer, persistence and revocation in isolated Chrome."""

import asyncio
import uuid
from pathlib import Path

import httpx
from playwright.async_api import async_playwright, expect

from alive.config import Settings, prepare_local


async def main():
    token = prepare_local(Settings())
    async with async_playwright() as p:
        context = await p.chromium.launch_persistent_context(
            str(Path(".alive") / f"extension-test-{uuid.uuid4().hex}"),
            channel="chrome",
            headless=True,
            ignore_default_args=["--disable-extensions"],
            args=["--enable-unsafe-extension-debugging"],
        )
        browser = context.browser
        try:
            cdp = await browser.new_browser_cdp_session()
            extension_id = (
                await cdp.send(
                    "Extensions.loadUnpacked",
                    {
                        "path": str(Path("extension").resolve()),
                        "enableInIncognito": True,
                    },
                )
            )["id"]
            demo = await context.new_page()
            await demo.goto("http://127.0.0.1:8000/demo")
            await demo.evaluate("""() => {
                const privateContent=document.createElement('div');
                privateContent.dataset.alivePrivate='';
                privateContent.textContent='PRIVATE_FIXTURE_OMIT';
                const hidden=document.createElement('div');
                hidden.style.display='none'; hidden.textContent='HIDDEN_FIXTURE_OMIT';
                document.body.append(privateContent,hidden);
            }""")
            panel = await context.new_page()
            await panel.goto(f"chrome-extension://{extension_id}/panel.html")
            await panel.locator("#token").fill(token)
            await panel.locator("#connect").click()
            await expect(panel.locator("#status")).to_contain_text("Connected")
            # The demo origin is already explicitly granted in the extension manifest.
            await panel.evaluate(
                "async () => { const tabs=await chrome.tabs.query({}); "
                "const tab=tabs.find(t=>t.url?.endsWith('/demo')); "
                "await chrome.tabs.update(tab.id,{active:true}); }"
            )
            result = await panel.evaluate("chrome.runtime.sendMessage({type:'start'})")
            assert not result.get("error"), result
            await expect(panel.locator("#preview")).to_contain_text("habitat")
            await demo.locator("#message").fill("Extension verification: a violet beacon appeared")
            await demo.locator("#change").click()
            await expect(panel.locator("#preview")).to_contain_text("violet beacon")
            latest = await panel.evaluate("chrome.storage.session.get('latest')")
            assert "PRIVATE_FIXTURE_OMIT" not in latest["latest"]["payload"]["text"]
            assert "HIDDEN_FIXTURE_OMIT" not in latest["latest"]["payload"]["text"]
            event_id = latest["latest"]["event_id"]
            await panel.locator("#send").click()
            await expect(panel.locator("#status")).to_contain_text("persisted")
            async with httpx.AsyncClient(headers={"Authorization": f"Bearer {token}"}) as client:
                events = (
                    await client.get("http://127.0.0.1:8000/api/v1/events", params={"limit": 500})
                ).json()
                assert any(e["event_id"] == event_id for e in events)
            await panel.locator("#stop").click()
            await expect(panel.locator("#status")).to_contain_text("revoked")
            assert await demo.evaluate("!globalThis.__aliveObserver")
            assert not (await panel.evaluate("chrome.storage.session.get('latest')")).get("latest")
            print(
                "VERIFIED LIVE: stable Chrome MV3 load, panel connection, DOM observation, "
                "PostgreSQL event persistence, stop and revocation"
            )
        finally:
            await context.close()


if __name__ == "__main__":
    asyncio.run(main())
