"""Real Chrome + unchanged PR54 unpacked extension + disposable Docker backend.

Uses existing repository CDP test helpers. Never uses the owner's Chrome profile.
"""
import asyncio
import hashlib
import json
import subprocess
import sys
from pathlib import Path

import httpx
from playwright.async_api import async_playwright
from scripts import native10 as harness
from scripts import native_demo_live_01 as ui

OUT = Path(__file__).resolve().parent
BACKEND = "http://127.0.0.1:8000"
PR54 = Path("C:/Projects/alive-audit-01-pr54")
TOKEN = "audit-only-local-token-00000000000000"
API = "/api/v1/browser-experience"


async def main():
    report = {"pr54_commit": "7bff18aab6db50e6b62a1c36529042d877af647f",
              "extension_modified": False, "external_model_calls": 0, "steps": []}
    ui.EVIDENCE = OUT / "receipts"
    harness.TOKEN = TOKEN
    profile = OUT.parents[3] / ".alive/audit-chrome-profile"
    async with httpx.AsyncClient(base_url=BACKEND, headers={"Authorization": "Bearer " + TOKEN}) as api:
        async def get(path):
            r = await api.get(API + path)
            r.raise_for_status()
            return r.json()
        async with async_playwright() as p:
            context = await p.chromium.launch_persistent_context(str(profile), channel="chrome",
                headless=False, ignore_default_args=["--disable-extensions"],
                args=["--enable-unsafe-extension-debugging", "--window-size=1440,1100"])
            try:
                cdp = await context.browser.new_browser_cdp_session()
                report["chrome"] = await cdp.send("Browser.getVersion")
                extension = PR54 / "extension"
                report["extension_files_sha256"] = {f.name: hashlib.sha256(f.read_bytes()).hexdigest()
                    for f in extension.iterdir() if f.is_file()}
                eid = (await cdp.send("Extensions.loadUnpacked", {"path": str(extension)}))["id"]
                page = await context.new_page()
                url = lambda name: BACKEND + "/demo-live-01/" + name + ".html"
                await page.goto(url("python-3.11"))
                panel, report["panel"] = await harness.open_panel(context, cdp, eid, page, require_docked=True)
                await harness.connect_panel(panel, BACKEND)
                async def goal(label):
                    await panel.evaluate("document.querySelector('#goal').value=" + json.dumps(label))
                    await panel.click("#save-goal")
                    await panel.wait("document.querySelector('#status').textContent.includes('Goal saved')")
                    return await panel.evaluate("(await chrome.storage.local.get('goalId')).goalId")
                async def authorise(name):
                    await page.goto(url(name))
                    await page.bring_to_front()
                    await panel.click("#live-authorise")
                    await panel.wait("(await chrome.storage.session.get('latest')).latest?.payload.url === " + json.dumps(url(name)))
                    await panel.wait("document.querySelector('#live-companion').getAttribute('aria-busy') !== 'true'")
                async def remember():
                    await ui.select_behavior(page)
                    await panel.click("#live-remember")
                    await panel.wait("document.querySelector('#live-content').textContent.includes('Confirm passage')")
                    await ui.click(panel, "Confirm passage")
                    await panel.wait("Array.from(document.querySelectorAll('#live-content button')).some(b=>b.textContent==='Withdraw saved source')")
                async def compare():
                    await panel.wait("document.querySelector('#live-content').textContent.includes('Check against new evidence')")
                    await ui.click(panel, "Check against new evidence")
                    await panel.wait("document.querySelector('#live-state').textContent.includes('awaiting authorisation')")
                    await ui.click(panel, "Authorise exact comparison")
                ga = await goal("Audit A: datetime.utcnow standing")
                await authorise("python-3.11")
                await remember()
                await authorise("python-3.12")
                await compare()
                await panel.wait("document.querySelector('#live-state').textContent.includes('New evidence worth reviewing')")
                ledger = await get("/research/relationships?goal_id=" + ga)
                assert len(ledger["connections"]) == 1
                assert ledger["connections"][0]["data"]["historical_quote_retained_in_current"]
                assert ledger["analyses"][0]["data"]["provider"]["id"] == "local_fixture_claim"
                report["steps"].append("real browser capture, anchor, authorized fixture comparison passed")
                await ui.snapshot(panel, "chrome-change")
                await ui.click(panel, "Withdraw saved source")
                await ui.click(panel, "Confirm withdrawal")
                await panel.wait("document.querySelector('#live-state').textContent.includes('Evidence retired')")
                assert (await get("/research/relationships?goal_id=" + ga))["connections"] == []
                report["steps"].append("withdrawal removed finding in real panel and PostgreSQL-backed API")
                subprocess.run(["docker", "compose", "-p", "alive-audit01-pr54", "restart", "app"], cwd=PR54, check=True)
                for _ in range(60):
                    try:
                        if (await api.get("/api/v1/health")).json().get("status") == "ok":
                            break
                    except httpx.HTTPError:
                        pass
                    await asyncio.sleep(.5)
                await panel.send("Page.reload")
                await panel.wait("!!document.querySelector('#live-state') && !document.querySelector('#connect').disabled")
                await panel.click("#live-refresh")
                await panel.wait("document.querySelector('#live-state').textContent.includes('Nothing significant')")
                assert (await get("/research/relationships?goal_id=" + ga))["connections"] == []
                report["steps"].append("container restart: withdrawn finding remained absent")
                gb = await goal("Audit B: UTC standing abstention")
                await authorise("python-3.11")
                await remember()
                await authorise("synthetic-no-change")
                await compare()
                await panel.wait("document.querySelector('#live-state').textContent.includes('No validated change detected')")
                ledger = await get("/research/relationships?goal_id=" + gb)
                assert ledger["connections"] == []
                assert ledger["analyses"][0]["data"]["validation"]["relationship"] == "insufficient_evidence"
                report["steps"].append("real panel: no-change comparison abstained")
                await ui.snapshot(panel, "chrome-abstention")
                report["status"] = "PASS"
            except BaseException as e:
                report["status"] = "FAIL"
                report["error"] = type(e).__name__ + ": " + str(e)
                raise
            finally:
                (OUT / "receipts/chrome-docker.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
                await context.close()
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    asyncio.run(main())
