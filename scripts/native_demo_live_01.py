"""Demos A/B in a real docked Chrome panel, isolated local backend and database.

Uses the project's supported CDP/Playwright harness. No frontend/backend mock state,
no remote model transport, and no owner database. Screenshots emulate a 360px panel.
"""

import asyncio
import base64
import json
import platform
import shutil
import sqlite3
import subprocess
import uuid
from pathlib import Path

import httpx
from playwright.async_api import async_playwright

from scripts import native10 as chrome_harness
from scripts.demo_live_01 import environment, prepare_schema

ROOT = Path(__file__).resolve().parents[1]
EVIDENCE = ROOT / "docs/validation/demo-live-01/native"
BEHAVIOR = "Return the current UTC date and time, with tzinfo None."
DEPRECATION = "Deprecated since version 3.12: Use datetime.now() with UTC instead."


async def click(panel, label):
    await panel.evaluate(
        "(() => { const b=Array.from(document.querySelectorAll('#live-content button'))"
        f".find(b=>b.textContent==={json.dumps(label)}); "
        "if(!b) throw new Error('Missing action'); b.click(); })()"
    )


async def snapshot(panel, name):
    await panel.send(
        "Emulation.setDeviceMetricsOverride",
        {
            "width": 360,
            "height": 1100,
            "deviceScaleFactor": 1,
            "mobile": False,
        },
    )
    assert await panel.evaluate("document.documentElement.scrollWidth <= 360"), "Panel overflow"
    await panel.send("Page.enable")
    result = await panel.send("Page.captureScreenshot", {"captureBeyondViewport": True})
    (EVIDENCE / (name + ".png")).write_bytes(base64.b64decode(result["data"]))


async def select_behavior(page):
    # Set a genuine DOM selection spanning the paragraph's inline code nodes.
    # Nothing is written to extension storage or to application state here.
    await page.evaluate(
        """quote => {
      const dt=document.getElementById('datetime.datetime.utcnow');
      const p=dt.parentElement.querySelector('dd p');
      const walker=document.createTreeWalker(p,NodeFilter.SHOW_TEXT);
      let node, normalized='', points=[];
      while((node=walker.nextNode())) for(let i=0;i<node.nodeValue.length;i++) {
        let char=node.nodeValue[i]; if(/[\\t\\r\\n ]/.test(char)) char=' ';
        if(char===' ' && (!normalized || normalized.endsWith(' '))) continue;
        normalized+=char; points.push({node,offset:i});
      }
      const start=normalized.indexOf(quote);
      if(start<0) throw new Error('Exact source sentence missing');
      const first=points[start], last=points[start+quote.length-1], range=document.createRange();
      range.setStart(first.node,first.offset); range.setEnd(last.node,last.offset+1);
      const selection=window.getSelection();selection.removeAllRanges();selection.addRange(range);
    }""",
        BEHAVIOR,
    )


def audit_database(database):
    allowed = {"snapshot", "research_memory"}
    hits = []
    with sqlite3.connect(database) as db:
        for (name,) in db.execute("select name from sqlite_master where type='table'"):
            if name.startswith("sqlite_"):
                continue
            cursor = db.execute('select * from "' + name + '"')
            columns = [item[0] for item in cursor.description]
            for values in cursor:
                row = dict(zip(columns, values))
                if "tzinfo None" in json.dumps(row, default=str):
                    hit = {"table": name, "kind": row.get("kind"), "status": row.get("status")}
                    hits.append(hit)
                    assert name == "web_experiences" and row.get("kind") in allowed, hit
                    if row.get("kind") == "research_memory":
                        assert row.get("status") == "withdrawn"
        assert (
            db.execute("select count(*) from web_experiences where kind='note'").fetchone()[0] == 0
        )
    return hits


