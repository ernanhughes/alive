"""Native Chrome side-panel qualification on the two owner-authorised public pages.

Run first, inspect the local note, then feedback, restart backend, and run revisit.
Feedback is a qualification operator's explicit rating, not a measured user study.
All raw excerpts and browser credentials stay under ignored .alive/.
"""

import argparse
import asyncio
import base64
import json
from pathlib import Path

import httpx
from playwright.async_api import async_playwright

from alive.config import Settings, prepare_local

OUT = Path(".alive/browser05")
PYTHON = "https://docs.python.org/3/tutorial/"
MDN = "https://developer.mozilla.org/en-US/docs/Web/JavaScript/Guide"


class Panel:
    def __init__(self, cdp, session):
        self.cdp, self.session = cdp, session
        self.counter, self.pending = 0, {}
        cdp.on("Target.receivedMessageFromTarget", self.received)

    def received(self, event):
        if event["sessionId"] != self.session:
            return
        message = json.loads(event["message"])
        future = self.pending.get(message.get("id"))
        if future and not future.done():
            future.set_result(message)

    async def send(self, method, params=None):
        self.counter += 1
        future = asyncio.get_running_loop().create_future()
        self.pending[self.counter] = future
        await self.cdp.send(
            "Target.sendMessageToTarget",
            {
                "sessionId": self.session,
                "message": json.dumps(
                    {"id": self.counter, "method": method, "params": params or {}}
                ),
            },
        )
        result = await asyncio.wait_for(future, 15)
        if "error" in result:
            raise RuntimeError(result["error"])
        return result["result"]

    async def evaluate(self, expression):
        result = await self.send(
            "Runtime.evaluate",
            {
                "expression": expression,
                "returnByValue": True,
                "awaitPromise": True,
                "userGesture": True,
                "replMode": True,
            },
        )
        if "exceptionDetails" in result:
            raise RuntimeError(result["exceptionDetails"]["text"])
        return result["result"].get("value")

    async def click(self, selector):
        await self.evaluate(f"document.querySelector({json.dumps(selector)}).click()")

    async def wait(self, expression, seconds=15):
        for _ in range(seconds * 4):
            value = await self.evaluate(expression)
            if value:
                return value
            await asyncio.sleep(0.25)
        status = await self.evaluate("document.querySelector('#status').textContent")
        raise AssertionError("Panel did not reach expected state: " + expression + "; " + status)

    async def screenshot(self, name):
        # Collapse credentials and raw third-party excerpt; retain actual note/provenance UI.
        await self.evaluate(
            "document.querySelector('#connection').open=false; "
            "document.querySelector('#excerpt').open=false"
        )
        await self.send("Page.enable")
        result = await self.send("Page.captureScreenshot", {"captureBeyondViewport": True})
        (OUT / (name + ".png")).write_bytes(base64.b64decode(result["data"]))


