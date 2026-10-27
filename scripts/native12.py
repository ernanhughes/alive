"""ALIVE-12 native Chrome synthetic qualification for cross-page research memory."""

import asyncio
import json
import shutil
import threading
import traceback
import uuid
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

from playwright.async_api import async_playwright

from scripts import native10 as harness

ROOT = Path(__file__).resolve().parents[1]
TOKEN = "native12-" + uuid.uuid4().hex
GOAL = "Understand persistent agent memory for research tasks"
A_TEXT = "Persistent agent memory retains reviewed research sources across sessions."
B_TEXT = "Persistent agent memory retrieval selects earlier research sources for a current goal."


class TwoPageHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        if self.path not in {"/research/a", "/research/b"}:
            self.send_error(404)
            return
        body = (
            "<!doctype html><meta charset='utf-8'><title>ALIVE-12 controlled research page</title>"
            "<style>body{font:22px/1.6 system-ui;margin:60px;background:#eef3e9}"
            "main{background:white;padding:30px}</style>"
            f"<h1>Controlled research source {self.path[-1].upper()}</h1>"
            "<main id='content'>Initial controlled research observation.</main>"
        ).encode()
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, *args):
        return


def prepare_extension(run_dir, backend, pages):
    target = run_dir / "extension"
    shutil.copytree(ROOT / "extension", target)
    (target / "config.js").write_text(
        "export const DEFAULT_BACKEND = " + json.dumps(backend) + ";\n"
        "export const DEFAULT_BACKENDS = " + json.dumps([backend]) + ";\n"
        "export const AUTHORISED_PAGES = " + json.dumps(pages) + ";\n"
        "export function isLocalDemo() { return false; }\n",
        encoding="utf-8",
    )
    manifest_path = target / "manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest["name"] = "ALIVE 12 Native Research Qualification"
    manifest["host_permissions"] = [backend + "/*"] + [
        page.rsplit("/", 1)[0] + "/*" for page in pages
    ]
    manifest_path.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    return target


async def start_page(panel, page_url, marker):
    prior = await panel.evaluate("(await chrome.storage.session.get('grantId')).grantId")
    await panel.evaluate(
        "(async () => { const tabs=await chrome.tabs.query({}); "
        "const tab=tabs.find(t=>t.url==="
        + json.dumps(page_url)
        + "); if (!tab) throw new Error('controlled tab not found'); "
        "await chrome.tabs.update(tab.id,{active:true}); })()"
    )
    await panel.click("#start")
    await panel.wait(
        "(await chrome.storage.session.get('grantId')).grantId && "
        "(await chrome.storage.session.get('grantId')).grantId !== " + json.dumps(prior)
    )
    await panel.wait(
        "document.querySelector('#preview').textContent.includes(" + json.dumps(marker) + ")"
    )


async def send_current(panel):
    await panel.click("#send")
    await panel.wait("(await chrome.storage.session.get('selected')).selected?.snapshot.id")
    value = json.loads(
        await panel.evaluate(
            "JSON.stringify((await chrome.storage.session.get('selected')).selected)"
        )
    )
    while isinstance(value, str):
        value = json.loads(value)
    return value


