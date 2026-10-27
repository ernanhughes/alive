"""ALIVE-10 isolated native Chrome qualification with a synthetic HTTP provider.

The harness starts a current-branch backend, an isolated SQLite database, a controlled page
server and a local Meta-compatible HTTP stub. It loads a temporary copy of the unpacked
extension in a fresh Chrome profile. No paid inference, owner database or primary worktree
process is used.
"""

import argparse
import asyncio
import base64
import hashlib
import json
import os
import shutil
import socket
import sqlite3
import subprocess
import sys
import threading
import time
import traceback
import uuid
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

import httpx
from playwright.async_api import async_playwright

ROOT = Path(__file__).resolve().parents[1]
TOKEN = "native10-" + uuid.uuid4().hex + uuid.uuid4().hex
GOAL = "Help me understand Python memory management and reference counting."
ROOT_API = "/browser-experience"


def free_port():
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        return sock.getsockname()[1]


def digest(text):
    return hashlib.sha256(text.encode()).hexdigest()


def content(marker):
    return (
        f"Python memory management research note {marker}. "
        "Python uses reference counting and a cycle collector. "
        "This controlled observation is not a factual verification. "
        f"Distinct observation marker {marker}."
    )


class PageHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        if self.path != "/native10":
            self.send_error(404)
            return
        body = (
            "<!doctype html><html><head><meta charset='utf-8'>"
            "<title>ALIVE-10 controlled research page</title></head><body>"
            "<main id='content'>Python memory management initial controlled observation.</main>"
            "</body></html>"
        ).encode()
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, *args):
        return


class StubHandler(BaseHTTPRequestHandler):
    def do_POST(self):
        if self.path != "/v1/chat/completions":
            self.send_error(404)
            return
        length = int(self.headers.get("Content-Length", "0"))
        body = json.loads(self.rfile.read(length) or b"{}")
        try:
            excerpt = json.loads(body["messages"][1]["content"])["untrusted_excerpt"]
        except (KeyError, IndexError, TypeError, json.JSONDecodeError):
            excerpt = "Controlled synthetic excerpt."
        quote = excerpt.split(". ")[0][:120]
        if len(quote) < 5:
            quote = excerpt[:80]
        result = {
            "summary": "Synthetic controlled note: the excerpt mentions Python memory management.",
            "evidence_quote": quote,
            "limitations": "Synthetic provider; only the controlled excerpt was read.",
        }
        self.server.calls.append(
            {
                "model": body.get("model"),
                "request_id": self.headers.get("X-Request-ID"),
                "total_tokens": 150,
            }
        )
        payload = json.dumps(
            {
                "choices": [
                    {
                        "message": {"content": json.dumps(result)},
                        "finish_reason": "stop",
                    }
                ],
                "usage": {
                    "prompt_tokens": 100,
                    "completion_tokens": 50,
                    "total_tokens": 150,
                },
            }
        ).encode()
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(payload)))
        self.end_headers()
        self.wfile.write(payload)

    def log_message(self, *args):
        return


class CdpPanel:
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
        result = await asyncio.wait_for(future, 20)
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

    async def wait(self, expression, seconds=20):
        for _ in range(seconds * 4):
            value = await self.evaluate(expression)
            if value:
                return value
            await asyncio.sleep(0.25)
        status = await self.evaluate("document.querySelector('#status').textContent")
        raise AssertionError("Panel did not reach expected state: " + expression + "; " + status)

    async def screenshot(self, path):
        await self.evaluate(
            "document.querySelector('#connection').open=false; "
            "document.querySelector('#excerpt').open=false"
        )
        await self.send("Page.enable")
        result = await self.send("Page.captureScreenshot", {"captureBeyondViewport": True})
        Path(path).write_bytes(base64.b64decode(result["data"]))


class PagePanel:
    def __init__(self, page):
        self.page = page

    async def evaluate(self, expression):
        return await self.page.evaluate(f"async () => {{ return ({expression}); }}")

    async def click(self, selector):
        await self.page.click(selector)

    async def wait(self, expression, seconds=20):
        for _ in range(seconds * 4):
            value = await self.evaluate(expression)
            if value:
                return value
            await asyncio.sleep(0.25)
        status = await self.page.locator("#status").inner_text()
        raise AssertionError("Panel did not reach expected state: " + expression + "; " + status)

    async def screenshot(self, path):
        await self.page.evaluate(
            "document.querySelector('#connection').open=false; "
            "document.querySelector('#excerpt').open=false"
        )
        await self.page.screenshot(path=path, full_page=True)


