"""Recall real Meta experience from a backed-up store with inference disabled."""

import argparse
import asyncio
import hashlib
import html
import json
import sqlite3
import threading
import uuid
from pathlib import Path
from urllib.parse import urlsplit

from playwright.async_api import async_playwright

from scripts import native10 as h


async def main(prior):
    prior = prior.resolve()
    allowed = (h.ROOT / ".alive").resolve()
    if not prior.is_relative_to(allowed):
        raise ValueError("Recall input must be an owned local qualification run")
    evidence_before = json.loads((prior / "evidence.json").read_text())
    if evidence_before["status"] != "NATIVE_META_PASS":
        raise ValueError("A completed real Meta qualification is required")
    rows = json.loads((prior / "persisted-experience.json").read_text())
    original_digest = hashlib.sha256((prior / "native.db").read_bytes()).hexdigest()
    feedback = next(r for r in rows if r["kind"] == "feedback" and r["data"]["useful"])
    # The persisted evidence links feedback to a note; resolve the parent from SQLite.
    with sqlite3.connect(f"file:{(prior / 'native.db').as_posix()}?mode=ro", uri=True) as original:
        note_id = original.execute(
            "SELECT parent_id FROM web_experiences WHERE id=?", (feedback["id"],)
        ).fetchone()[0]
        note = next(r for r in rows if r["id"] == note_id)
        original_spent = original.execute("SELECT spent FROM cognitive_control").fetchone()[0]
    url = urlsplit(note["data"]["url"])
    if url.hostname != "127.0.0.1" or url.path != "/native10" or not url.port:
        raise ValueError("Expected the original controlled loopback source")
    source_text = next(
        r["data"]["text"]
        for r in rows
        if r["kind"] == "snapshot" and r["data"]["sha256"] == note["data"]["sha256"]
    )

    class RecallPage(h.PageHandler):
        def do_GET(self):
            if self.path != url.path:
                self.send_error(404)
                return
            body = (
                "<!doctype html><meta charset='utf-8'><title>ALIVE-11 recall-only workbench</title>"
                "<style>body{font:22px/1.6 system-ui;margin:60px;background:#eef3e9}"
                "main{background:white;padding:35px}</style>"
                "<h1>Recovered research experience</h1>"
                "<p>Real Meta note recalled. Credentials disabled. No new inference.</p>"
                f"<main>{html.escape(source_text)}</main>"
            ).encode()
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

    run = allowed / ("native11-recall-" + uuid.uuid4().hex[:12])
    run.mkdir()
    with sqlite3.connect(f"file:{(prior / 'native.db').as_posix()}?mode=ro", uri=True) as original:
        with sqlite3.connect(run / "native.db") as copy:
            original.backup(copy)
    # Binding the recorded source port must succeed; never kill a process or substitute its URL.
    server = h.ThreadingHTTPServer(("127.0.0.1", url.port), RecallPage)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    port = h.free_port()
    backend = f"http://127.0.0.1:{port}"
    env = h.backend_env(run, backend, 1, note["data"]["url"])
    env.update(
        ALIVE_META_API_KEY="",
        ALIVE_META_URL="http://127.0.0.1:1/disabled",
        ALIVE_COMPANION_MICRO_USD_LIMIT="0",
        ALIVE_EMBEDDING_ENABLED="false",
    )
    process, log = None, None
    result = {
        "kind": "native docked recall of backed-up Meta store",
        "new_inference_calls": 0,
        "credentials_disabled": True,
        "usd_limit": 0,
        "original_store_unchanged": True,
        "original_meta_source": evidence_before["provenance"]["source_commit"],
    }
    try:
        process, log = h.start_backend(run, env, port)
        await h.wait_backend(backend)
        status, identity = await h.api_json(backend, "GET", "/provenance")
        assert status == 200
        assert identity["source_commit"] == evidence_before["provenance"]["source_commit"]
        assert (
            identity["database"]["fingerprint"]
            == hashlib.sha256(str((run / "native.db").resolve()).encode()).hexdigest()
        )
        result["backend_identity"] = identity
        old_grant = next(
            r for r in reversed(rows) if r["kind"] == "grant" and r["status"] == "active"
        )
        stale, _ = await h.api_json(
            backend,
            "POST",
            h.ROOT_API + "/snapshots",
            {
                "grant_id": old_grant["id"],
                "url": note["data"]["url"],
                "title": "Stale grant test",
                "text": source_text,
                "reviewed_sha256": h.digest(source_text),
            },
        )
        assert stale == 403
        result["old_grant_rejected"] = stale
        extension = h.prepare_extension(run, backend, note["data"]["url"])
        async with async_playwright() as p:
            context = await p.chromium.launch_persistent_context(
                str(run / "profile"),
                channel="chrome",
                headless=False,
                ignore_default_args=["--disable-extensions"],
                args=["--enable-unsafe-extension-debugging", "--window-size=1440,1100"],
            )
            try:
                cdp = await context.browser.new_browser_cdp_session()
                ext = (await cdp.send("Extensions.loadUnpacked", {"path": str(extension)}))["id"]
                page = await context.new_page()
                await page.goto(note["data"]["url"])
                panel, presentation = await h.open_panel(
                    context, cdp, ext, page, require_docked=True
                )
                await h.connect_panel(panel, backend)
                await panel.evaluate(
                    "document.querySelector('#resume').value=" + json.dumps(note["data"]["goal_id"])
                )
                await panel.evaluate(
                    "document.querySelector('#resume').dispatchEvent(new Event('change'))"
                )
                await panel.wait(
                    "document.querySelector('#status').textContent.includes('Goal resumed')"
                )
                await h.start_page(panel, page.url, "recall", lambda _: source_text)
                await panel.click("#send")
                await panel.wait(
                    "document.querySelector('#status').textContent"
                    ".includes('Recalled useful evidence')"
                )
                selected = await panel.evaluate(
                    "(await chrome.storage.session.get('selected')).selected"
                )
                assert selected["decision"]["action"] == "recall"
                assert selected["decision"]["note"]["id"] == note_id
                assert await panel.evaluate("document.querySelector('#analyse').disabled")
                assert h.note_count(run / "native.db") == 8
                with sqlite3.connect(run / "native.db") as db:
                    assert json.loads(
                        db.execute("SELECT spent FROM cognitive_control").fetchone()[0]
                    ) == json.loads(original_spent)
                result.update(
                    presentation,
                    status="NATIVE_RECALL_PASS",
                    recalled_note_id=note_id,
                    note_count_before=8,
                    note_count_after=8,
                    expenditure_unchanged=True,
                    policy_version=selected["decision"]["policy_version"],
                )
                await panel.screenshot(run / "recall.png")
            finally:
                await context.close()
    except Exception as exc:
        result.update(status="NATIVE_RECALL_FAIL", error=type(exc).__name__)
        raise
    finally:
        h.stop_backend(process, log)
        server.shutdown()
        assert hashlib.sha256((prior / "native.db").read_bytes()).hexdigest() == original_digest
        result["original_database_sha256"] = original_digest
        result["recall_runner_sha256"] = hashlib.sha256(Path(__file__).read_bytes()).hexdigest()
        (run / "recall.json").write_text(json.dumps(result, indent=2), encoding="utf-8")
        print(run / "recall.json")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("prior", type=Path)
    asyncio.run(main(parser.parse_args().prior))