async def main(mode):
    OUT.mkdir(parents=True, exist_ok=True)
    url = MDN if mode == "mdn" else PYTHON
    async with async_playwright() as p:
        context = await p.chromium.launch_persistent_context(
            str((OUT / "chrome-profile-v2").resolve()),
            channel="chrome",
            headless=False,
            ignore_default_args=["--disable-extensions"],
            args=[
                "--enable-unsafe-extension-debugging",
                "--window-position=40,40",
                "--window-size=1440,1100",
            ],
        )
        try:
            cdp = await context.browser.new_browser_cdp_session()
            extension = (
                await cdp.send(
                    "Extensions.loadUnpacked", {"path": str(Path("extension").resolve())}
                )
            )["id"]
            page = await context.new_page()
            await page.goto(url, wait_until="networkidle")
            targets = (await cdp.send("Target.getTargets", {"filter": [{"type": "tab"}]}))[
                "targetInfos"
            ]
            target = next(t for t in targets if t["url"] == url)
            await cdp.send(
                "Extensions.triggerAction", {"id": extension, "targetId": target["targetId"]}
            )
            await asyncio.sleep(0.8)
            targets = (await cdp.send("Target.getTargets", {"filter": [{}]}))["targetInfos"]
            target = next(
                t for t in targets if t["type"] == "page" and t["url"].endswith("/panel.html")
            )
            session = (
                await cdp.send(
                    "Target.attachToTarget", {"targetId": target["targetId"], "flatten": False}
                )
            )["sessionId"]
            panel = Panel(cdp, session)
            await panel.wait("!document.querySelector('#connect').disabled")
            token = prepare_local(Settings())
            await panel.evaluate(f"document.querySelector('#token').value={json.dumps(token)}")
            await panel.click("#connect")
            await panel.wait("document.querySelector('#status').textContent.includes('Connected')")
            if mode == "first":
                await panel.evaluate(
                    "document.querySelector('#goal').value='Help me plan a first study session "
                    "using this documentation; distinguish what the excerpt covers "
                    "from what it does not.'"
                )
                await panel.click("#save-goal")
                await panel.wait(
                    "document.querySelector('#status').textContent.includes('Goal saved')"
                )
            elif not await panel.evaluate("(await chrome.storage.local.get('goalId')).goalId"):
                original = json.loads((OUT / "first-note.json").read_text(encoding="utf-8"))
                await panel.evaluate(
                    "document.querySelector('#resume').value="
                    + json.dumps(original["data"]["goal_id"])
                )
                await panel.evaluate(
                    "document.querySelector('#resume').dispatchEvent(new Event('change'))"
                )
                await panel.wait(
                    "document.querySelector('#status').textContent.includes('Goal resumed')"
                )
            await panel.click("#start")
            await panel.wait("document.querySelector('#preview').textContent.includes('tab_id')")
            await panel.click("#send")
            await panel.wait(
                "document.querySelector('#decision').textContent.includes('without_feedback_action')"
            )
            selected = await panel.evaluate(
                "(await chrome.storage.session.get('selected')).selected"
            )
            if mode in {"first", "mdn"}:
                assert selected["decision"]["action"] == "analyse", selected["decision"]["action"]
                await panel.click("#analyse")
                await panel.wait(
                    "document.querySelector('#cost').textContent.includes('validated') || "
                    "document.querySelector('#cost').textContent.includes('failed')",
                    seconds=100,
                )
                note_id = await panel.evaluate(
                    "(await chrome.storage.session.get('noteId')).noteId"
                )
                async with httpx.AsyncClient(headers={"Authorization": "Bearer " + token}) as api:
                    response = await api.get(
                        "http://127.0.0.1:8000/api/v1/browser-experience/notes/" + note_id
                    )
                    response.raise_for_status()
                    note = response.json()
                (OUT / (mode + "-note.json")).write_text(
                    json.dumps(note, indent=2), encoding="utf-8"
                )
                assert note["status"] == "validated", note["data"].get("error")
            elif mode == "feedback":
                original = json.loads((OUT / "first-note.json").read_text(encoding="utf-8"))
                assert selected["decision"]["action"] == "analyse", (
                    "Memory alone must not count as feedback"
                )
                assert selected["decision"]["candidate_note"]["id"] == original["id"]
                assert not await panel.evaluate("document.querySelector('#useful').disabled")
                await panel.click("#useful")
                await panel.wait(
                    "document.querySelector('#status').textContent.includes('Feedback saved')"
                )
            else:
                original = json.loads((OUT / "first-note.json").read_text(encoding="utf-8"))
                assert selected["decision"]["action"] == "recall"
                assert selected["decision"]["note"]["id"] == original["id"]
                assert await panel.evaluate("document.querySelector('#analyse').disabled")
            await panel.screenshot(mode + "-native-panel")
            # Evidence is local; archive builder removes raw text and credential-bearing profile.
            report = {
                "mode": mode,
                "url": url,
                "native_target": target["type"],
                "selected": selected,
                "chrome": context.browser.version,
                "feedback_source": "qualification operator" if mode == "feedback" else None,
            }
            (OUT / (mode + ".json")).write_text(json.dumps(report, indent=2), encoding="utf-8")
            await panel.click("#stop")
            await panel.wait("document.querySelector('#status').textContent.includes('revoked')")
            assert await page.evaluate("!globalThis.__aliveObserver")
            # Navigating while observed must revoke the extension's grant, even same-page reload.
            await panel.click("#start")
            await panel.wait("document.querySelector('#preview').textContent.includes('tab_id')")
            await page.reload(wait_until="networkidle")
            assert not await panel.evaluate(
                "(await chrome.storage.session.get('observedTab')).observedTab"
            )
            await panel.evaluate("chrome.storage.local.remove('token')")
            print(
                f"VERIFIED {mode}: native Chrome panel, {selected['decision']['action']}, "
                "exact excerpt, stop/navigation revocation"
            )
        finally:
            await context.close()


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("mode", choices=["first", "feedback", "revisit", "mdn"])
    asyncio.run(main(parser.parse_args().mode))