def prepare_extension(run_dir, backend, page_url):
    target = run_dir / "extension"
    shutil.copytree(ROOT / "extension", target)
    (target / "config.js").write_text(
        "export const DEFAULT_BACKEND = "
        + json.dumps(backend)
        + ";\n"
        + "export const DEFAULT_BACKENDS = "
        + json.dumps([backend])
        + ";\n"
        + "export const AUTHORISED_PAGES = "
        + json.dumps([page_url])
        + ";\n"
        + "export function isLocalDemo() { return false; }\n",
        encoding="utf-8",
    )
    manifest_path = target / "manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest["name"] = "ALIVE 10 Native Qualification"
    manifest["host_permissions"] = [backend + "/*", page_url.rsplit("/", 1)[0] + "/*"]
    manifest_path.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    return target


def backend_env(run_dir, backend, stub, page_url):
    env = os.environ.copy()
    env.update(
        {
            "DATABASE_URL": f"sqlite+aiosqlite:///{(run_dir / 'native.db').as_posix()}",
            "ALIVE_API_TOKEN": TOKEN,
            "ALIVE_WORKSPACE": str(run_dir / "agent-workspace"),
            "ALIVE_META_BASE_URL": f"http://127.0.0.1:{stub}/v1",
            "ALIVE_META_API_KEY": "native10-synthetic",
            "ALIVE_META_MODEL": "native10-synthetic-v1",
            "ALIVE_NATIVE_TEST_PAGES": page_url,
            "ALIVE_HEARTBEAT_SECONDS": "0.1",
        }
    )
    return env


def run_migrations(env):
    result = subprocess.run(
        [sys.executable, "-m", "alembic", "upgrade", "head"],
        cwd=ROOT,
        env=env,
        capture_output=True,
        text=True,
    )
    if result.returncode:
        raise RuntimeError("Migration failed: " + result.stdout + result.stderr)


def start_backend(run_dir, env, port):
    log = open(run_dir / "backend.log", "a", encoding="utf-8")
    process = subprocess.Popen(
        [
            sys.executable,
            "-m",
            "uvicorn",
            "alive.app:app",
            "--host",
            "127.0.0.1",
            "--port",
            str(port),
        ],
        cwd=ROOT,
        env=env,
        stdout=log,
        stderr=subprocess.STDOUT,
    )
    return process, log


async def wait_backend(backend, seconds=60):
    started = time.monotonic()
    while time.monotonic() - started < seconds:
        try:
            async with httpx.AsyncClient(timeout=2) as client:
                if (await client.get(backend + "/api/v1/health")).status_code == 200:
                    return
        except httpx.HTTPError:
            pass
        await asyncio.sleep(0.25)
    raise TimeoutError("Isolated backend did not become healthy")


def stop_backend(process, log):
    if process and process.poll() is None:
        process.terminate()
        try:
            process.wait(timeout=10)
        except subprocess.TimeoutExpired:
            process.kill()
    if log:
        log.close()


async def api(backend, method, path, body=None, token=TOKEN):
    headers = {"Authorization": "Bearer " + token, "Content-Type": "application/json"}
    async with httpx.AsyncClient(timeout=20) as client:
        response = await client.request(
            method, backend + "/api/v1" + path, json=body, headers=headers
        )
        return response


async def api_json(backend, method, path, body=None, token=TOKEN):
    response = await api(backend, method, path, body, token)
    return response.status_code, response.json() if response.content else None


def note_count(database):
    with sqlite3.connect(database) as connection:
        return connection.execute(
            "select count(*) from web_experiences where kind = 'note'"
        ).fetchone()[0]


def policy_context(policy):
    return next(iter(policy["contexts"].values()))


async def send_observation(panel, page, marker, previous_id=None):
    text = content(marker)
    await page.evaluate(
        "(text) => { document.querySelector('#content').textContent = text; }", text
    )
    await panel.wait(
        "document.querySelector('#preview').textContent.includes(" + json.dumps(marker) + ")"
    )
    await panel.click("#send")
    await panel.wait(
        "(await chrome.storage.session.get('selected')).selected && "
        "(await chrome.storage.session.get('selected')).selected.snapshot.id !== "
        + json.dumps(previous_id)
    )
    selected = await panel.evaluate("(await chrome.storage.session.get('selected')).selected")
    return selected, text