async def main():
    run_dir = ROOT / ".alive" / f"native12-{uuid.uuid4().hex[:12]}"
    run_dir.mkdir(parents=True)
    page_server = ThreadingHTTPServer(("127.0.0.1", 0), TwoPageHandler)
    page_port = page_server.server_address[1]
    pages = [f"http://127.0.0.1:{page_port}/research/a", f"http://127.0.0.1:{page_port}/research/b"]
    stub = ThreadingHTTPServer(("127.0.0.1", 0), harness.StubHandler)
    stub.calls = []
    stub_port = stub.server_address[1]
    for server in (page_server, stub):
        threading.Thread(target=server.serve_forever, daemon=True).start()
    backend_port = harness.free_port()
    backend = f"http://127.0.0.1:{backend_port}"
    env = harness.backend_env(run_dir, backend, stub_port, pages[0])
    env["ALIVE_NATIVE_TEST_PAGES"] = ",".join(pages)
    backend_process = backend_log = None
    context = None
    evidence = {
        "provenance": {
            "kind": "native Chrome extension with isolated current-branch backend",
            "chrome_native": True,
            "provider": "local synthetic HTTP stub",
            "paid_calls": 0,
            "meta_inference": False,
            "source_commit": harness.subprocess.check_output(
                ["git", "rev-parse", "HEAD"], cwd=ROOT, text=True
            ).strip(),
        },
        "environment": {"page_a": pages[0], "page_b": pages[1], "backend": backend},
        "steps": [],
    }
    try:
        harness.run_migrations(env)
        backend_process, backend_log = harness.start_backend(run_dir, env, backend_port)
        await harness.wait_backend(backend)
        extension = prepare_extension(run_dir, backend, pages)
        async with async_playwright() as playwright:
            context = await playwright.chromium.launch_persistent_context(
                str(run_dir / "chrome-profile"),
                channel="chrome",
                headless=False,
                ignore_default_args=["--disable-extensions"],
                args=["--enable-unsafe-extension-debugging", "--window-size=1440,1100"],
            )
            cdp = await context.browser.new_browser_cdp_session()
            extension_id = (
                await cdp.send("Extensions.loadUnpacked", {"path": str(extension.resolve())})
            )["id"]
            page_a = await context.new_page()
            await page_a.goto(pages[0], wait_until="domcontentloaded")
            await page_a.evaluate(
                "(text) => { document.querySelector('#content').textContent = text; }", A_TEXT
            )
            await page_a.bring_to_front()
            panel, panel_meta = await harness.open_panel(
                context, cdp, extension_id, page_a, require_docked=True
            )
            await harness.connect_panel(panel, backend)
            await panel.evaluate("document.querySelector('#goal').value=" + json.dumps(GOAL))
            await panel.click("#save-goal")
            await panel.wait("document.querySelector('#status').textContent.includes('Goal saved')")
            await start_page(panel, pages[0], "Persistent agent memory retains")
            selected = await send_current(panel)
            assert selected["snapshot"]["data"]["url"] == pages[0]
            await panel.click("#analyse")
            note = await harness.settle_note(panel, backend, selected)
            assert note["status"] == "validated"
            await panel.wait("!document.querySelector('#save-research').disabled")
            await panel.click("#save-research")
            await panel.wait(
                "document.querySelector('#research-status').textContent.includes('Saved')"
            )
            saved = await harness.api_json(backend, "GET", "/browser-experience/research/memories")
            assert saved[0] == 200 and saved[1]["memories"], saved
            memory_id = saved[1]["memories"][0]["id"]

            page_b = await context.new_page()
            await page_b.goto(pages[1], wait_until="domcontentloaded")
            await page_b.evaluate(
                "(text) => { document.querySelector('#content').textContent = text; }", B_TEXT
            )
            await page_b.bring_to_front()
            await start_page(panel, pages[1], "Persistent agent memory retrieval")
            current = await send_current(panel)
            assert current["snapshot"]["data"]["url"] == pages[1]
            await panel.click("#find-research")
            await panel.wait("document.querySelector('#research-results button') !== null")
            retrieved = (
                await harness.api_json(backend, "GET", "/browser-experience/research/memories")
            )[1]
            assert retrieved["memories"][0]["id"] == memory_id
            await panel.evaluate("document.querySelector('#research-results button').click()")
            await panel.wait(
                "document.querySelector('#connection').textContent.includes('candidate') || "
                "document.querySelector('#connection').textContent.includes('insufficient_evidence')"
            )
            connection_text = await panel.evaluate(
                "document.querySelector('#connection').textContent"
            )
            await panel.click("#connection-useful")
            await panel.wait(
                "document.querySelector('#connection').textContent.includes('feedback saved')"
            )
            evidence["steps"].append(
                {
                    "name": "cross-page",
                    "historical_url": pages[0],
                    "current_url": pages[1],
                    "memory_id": memory_id,
                    "connection": connection_text,
                    "provider_calls": len(stub.calls),
                }
            )
            await panel.screenshot(run_dir / "research-memory.png")
            evidence["environment"]["screenshot"] = "research-memory.png"

            harness.stop_backend(backend_process, backend_log)
            backend_process, backend_log = harness.start_backend(run_dir, env, backend_port)
            await harness.wait_backend(backend)
            reopened = (
                await harness.api_json(backend, "GET", "/browser-experience/research/memories")
            )[1]
            assert reopened["memories"][0]["id"] == memory_id
            assert reopened["memories"][0]["status"] == "active"
            await panel.click("#find-research")
            await panel.wait("document.querySelector('#research-results button') !== null")
            await panel.click("#withdraw-research")
            await panel.wait(
                "document.querySelector('#research-status').textContent.includes('withdrawn')"
            )
            after = (
                await harness.api_json(backend, "GET", "/browser-experience/research/memories")
            )[1]
            assert after["memories"] == []
            evidence["restart"] = {
                "memory_persisted": True,
                "withdrawn": True,
                "active_after_withdraw": 0,
                "provider_calls": len(stub.calls),
            }
            evidence["negative_checks"] = {
                "wrong_origin_grant": (
                    await harness.api(
                        backend,
                        "POST",
                        "/browser-experience/grants",
                        {
                            "goal_id": reopened["memories"][0]["data"]["goal_id"]
                            if reopened["memories"]
                            else None,
                            "url": pages[0] + "?not-allowed",
                            "tab_key": "native12-wrong",
                            "approved": True,
                        },
                    )
                ).status_code,
            }
            evidence["environment"].update(
                {
                    "chrome": context.browser.version,
                    "presentation": "native side panel target",
                    "panel_opened_as_ordinary_tab": False,
                }
            )
            evidence["provider"] = {"synthetic_calls": len(stub.calls), "paid": False}
            evidence["status"] = "NATIVE_SYNTHETIC_PASS"
            print("VERIFIED native research memory; synthetic calls", len(stub.calls))
    except Exception:
        evidence["status"] = "NATIVE_SYNTHETIC_FAIL"
        evidence["error"] = traceback.format_exc()
        raise
    finally:
        if context:
            try:
                await context.close()
            except Exception:
                pass
        harness.stop_backend(backend_process, backend_log)
        page_server.shutdown()
        stub.shutdown()
        (run_dir / "evidence.json").write_text(
            json.dumps(evidence, indent=2) + "\n", encoding="utf-8"
        )
        print("evidence:", run_dir / "evidence.json")


if __name__ == "__main__":
    asyncio.run(main())