async def main():
    EVIDENCE.mkdir(parents=True, exist_ok=True)
    work = ROOT / ".alive" / ("demo-live-native-" + uuid.uuid4().hex)
    port = chrome_harness.free_port()
    backend = f"http://127.0.0.1:{port}"
    env, token = environment(work, port)
    await prepare_schema(env["DATABASE_URL"])
    urls = [
        backend + "/demo-live-01/" + name
        for name in ("python-3.11.html", "python-3.12.html", "synthetic-no-change.html")
    ]
    extension = work / "extension"
    shutil.copytree(ROOT / "extension", extension)
    (extension / "config.js").write_text(
        "export const DEFAULT_BACKEND = " + json.dumps(backend) + ";\n"
        "export const DEFAULT_BACKENDS = [" + json.dumps(backend) + "];\n"
        "export const AUTHORISED_PAGES = " + json.dumps(urls) + ";\n"
        "export function isLocalDemo() { return false; }\n",
        encoding="utf-8",
    )
    copied_manifest = json.loads((extension / "manifest.json").read_text(encoding="utf-8"))
    shipped_permissions = copied_manifest["permissions"]
    copied_manifest["host_permissions"] = [backend + "/*"]
    (extension / "manifest.json").write_text(json.dumps(copied_manifest), encoding="utf-8")
    chrome_harness.TOKEN = token
    process, log = chrome_harness.start_backend(work, env, port)
    report = {
        "source_commit": subprocess.check_output(
            ["git", "rev-parse", "HEAD"], cwd=ROOT, text=True
        ).strip(),
        "source_status_before_run": subprocess.check_output(
            ["git", "status", "--porcelain"], cwd=ROOT, text=True
        ).strip(),
        "platform": platform.platform(),
        "shipped_permissions": shipped_permissions,
        "harness_host_permissions": copied_manifest["host_permissions"],
        "external_model_calls": 0,
        "paid_inference_spend_usd": 0,
        "steps": [],
    }
    try:
        await chrome_harness.wait_backend(backend)
        async with async_playwright() as playwright:
            context = await playwright.chromium.launch_persistent_context(
                str(work / "chrome-profile"),
                channel="chrome",
                headless=False,
                ignore_default_args=["--disable-extensions"],
                args=["--enable-unsafe-extension-debugging", "--window-size=1440,1100"],
            )
            try:
                cdp = await context.browser.new_browser_cdp_session()
                report["chrome"] = await cdp.send("Browser.getVersion")
                extension_id = (
                    await cdp.send("Extensions.loadUnpacked", {"path": str(extension.resolve())})
                )["id"]
                page = await context.new_page()
                await page.goto(urls[0])
                panel, report["panel"] = await chrome_harness.open_panel(
                    context, cdp, extension_id, page, require_docked=True
                )
                await chrome_harness.connect_panel(panel, backend)

                async def api(path):
                    async with httpx.AsyncClient() as client:
                        response = await client.get(
                            backend + "/api/v1/browser-experience" + path,
                            headers={"Authorization": "Bearer " + token},
                        )
                        response.raise_for_status()
                        return response.json()

                async def investigation(label):
                    await panel.evaluate(
                        "document.querySelector('#goal').value=" + json.dumps(label)
                    )
                    await panel.click("#save-goal")
                    await panel.wait(
                        "document.querySelector('#status').textContent.includes('Goal saved')"
                    )
                    return await panel.evaluate("(await chrome.storage.local.get('goalId')).goalId")

                async def authorise(url):
                    if page.url != url:
                        await page.goto(url)
                    await page.bring_to_front()
                    await panel.click("#live-authorise")
                    await panel.wait(
                        "(await chrome.storage.session.get('latest')).latest?.payload.url === "
                        + json.dumps(url)
                    )
                    await panel.wait(
                        "document.querySelector('#live-companion')"
                        ".getAttribute('aria-busy') !== 'true'"
                    )

                async def remember():
                    await select_behavior(page)
                    await panel.click("#live-remember")
                    await panel.wait(
                        "document.querySelector('#live-content')"
                        ".textContent.includes('Confirm passage')"
                    )
                    assert (
                        await panel.evaluate(
                            "document.querySelector('#live-content blockquote').textContent"
                        )
                        == BEHAVIOR
                    )
                    await click(panel, "Confirm passage")
                    await panel.wait(
                        "document.querySelector('#live-companion')"
                        ".getAttribute('aria-busy') !== 'true' && "
                        "Array.from(document.querySelectorAll('#live-content button'))"
                        ".some(button => button.textContent === 'Withdraw saved source')"
                    )

                async def check():
                    await panel.click("#live-review")
                    await panel.wait(
                        "document.querySelector('#live-content')"
                        ".textContent.includes('Check against new evidence')"
                    )
                    await click(panel, "Check against new evidence")
                    await panel.wait(
                        "document.querySelector('#live-state')"
                        ".textContent.includes('awaiting authorisation')"
                    )
                    assert await panel.evaluate(
                        "document.querySelector('#live-content')"
                        ".textContent.includes('claim_comparison')"
                    )
                    await click(panel, "Authorise exact comparison")

                goal_a = await investigation("Demo A: datetime.utcnow standing")
                await authorise(urls[0])
                await remember()
                await snapshot(panel, "01-anchored-source")
                await authorise(urls[1])
                await check()
                await panel.wait(
                    "document.querySelector('#live-state')"
                    ".textContent.includes('New evidence worth reviewing')"
                )
                assert await panel.evaluate(
                    "document.querySelector('#live-content').textContent.includes("
                    + json.dumps(DEPRECATION)
                    + ")"
                )
                await snapshot(panel, "02-meaningful-change")
                await click(panel, "Dismiss interpretation")
                await panel.wait(
                    "document.querySelector('#live-state')"
                    ".textContent.includes('Interpretation dismissed')"
                )
                assert len((await api("/research/memories?goal_id=" + goal_a))["memories"]) == 1
                await panel.click("#live-refresh")
                await panel.wait(
                    "!document.querySelector('[data-finding-id]') && "
                    "document.querySelector('#live-content').textContent.includes('Check against new evidence')"
                )
                await click(panel, "Check against new evidence")
                await panel.wait(
                    "document.querySelector('#live-state')"
                    ".textContent.includes('awaiting authorisation')"
                )
                await click(panel, "Authorise exact comparison")
                await panel.wait("!!document.querySelector('[data-finding-id]')")
                assert (
                    len((await api("/research/relationships?goal_id=" + goal_a))["analyses"]) == 1
                )
                report["dismissal_kept_source"] = True
                report["candidate_reuse_confirmed"] = True
                await click(panel, "Keep for review")
                await panel.wait(
                    "document.querySelector('#live-state').textContent.includes('Kept for review')"
                )
                ledger = await api("/research/relationships?goal_id=" + goal_a)
                assert len(ledger["connections"]) == 1
                finding = ledger["connections"][0]
                assert finding["data"]["validation"]["subject_entry"] == "datetime.datetime.utcnow"
                assert finding["data"]["historical_quote_retained_in_current"] is True
                report["steps"].append(
                    {
                        "demo": "A",
                        "outcome": "candidate",
                        "analysis_mode": ledger["analyses"][0]["data"]["analysis_mode"],
                        "validation": finding["data"]["validation"],
                        "usage": ledger["analyses"][0]["data"]["usage"],
                    }
                )
                await click(panel, "Withdraw saved source")
                await click(panel, "Confirm withdrawal")
                await panel.wait(
                    "document.querySelector('#live-state').textContent.includes('Evidence retired')"
                )
                assert not await panel.evaluate(
                    "document.querySelector('#live-content').textContent.includes("
                    + json.dumps(BEHAVIOR)
                    + ")"
                )
                report["withdrawal_scan"] = audit_database(work / "demo.db")
                assert (await api("/research/relationships?goal_id=" + goal_a))["connections"] == []
                await snapshot(panel, "03-evidence-retired")
                chrome_harness.stop_backend(process, log)
                process, log = chrome_harness.start_backend(work, env, port)
                await chrome_harness.wait_backend(backend)
                await panel.send("Page.reload")
                await panel.wait(
                    "document.querySelector('#live-state')"
                    " && !document.querySelector('#connect').disabled"
                )
                await panel.click("#live-refresh")
                await panel.wait(
                    "document.querySelector('#live-state')"
                    ".textContent.includes('Nothing significant')"
                )
                assert (await api("/research/relationships?goal_id=" + goal_a))["connections"] == []
                assert not await panel.evaluate(
                    "document.querySelector('#live-content').textContent.includes("
                    + json.dumps(BEHAVIOR)
                    + ")"
                )
                await snapshot(panel, "04-retired-after-restart")
                report["restart_confirmed"] = True

                goal_b = await investigation("Demo B: UTC standing abstention")
                await authorise(urls[0])
                await remember()
                await authorise(urls[2])
                await check()
                await panel.wait(
                    "document.querySelector('#live-state')"
                    ".textContent.includes('No validated change detected')"
                )
                ledger_b = await api("/research/relationships?goal_id=" + goal_b)
                assert ledger_b["connections"] == []
                assert ledger_b["analyses"][0]["status"] == "validated"
                assert (
                    ledger_b["analyses"][0]["data"]["validation"]["relationship"]
                    == "insufficient_evidence"
                )
                await snapshot(panel, "05-credible-abstention")
                report["steps"].append(
                    {
                        "demo": "B",
                        "outcome": "insufficient_evidence",
                        "analysis_status": ledger_b["analyses"][0]["status"],
                        "usage": ledger_b["analyses"][0]["data"]["usage"],
                    }
                )
                report["goal_isolation_confirmed"] = (
                    await api("/research/relationships?goal_id=" + goal_a)
                )["connections"] == []
                report["panel_width_px"] = await panel.evaluate("window.innerWidth")
                with sqlite3.connect(work / "demo.db") as database:
                    attempts = [
                        json.loads(row[0])
                        for row in database.execute(
                            "select data from web_experiences "
                            "where kind='research_relationship_analysis'"
                        )
                    ]
                    report["recorded_provider_ids"] = [row["provider"]["id"] for row in attempts]
                    assert report["recorded_provider_ids"] == [
                        "local_fixture_claim",
                        "local_fixture_claim",
                    ]
                    assert all(row["usage"]["total_tokens"] == 0 for row in attempts)
                    report["external_model_calls"] = sum(
                        row["provider"]["id"] == "meta" for row in attempts
                    )
                    report["recorded_attempts"] = len(attempts)
                    assert (
                        database.execute(
                            "select count(*) from web_experiences where kind='note'"
                        ).fetchone()[0]
                        == 0
                    )
                report["status"] = "PASS"
            finally:
                await context.close()
    except BaseException as exc:
        report["status"] = "FAIL"
        report["error"] = type(exc).__name__ + ": " + str(exc)
        raise
    finally:
        chrome_harness.stop_backend(process, log)
        (EVIDENCE / "result.json").write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    asyncio.run(main())