async def settle_note(panel, backend, selected):
    note_id = None
    for _ in range(200):
        note_id = await panel.evaluate("(await chrome.storage.session.get('noteId')).noteId")
        if note_id:
            break
        await asyncio.sleep(0.05)
    assert note_id, "analysis did not create a note"
    for _ in range(400):
        status, note = await api_json(backend, "GET", ROOT_API + "/notes/" + note_id)
        assert status == 200, note
        if note["status"] != "reserved":
            return note
        await asyncio.sleep(0.05)
    raise AssertionError("note did not settle")


async def rate(panel, backend, useful):
    await panel.wait("!document.querySelector('#useful').disabled")
    await panel.click("#useful" if useful else "#needs-work")
    await panel.wait("document.querySelector('#status').textContent.includes('Feedback saved')")
    status, state = await api_json(backend, "GET", ROOT_API)
    assert status == 200, state
    return state["policy"]["data"]


async def connect_panel(panel, backend):
    await panel.wait("!document.querySelector('#connect').disabled")
    await panel.evaluate(
        "(async () => { document.querySelector('#backend').value="
        + json.dumps(backend)
        + "; document.querySelector('#token').value="
        + json.dumps(TOKEN)
        + "; })()"
    )
    await panel.click("#connect")
    await panel.wait("document.querySelector('#status').textContent.includes('Connected')")


async def start_page(panel, page_url, marker):
    await panel.evaluate(
        "(async () => { const tabs=await chrome.tabs.query({}); "
        "const tab=tabs.find(t=>t.url==="
        + json.dumps(page_url)
        + "); if (!tab) throw new Error('controlled tab not found'); "
        "await chrome.tabs.update(tab.id,{active:true}); })()"
    )
    await panel.click("#start")
    await panel.wait(
        "document.querySelector('#preview').textContent.includes(" + json.dumps(marker) + ")"
    )


