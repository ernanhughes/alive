"""ALIVE-14-R5 native synthetic approval and read-only qualification."""

import asyncio
import json
import threading
import traceback
import uuid
from http.server import ThreadingHTTPServer
from pathlib import Path

from playwright.async_api import async_playwright

import scripts.alive14r5_experiment as runner
from scripts import native10 as harness

ROOT = Path(__file__).resolve().parents[1]
TOKEN = "native14r5-" + uuid.uuid4().hex


async def main():
    run_dir = ROOT / ".alive" / f"native14r5-{uuid.uuid4().hex[:12]}"
    run_dir.mkdir(parents=True)
    runner.RUNS = run_dir / "runs"
    runner.ARCHIVE = run_dir / "archive"
    state = await asyncio.to_thread(runner.prepare, "synthetic")
    protocol = runner.verify_protocol_identity()
    directory = runner.run_dir("synthetic", protocol)
    token = runner.token_for(directory)
    page_server = ThreadingHTTPServer(("127.0.0.1", 0), harness.PageHandler)
    page_port = page_server.server_address[1]
    page_url = f"http://127.0.0.1:{page_port}/native10"
    threading.Thread(target=page_server.serve_forever, daemon=True).start()
    backend_port = harness.free_port()
    backend = f"http://127.0.0.1:{backend_port}"
    env = harness.backend_env(run_dir, backend, 1, page_url)
    env["DATABASE_URL"] = f"sqlite+aiosqlite:///{(directory / 'experiment.db').as_posix()}"
    env["ALIVE_API_TOKEN"] = token
    env["ALIVE_WORKSPACE"] = str(directory / "workspace")
    env["ALIVE_NATIVE_TEST_PAGES"] = page_url
    env["ALIVE_HEARTBEAT_SECONDS"] = "0.1"
    backend_process = backend_log = None
    context = None
    evidence = {
        "provenance": {
            "kind": "genuine docked Chrome side panel with isolated R5 database",
            "chrome_native": True,
            "provider": "local deterministic stub",
            "paid_calls": 0,
            "source_commit": harness.subprocess.check_output(
                ["git", "rev-parse", "HEAD"], cwd=ROOT, text=True
            ).strip(),
        },
        "campaign": {},
        "native_actions": [],
        "backend_actions": [],
        "screenshots": [],
        "status": "NATIVE_SYNTHETIC_FAIL",
    }
    try:
        harness.TOKEN = token
        backend_process, backend_log = harness.start_backend(run_dir, env, backend_port)
        await harness.wait_backend(backend)
        extension = harness.prepare_extension(run_dir, backend, page_url)
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
            await target_tab.goto(page_url, wait_until="domcontentloaded")
            await target_tab.bring_to_front()
            panel, panel_meta = await harness.open_panel(
                context, cdp, extension_id, target_tab, require_docked=True
            )
            await harness.connect_panel(panel, backend)
            evidence["native_actions"].append("Chrome: connect docked panel")
            await panel.click("#campaign-refresh")
            await panel.wait("document.querySelectorAll('#campaign-select option').length > 1")
            await panel.evaluate(
                "(() => { const s=document.querySelector('#campaign-select');"
                "s.value=" + json.dumps(state["campaign_digest"]) + ";"
                "s.dispatchEvent(new Event('change')); })()"
            )
            await panel.wait(
                "document.querySelector('#campaign-digest').textContent.includes("
                + json.dumps(state["campaign_digest"])
                + ")"
            )
            digest_text = await panel.evaluate(
                "document.querySelector('#campaign-digest').textContent"
            )
            manifest_text = await panel.evaluate(
                "document.querySelector('#campaign-manifest').textContent"
            )
            assert state["campaign_digest"] in digest_text
            assert "stage_1" in manifest_text or "tasks" in manifest_text
            evidence["native_actions"].append("Chrome: review immutable digest and manifest")

            # Stage 2 must be rejected before stage 1.
            await panel.evaluate("document.querySelector('#campaign-stage').value='2'")
            await panel.click("#campaign-approve")
            await panel.wait(
                "document.querySelector('#status').textContent.includes('not eligible')"
            )
            evidence["native_actions"].append(
                "Chrome: observed server rejection of stage 2 before stage 1"
            )

            # Approve stage 1, revoke it, then re-approve before any dispatch.
            await panel.evaluate("document.querySelector('#campaign-stage').value='1'")
            await panel.click("#campaign-approve")
            await panel.wait(
                "document.querySelector('#campaign-status').textContent.includes("
                + json.dumps("active for stage")
                + ")"
            )
            await panel.screenshot(run_dir / "native-r5-stage1-approval.png")
            evidence["screenshots"].append("native-r5-stage1-approval.png")
            await panel.click("#campaign-revoke")
            await panel.wait(
                "document.querySelector('#campaign-status').textContent.includes('is revoked')"
            )
            evidence["native_actions"].append(
                "Chrome: approved stage 1 and revoked it through the owner UI"
            )
            await panel.click("#campaign-approve")
            await panel.wait(
                "document.querySelector('#campaign-status').textContent.includes("
                + json.dumps("active for stage")
                + ")"
            )
            evidence["native_actions"].append("Chrome: re-approved stage 1 with no prior dispatch")
            evidence["campaign"] = {
                "campaign_digest": state["campaign_digest"],
                "digest_displayed": True,
                "manifest_displayed": True,
                "stage_2_before_stage_1_rejected": True,
                "stage_1_approved": True,
                "stage_1_revoked_in_ui": True,
                "stage_1_reapproved_before_dispatch": True,
                "synthetic": True,
            }
            await context.close()
            context = None

        harness.stop_backend(backend_process, backend_log)
        backend_process = backend_log = None
        await asyncio.to_thread(runner.approve, "synthetic", synthetic=True, stage=1)
        first = await asyncio.to_thread(runner.execute, "synthetic", limit=2)
        assert first["phase"] == "staged", first["phase"]
        assert first["execution"]["attempted_dispatches"] == 2
        evidence["backend_actions"].append(
            "Runner CLI: read server stage-1 approval and dispatched exactly two calls"
        )

        backend_process, backend_log = harness.start_backend(run_dir, env, backend_port)
        await harness.wait_backend(backend)
        async with async_playwright() as playwright:
            context = await playwright.chromium.launch_persistent_context(
                str(run_dir / "chrome-profile-stage2"),
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
            await target_tab.goto(page_url, wait_until="domcontentloaded")
            await target_tab.bring_to_front()
            panel, panel_meta = await harness.open_panel(
                context, cdp, extension_id, target_tab, require_docked=True
            )
            await harness.connect_panel(panel, backend)
            await panel.click("#campaign-refresh")
            await panel.wait("document.querySelectorAll('#campaign-select option').length > 1")
            await panel.evaluate(
                "(() => { const s=document.querySelector('#campaign-select');"
                "s.value=" + json.dumps(state["campaign_digest"]) + ";"
                "s.dispatchEvent(new Event('change')); })()"
            )
            await panel.wait(
                "document.querySelector('#campaign-digest').textContent.includes("
                + json.dumps(state["campaign_digest"])
                + ")"
            )
            await panel.evaluate("document.querySelector('#campaign-stage').value='2'")
            await panel.click("#campaign-approve")
            await panel.wait(
                "document.querySelector('#campaign-status').textContent.includes("
                + json.dumps("active for stage")
                + ")"
            )
            await panel.screenshot(run_dir / "native-r5-stage2-approval.png")
            evidence["screenshots"].append("native-r5-stage2-approval.png")
            evidence["native_actions"].append(
                "Chrome: stage 2 approval became available after two stage-1 "
                "attempts and was approved"
            )
            await context.close()
            context = None

        harness.stop_backend(backend_process, backend_log)
        backend_process = backend_log = None
        await asyncio.to_thread(runner.approve, "synthetic", synthetic=True, stage=2)
        second = await asyncio.to_thread(runner.execute, "synthetic", limit=16)
        assert second["phase"] == "awaiting_ratings", second["phase"]
        assert second["execution"]["attempted_dispatches"] == 18
        await asyncio.to_thread(runner.rate, "synthetic", synthetic=True)
        await asyncio.to_thread(runner.reveal, "synthetic")
        await asyncio.to_thread(runner.analyse, "synthetic")
        await asyncio.to_thread(runner.archive, "synthetic")
        evidence["backend_actions"].append(
            "Runner CLI: dispatched remaining 16 calls, rated, revealed, analysed and archived"
        )

        backend_process, backend_log = harness.start_backend(run_dir, env, backend_port)
        await harness.wait_backend(backend)
        async with async_playwright() as playwright:
            context = await playwright.chromium.launch_persistent_context(
                str(run_dir / "chrome-profile-readonly"),
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
            await target_tab.goto(page_url, wait_until="domcontentloaded")
            await target_tab.bring_to_front()
            panel, panel_meta = await harness.open_panel(
                context, cdp, extension_id, target_tab, require_docked=True
            )
            await harness.connect_panel(panel, backend)
            await panel.click("#blind-refresh")
            await panel.wait("document.querySelectorAll('#blind-run option').length > 1")
            await panel.evaluate(
                "(() => { const s=document.querySelector('#blind-run');"
                "s.value=" + json.dumps(second["blind"]["run_id"]) + ";"
                "s.dispatchEvent(new Event('change')); })()"
            )
            await panel.click("#blind-load")
            await panel.wait(
                "document.querySelector('#blind-status').textContent.includes('Read-only results')"
            )
            await panel.screenshot(run_dir / "native-r5-readonly.png")
            evidence["screenshots"].append("native-r5-readonly.png")
            evidence["native_actions"].append(
                "Chrome: loaded archived blind results read-only after restart"
            )
            evidence["environment"] = {
                "chrome": context.browser.version,
                "presentation": panel_meta.get("presentation"),
                "panel_opened_as_ordinary_tab": panel_meta.get(
                    "panel_opened_as_ordinary_tab", False
                ),
                "campaign_digest": state["campaign_digest"],
                "synthetic": True,
            }
            await context.close()
            context = None
        evidence["status"] = "NATIVE_SYNTHETIC_PASS"
        print("NATIVE_SYNTHETIC_PASS", "paid calls 0")
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
        (run_dir / "evidence.json").write_text(
            json.dumps(evidence, indent=2) + "\n", encoding="utf-8"
        )
        print(run_dir / "evidence.json")


if __name__ == "__main__":
    asyncio.run(main())
