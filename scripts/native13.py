"""ALIVE-13 native Chrome synthetic qualification for reliable research retrieval."""

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
TOKEN = "native13-" + uuid.uuid4().hex
GOAL = "Understand persistent agent memory for research tasks"
TARGET_TEXT = "Persistent agent memory retains reviewed research sources across sessions."
DISTRACTOR_ONE = "Persistent agent memory ordinary note about scheduling and timers."
DISTRACTOR_TWO = "Persistent agent memory ordinary note about rendering and layout."
CURRENT_TEXT = (
    "Persistent agent memory retrieval selects earlier research sources for a current goal."
)
TARGET_MARKER = "retains reviewed research sources"
CURRENT_MARKER = "retrieval selects earlier research sources"


class MultiPageHandler(BaseHTTPRequestHandler):
    PAGES = {
        "/research/a": "A",
        "/research/distractor-1": "D1",
        "/research/distractor-2": "D2",
        "/research/current": "B",
    }

    def do_GET(self):
        if self.path not in self.PAGES:
            self.send_error(404)
            return
        body = (
            "<!doctype html><meta charset='utf-8'>"
            "<title>ALIVE-13 controlled research page</title>"
            "<style>body{font:22px/1.6 system-ui;margin:60px;background:#eef3e9}"
            "main{background:white;padding:30px}</style>"
            f"<h1>Controlled research source {self.PAGES[self.path]}</h1>"
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
    manifest["name"] = "ALIVE 13 Native Research Qualification"
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


async def save_research(panel, backend, page_url, marker):
    await start_page(panel, page_url, marker)
    selected = await send_current(panel)
    assert selected["snapshot"]["data"]["url"] == page_url
    await panel.click("#analyse")
    note = await harness.settle_note(panel, backend, selected)
    assert note["status"] == "validated"
    await panel.wait("!document.querySelector('#save-research').disabled")
    await panel.click("#save-research")
    await panel.wait("document.querySelector('#research-status').textContent.includes('Saved')")
    return selected


async def main():
    run_dir = ROOT / ".alive" / f"native13-{uuid.uuid4().hex[:12]}"
    run_dir.mkdir(parents=True)
    page_server = ThreadingHTTPServer(("127.0.0.1", 0), MultiPageHandler)
    page_port = page_server.server_address[1]
    base = f"http://127.0.0.1:{page_port}"
    pages = [
        f"{base}/research/a",
        f"{base}/research/distractor-1",
        f"{base}/research/distractor-2",
        f"{base}/research/current",
    ]
    target_page, distractor_one, distractor_two, current_page = pages
    stub = ThreadingHTTPServer(("127.0.0.1", 0), harness.StubHandler)
    stub.calls = []
    stub_port = stub.server_address[1]
    for server in (page_server, stub):
        threading.Thread(target=server.serve_forever, daemon=True).start()
    backend_port = harness.free_port()
    backend = f"http://127.0.0.1:{backend_port}"
    env = harness.backend_env(run_dir, backend, stub_port, target_page)
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
        "environment": {
            "target_page": target_page,
            "distractor_pages": [distractor_one, distractor_two],
            "current_page": current_page,
            "backend": backend,
        },
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
            target_tab = await context.new_page()
            await target_tab.goto(target_page, wait_until="domcontentloaded")
            await target_tab.evaluate(
                "(text) => { document.querySelector('#content').textContent = text; }",
                TARGET_TEXT,
            )
            await target_tab.bring_to_front()
            panel, panel_meta = await harness.open_panel(
                context, cdp, extension_id, target_tab, require_docked=True
            )
            await harness.connect_panel(panel, backend)
            await panel.evaluate("document.querySelector('#goal').value=" + json.dumps(GOAL))
            await panel.click("#save-goal")
            await panel.wait("document.querySelector('#status').textContent.includes('Goal saved')")

            await save_research(panel, backend, target_page, TARGET_MARKER)
            for page_url, text, marker in (
                (distractor_one, DISTRACTOR_ONE, "scheduling and timers"),
                (distractor_two, DISTRACTOR_TWO, "rendering and layout"),
            ):
                tab = await context.new_page()
                await tab.goto(page_url, wait_until="domcontentloaded")
                await tab.evaluate(
                    "(text) => { document.querySelector('#content').textContent = text; }",
                    text,
                )
                await tab.bring_to_front()
                await save_research(panel, backend, page_url, marker)

            memories = (
                await harness.api_json(backend, "GET", "/browser-experience/research/memories")
            )[1]["memories"]
            assert len(memories) == 3, memories
            by_url = {row["data"]["url"]: row for row in memories}
            target_memory = by_url[target_page]["id"]
            distractor_ids = {by_url[distractor_one]["id"], by_url[distractor_two]["id"]}
            assert target_memory not in distractor_ids

            current_tab = await context.new_page()
            await current_tab.goto(current_page, wait_until="domcontentloaded")
            await current_tab.evaluate(
                "(text) => { document.querySelector('#content').textContent = text; }",
                CURRENT_TEXT,
            )
            await current_tab.bring_to_front()
            await start_page(panel, current_page, CURRENT_MARKER)
            current = await send_current(panel)
            assert current["snapshot"]["data"]["url"] == current_page
            retrieved = (
                await harness.api_json(
                    backend,
                    "POST",
                    "/browser-experience/research/retrieve",
                    {"snapshot_id": current["snapshot"]["id"], "top_k": 3, "mode": "hybrid"},
                )
            )[1]
            assert retrieved["results"][0]["memory_id"] == target_memory, retrieved
            assert retrieved["results"][0]["source_url"] == target_page
            evidence["retrieval"] = {
                "target_memory": target_memory,
                "rank_1_memory": retrieved["results"][0]["memory_id"],
                "rank_1_source_url": retrieved["results"][0]["source_url"],
                "competing_research_memories": len(memories),
                "result_count": len(retrieved["results"]),
                "ranking_version": retrieved["results"][0]["ranking_version"],
            }

            await panel.click("#find-research")
            await panel.wait("document.querySelector('#research-results button') !== null")
            await panel.evaluate(
                "(() => { const block=[...document.querySelectorAll('#research-results > div')]"
                ".find(b=>b.querySelector('blockquote')?.textContent.includes("
                + json.dumps(TARGET_MARKER)
                + ")); if(!block) throw new Error('target research block missing'); "
                "[...block.querySelectorAll('button')]"
                ".find(b=>b.textContent==='Explain connection to this page').click(); })()"
            )
            await panel.wait(
                "document.querySelector('#connection').textContent.includes("
                + json.dumps("topic_overlap_candidate")
                + ") || document.querySelector('#connection').textContent.includes("
                + json.dumps("insufficient_evidence")
                + ")"
            )
            connection_text = await panel.evaluate(
                "document.querySelector('#connection').textContent"
            )
            assert "topic_overlap_candidate" in connection_text, connection_text
            assert "Historical source quote" in connection_text, connection_text
            assert "Current source quote" in connection_text, connection_text
            assert "does not establish agreement" in connection_text, connection_text
            assert "same_concept" not in connection_text
            assert "complementary" not in connection_text
            await panel.click("#connection-useful")
            await panel.wait(
                "document.querySelector('#connection').textContent.includes('feedback saved')"
            )
            evidence["connection"] = {
                "displayed": connection_text,
                "truthful_label": True,
                "exact_source_spans": True,
                "owner_feedback_persisted": True,
            }
            await panel.screenshot(run_dir / "research-memory.png")
            evidence["environment"]["screenshot"] = "research-memory.png"

            grant_id = await panel.evaluate("(await chrome.storage.session.get('grantId')).grantId")
            await harness.api(backend, "POST", f"/browser-experience/grants/{grant_id}/revoke", {})
            revoked_connection = await harness.api(
                backend,
                "POST",
                "/browser-experience/research/connections",
                {"snapshot_id": current["snapshot"]["id"], "memory_id": target_memory},
            )
            assert revoked_connection.status_code == 403, revoked_connection.text
            evidence["negative_checks"] = {
                "revoked_grant_connection": revoked_connection.status_code,
                "retrieval_remains_local_after_revoke": True,
            }

            harness.stop_backend(backend_process, backend_log)
            backend_process, backend_log = harness.start_backend(run_dir, env, backend_port)
            await harness.wait_backend(backend)
            reopened = (
                await harness.api_json(backend, "GET", "/browser-experience/research/memories")
            )[1]["memories"]
            assert {row["id"] for row in reopened} == {target_memory} | distractor_ids
            await panel.click("#find-research")
            await panel.wait("document.querySelector('#research-results button') !== null")
            await panel.evaluate(
                "(() => { const block=[...document.querySelectorAll('#research-results > div')]"
                ".find(b=>b.querySelector('blockquote')?.textContent.includes("
                + json.dumps(TARGET_MARKER)
                + ")); if(!block) throw new Error('target research block missing'); "
                "[...block.querySelectorAll('button')]"
                ".find(b=>b.textContent==='Withdraw this memory').click(); })()"
            )
            await panel.wait(
                "document.querySelector('#research-status').textContent.includes("
                + json.dumps("Withdrew displayed memory " + target_memory)
                + ")"
            )
            after = (
                await harness.api_json(backend, "GET", "/browser-experience/research/memories")
            )[1]["memories"]
            assert {row["id"] for row in after} == distractor_ids, after
            evidence["withdrawal"] = {
                "displayed_target": target_memory,
                "remaining_memory_ids": sorted(row["id"] for row in after),
                "last_saved_was_distractor": True,
                "target_withdrawn": target_memory not in {row["id"] for row in after},
            }

            harness.stop_backend(backend_process, backend_log)
            backend_process, backend_log = harness.start_backend(run_dir, env, backend_port)
            await harness.wait_backend(backend)
            after_restart = (
                await harness.api_json(backend, "GET", "/browser-experience/research/memories")
            )[1]["memories"]
            assert target_memory not in {row["id"] for row in after_restart}
            assert {row["id"] for row in after_restart} == distractor_ids
            evidence["restart"] = {
                "memory_persisted_before_withdrawal": True,
                "withdrawal_effective_after_restart": True,
                "active_after_withdrawal": len(after_restart),
            }
            evidence["negative_checks"]["wrong_origin_grant"] = (
                await harness.api(
                    backend,
                    "POST",
                    "/browser-experience/grants",
                    {
                        "goal_id": reopened[0]["data"]["goal_id"],
                        "url": target_page + "?not-allowed",
                        "tab_key": "native13-wrong",
                        "approved": True,
                    },
                )
            ).status_code
            evidence["environment"].update(
                {
                    "chrome": context.browser.version,
                    "presentation": panel_meta.get("presentation", "native side panel target"),
                    "panel_opened_as_ordinary_tab": panel_meta.get(
                        "panel_opened_as_ordinary_tab", False
                    ),
                }
            )
            evidence["provider"] = {"synthetic_calls": len(stub.calls), "paid": False}
            assert len(stub.calls) == 3, stub.calls
            evidence["status"] = "NATIVE_SYNTHETIC_PASS"
            print(
                "VERIFIED native research retrieval, truthful connection and explicit withdrawal;",
                "synthetic calls",
                len(stub.calls),
            )
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