async def main(args):
    run_dir = ROOT / ".alive" / f"native10-{uuid.uuid4().hex[:12]}"
    run_dir.mkdir(parents=True, exist_ok=False)
    page_server = ThreadingHTTPServer(("127.0.0.1", 0), PageHandler)
    page_port = page_server.server_address[1]
    page_url = f"http://127.0.0.1:{page_port}/native10"
    stub_server = ThreadingHTTPServer(("127.0.0.1", 0), StubHandler)
    stub_server.calls = []
    stub_port = stub_server.server_address[1]
    for server in (page_server, stub_server):
        threading.Thread(target=server.serve_forever, daemon=True).start()
    backend_port = free_port()
    backend = f"http://127.0.0.1:{backend_port}"
    env = backend_env(run_dir, backend, stub_port, page_url)
    browser = None
    backend_process = None
    backend_log = None
    evidence = {
        "provenance": {
            "kind": "native Chrome extension with isolated current-branch backend",
            "chrome_native": True,
            "provider": "local Meta-compatible synthetic HTTP stub",
            "paid_calls": 0,
            "meta_inference": False,
            "source_commit": subprocess.check_output(
                ["git", "rev-parse", "HEAD"], cwd=ROOT, text=True
            ).strip(),
        },
        "environment": {
            "backend": backend,
            "page_url": page_url,
            "database": str(run_dir / "native.db"),
            "template_extension": str(ROOT / "extension"),
            "isolated_extension": str(run_dir / "extension"),
        },
        "steps": [],
    }
    try:
        run_migrations(env)
        backend_process, backend_log = start_backend(run_dir, env, backend_port)
        await wait_backend(backend)
        extension = prepare_extension(run_dir, backend, page_url)
        async with async_playwright() as playwright:
            context = await playwright.chromium.launch_persistent_context(
                str(run_dir / "chrome-profile"),
                channel="chrome",
                headless=not args.headful,
                ignore_default_args=["--disable-extensions"],
                args=[
                    "--enable-unsafe-extension-debugging",
                    "--no-first-run",
                    "--no-default-browser-check",
                    "--window-size=1440,1100",
                ],
            )
            browser = context.browser
            try:
                cdp = await context.browser.new_browser_cdp_session()
                extension_id = (
                    await cdp.send("Extensions.loadUnpacked", {"path": str(extension.resolve())})
                )["id"]
                page = await context.new_page()
                await page.goto(page_url, wait_until="domcontentloaded")
                await page.evaluate(
                    "(text) => { document.querySelector('#content').textContent = text; }",
                    content("initial"),
                )
                await page.bring_to_front()
                targets = (await cdp.send("Target.getTargets", {"filter": [{"type": "tab"}]}))[
                    "targetInfos"
                ]
                target = next(t for t in targets if t["url"] == page_url)
                await cdp.send(
                    "Extensions.triggerAction",
                    {"id": extension_id, "targetId": target["targetId"]},
                )
                await asyncio.sleep(0.8)
                targets = (await cdp.send("Target.getTargets", {"filter": [{}]}))["targetInfos"]
                panel_target = next(
                    (
                        t
                        for t in targets
                        if t["type"] == "page" and t["url"].endswith("/panel.html")
                    ),
                    None,
                )
                if panel_target:
                    session = (
                        await cdp.send(
                            "Target.attachToTarget",
                            {"targetId": panel_target["targetId"], "flatten": False},
                        )
                    )["sessionId"]
                    panel = CdpPanel(cdp, session)
                    evidence["environment"]["presentation"] = "native side panel target"
                else:
                    panel_page = await context.new_page()
                    await panel_page.goto(f"chrome-extension://{extension_id}/panel.html")
                    panel = PagePanel(panel_page)
                    evidence["environment"]["presentation"] = "extension page fallback"
                    evidence["environment"]["available_targets"] = [
                        {"type": t["type"], "url": t["url"]} for t in targets
                    ]
                evidence["environment"]["chrome"] = context.browser.version
                evidence["environment"]["extension_id"] = extension_id
                await connect_panel(panel, backend)
                await panel.evaluate("document.querySelector('#goal').value=" + json.dumps(GOAL))
                await panel.click("#save-goal")
                await panel.wait(
                    "document.querySelector('#status').textContent.includes('Goal saved')"
                )
                await start_page(panel, page_url, "initial")
                grant = await panel.evaluate(
                    "(await chrome.storage.session.get('grantId')).grantId"
                )
                evidence["environment"]["grant_id"] = grant

                # Three genuinely distinct controlled observations.
                previous = None
                for index, marker in enumerate(("distinct-1", "distinct-2", "distinct-3"), 1):
                    selected, _ = await send_observation(panel, page, marker, previous)
                    previous = selected["snapshot"]["id"]
                    assert selected["decision"]["action"] == "analyse", selected["decision"]
                    assert selected["decision"]["adaptive_policy"]["support"] == index - 1
                    await panel.click("#analyse")
                    note = await settle_note(panel, backend, selected)
                    assert note["status"] == "validated", note["data"].get("error")
                    assert (
                        note["data"]["output"]["evidence_quote"]
                        in selected["snapshot"]["data"]["text"]
                    )
                    policy = await rate(panel, backend, False)
                    policy_ctx = policy_context(policy)
                    assert (
                        policy_ctx["evidence"].keys()
                        == {
                            digest(content("distinct-1")),
                            digest(content("distinct-2")),
                            digest(content("distinct-3")),
                        }
                        if index == 3
                        else len(policy_ctx["evidence"]) == index
                    )
                    evidence["steps"].append(
                        {
                            "name": f"distinct-{index}",
                            "action": selected["decision"]["action"],
                            "policy_version": policy["version"],
                            "distinct_support": len(policy_ctx["evidence"]),
                        }
                    )

                # Suppression, then one bounded owner correction.
                selected, _ = await send_observation(panel, page, "suppressed-1", previous)
                previous = selected["snapshot"]["id"]
                assert selected["decision"]["action"] == "no_action"
                assert selected["decision"]["no_action_source"] == "feedback_policy"
                assert selected["decision"]["without_feedback_action"] == "analyse"
                assert selected["decision"]["adaptive_policy"]["suppressions"] == 1
                assert selected["decision"]["note"] is None
                assert await panel.evaluate("document.querySelector('#useful').disabled")
                assert len(stub_server.calls) == 3
                evidence["steps"].append(
                    {
                        "name": "suppressed-1",
                        "action": "no_action",
                        "source": "feedback_policy",
                        "suppressions": 1,
                        "provider_calls": len(stub_server.calls),
                    }
                )

                selected, _ = await send_observation(panel, page, "suppressed-2", previous)
                previous = selected["snapshot"]["id"]
                assert selected["decision"]["action"] == "no_action"
                assert selected["decision"]["adaptive_policy"]["suppressions"] == 2
                await panel.click("#analyse")
                correction_note = await settle_note(panel, backend, selected)
                assert correction_note["status"] == "validated"
                assert correction_note["data"]["owner_correction"] is True
                assert len(stub_server.calls) == 4
                state = (await api_json(backend, "GET", ROOT_API))[1]
                assert state["corrections"]
                assert state["corrections"][-1]["data"]["suppressions_reset"] is True
                policy = state["policy"]["data"]
                assert policy_context(policy)["suppressions"] == 0
                evidence["steps"].append(
                    {
                        "name": "owner_correction",
                        "action": "analyse",
                        "correction": True,
                        "policy_version": policy["version"],
                        "provider_calls": len(stub_server.calls),
                    }
                )

                # Three paused observations reach the probe threshold. The next observation
                # is a bounded periodic re-evaluation rather than permanent suppression.
                for index in range(3):
                    marker = f"paused-{index + 1}"
                    selected, _ = await send_observation(panel, page, marker, previous)
                    previous = selected["snapshot"]["id"]
                    assert selected["decision"]["action"] == "no_action"
                    assert selected["decision"]["adaptive_policy"]["suppressions"] == index + 1
                evidence["steps"].append(
                    {"name": "three_paused_observations", "provider_calls": len(stub_server.calls)}
                )

                selected, _ = await send_observation(panel, page, "probe-1", previous)
                previous = selected["snapshot"]["id"]
                probe_snapshot = selected
                assert selected["decision"]["action"] == "analyse"
                assert selected["decision"]["probe"] is True
                assert selected["decision"]["adaptive_policy"]["probe"] is True
                assert selected["decision"]["adaptive_policy"]["suppressions"] == 0
                await panel.click("#analyse")
                probe_note = await settle_note(panel, backend, selected)
                assert probe_note["status"] == "validated"
                assert len(stub_server.calls) == 5
                policy = await rate(panel, backend, True)
                policy_ctx = policy_context(policy)
                assert len(policy_ctx["evidence"]) == 4
                assert sum(1 for unit in policy_ctx["evidence"].values() if unit["useful"]) == 1
                evidence["steps"].append(
                    {
                        "name": "periodic_probe",
                        "action": "analyse",
                        "probe": True,
                        "policy_version": policy["version"],
                        "distinct_support": len(policy_ctx["evidence"]),
                        "provider_calls": len(stub_server.calls),
                    }
                )

                selected, _ = await send_observation(panel, page, "restored-1", previous)
                previous = selected["snapshot"]["id"]
                assert selected["decision"]["action"] == "analyse"
                assert selected["decision"]["adaptive_policy"]["support"] == 4
                assert selected["decision"]["adaptive_policy"]["useful_rate"] == 0.25
                evidence["steps"].append(
                    {
                        "name": "restored",
                        "action": "analyse",
                        "distinct_support": 4,
                        "provider_calls": len(stub_server.calls),
                    }
                )

                duplicate = await api(
                    backend,
                    "POST",
                    ROOT_API + "/analyse",
                    {
                        "snapshot_id": probe_snapshot["snapshot"]["id"],
                        "reviewed_sha256": probe_snapshot["snapshot"]["data"]["sha256"],
                        "send_to_meta": True,
                    },
                )
                assert duplicate.status_code == 409, duplicate.text
                assert len(stub_server.calls) == 5
                evidence["negative_checks"] = {
                    "duplicate_analysis": duplicate.status_code,
                    "provider_calls": len(stub_server.calls),
                }

                policy_before_restart = (await api_json(backend, "GET", ROOT_API))[1]["policy"][
                    "data"
                ]
                notes_before = note_count(run_dir / "native.db")
                await panel.screenshot(run_dir / "native-panel.png")

                stop_backend(backend_process, backend_log)
                backend_process, backend_log = start_backend(run_dir, env, backend_port)
                await wait_backend(backend)
                policy_after_restart = (await api_json(backend, "GET", ROOT_API))[1]["policy"][
                    "data"
                ]
                notes_after = note_count(run_dir / "native.db")
                assert policy_after_restart["version"] == policy_before_restart["version"]
                assert notes_after == notes_before
                assert len(stub_server.calls) == 5
                stale = await api(
                    backend,
                    "POST",
                    ROOT_API + "/snapshots",
                    {
                        "grant_id": grant,
                        "url": page_url,
                        "title": "Controlled page",
                        "text": content("stale-grant"),
                        "reviewed_sha256": digest(content("stale-grant")),
                    },
                )
                assert stale.status_code == 403, stale.text
                await start_page(panel, page_url, "restored-1")
                new_grant = await panel.evaluate(
                    "(await chrome.storage.session.get('grantId')).grantId"
                )
                selected, _ = await send_observation(panel, page, "post-restart", previous)
                assert selected["decision"]["action"] == "analyse"
                assert selected["decision"]["adaptive_policy"]["support"] == 4
                evidence["restart"] = {
                    "policy_version_before": policy_before_restart["version"],
                    "policy_version_after": policy_after_restart["version"],
                    "notes_before": notes_before,
                    "notes_after": notes_after,
                    "stale_grant_status": stale.status_code,
                    "duplicate_inference": notes_after != notes_before
                    or len(stub_server.calls) != 5,
                    "post_restart_action": selected["decision"]["action"],
                }

                wrong = await api(
                    backend,
                    "POST",
                    ROOT_API + "/grants",
                    {
                        "goal_id": state["goals"][0]["id"],
                        "url": page_url + "?not-allowed",
                        "tab_key": "native10-wrong-origin",
                        "approved": True,
                    },
                )
                bad_hash = await api(
                    backend,
                    "POST",
                    ROOT_API + "/snapshots",
                    {
                        "grant_id": new_grant,
                        "url": page_url,
                        "title": "Controlled page",
                        "text": content("bad-hash"),
                        "reviewed_sha256": "0" * 64,
                    },
                )
                budget_text = content("budget-check")
                budget_snapshot = await api(
                    backend,
                    "POST",
                    ROOT_API + "/snapshots",
                    {
                        "grant_id": new_grant,
                        "url": page_url,
                        "title": "Controlled page",
                        "text": budget_text,
                        "reviewed_sha256": digest(budget_text),
                    },
                )
                assert budget_snapshot.status_code == 200, budget_snapshot.text
                budget_body = budget_snapshot.json()
                assert budget_body["decision"]["action"] == "analyse"
                assert (
                    await api(
                        backend,
                        "POST",
                        "/cognition/configuration",
                        {"session_calls": 0},
                    )
                ).status_code == 200
                budget_blocked = await api(
                    backend,
                    "POST",
                    ROOT_API + "/analyse",
                    {
                        "snapshot_id": budget_body["snapshot"]["id"],
                        "reviewed_sha256": budget_body["snapshot"]["data"]["sha256"],
                        "send_to_meta": True,
                    },
                )
                assert budget_blocked.status_code == 409, budget_blocked.text
                assert len(stub_server.calls) == 5
                evidence["negative_checks"] |= {
                    "wrong_origin_grant": wrong.status_code,
                    "modified_hash_snapshot": bad_hash.status_code,
                    "budget_exhaustion": budget_blocked.status_code,
                }
                evidence["provider"] = {
                    "kind": "local Meta-compatible synthetic HTTP stub",
                    "calls": len(stub_server.calls),
                    "prompt_tokens": 500,
                    "completion_tokens": 250,
                    "total_tokens": 750,
                    "estimated_usd": 0.0016875,
                    "paid": False,
                    "note": "Estimated with ALIVE's price() formula; not a Meta charge.",
                }
                evidence["status"] = "NATIVE_SYNTHETIC_PASS"
                print("VERIFIED native:", backend, "calls", len(stub_server.calls))
            finally:
                if browser:
                    await context.close()
    except Exception:
        evidence["status"] = "NATIVE_SYNTHETIC_FAIL"
        evidence["error"] = traceback.format_exc()
        raise
    finally:
        stop_backend(backend_process, backend_log)
        page_server.shutdown()
        stub_server.shutdown()
        (run_dir / "evidence.json").write_text(
            json.dumps(evidence, indent=2) + "\n", encoding="utf-8"
        )
        (run_dir / "provider-calls.json").write_text(
            json.dumps(stub_server.calls, indent=2) + "\n", encoding="utf-8"
        )
        print("evidence:", run_dir / "evidence.json")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--headful", action="store_true")
    asyncio.run(main(parser.parse_args()))
