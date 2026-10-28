"""ALIVE-14-R5-R1 native synthetic approval and durable-stop qualification.

This harness uses a genuine docked Chrome side panel against an isolated local
backend. It never configures a Meta key and never invokes Meta transport.
"""

import asyncio
import hashlib
import json
import subprocess
import threading
import traceback
import uuid
from http.server import ThreadingHTTPServer
from pathlib import Path

import httpx
from playwright.async_api import async_playwright

import scripts.alive14r5_experiment as runner
from scripts import native10 as harness

ROOT = Path(__file__).resolve().parents[1]
API = "/api/v1/browser-experience"


def source_identity():
    def git(*args):
        return subprocess.check_output(["git", *args], cwd=ROOT, text=True).strip()

    fingerprint = hashlib.sha256()
    for folder in ("alive", "scripts", "extension", "tests", ".github"):
        root = ROOT / folder
        if not root.exists():
            continue
        for path in sorted(root.rglob("*")):
            if not path.is_file() or "__pycache__" in path.parts:
                continue
            fingerprint.update(path.relative_to(ROOT).as_posix().encode())
            fingerprint.update(b"\0")
            fingerprint.update(path.read_bytes())
            fingerprint.update(b"\0")
    return {
        "source_commit": git("rev-parse", "HEAD"),
        "source_tree": git("rev-parse", "HEAD^{tree}"),
        "runtime_source_sha256": fingerprint.hexdigest(),
        "git_status": git("status", "--porcelain=v1"),
    }


async def prepare_campaign(root, label):
    runner.RUNS = root / label / "runs"
    runner.ARCHIVE = root / label / "archive"
    state = await asyncio.to_thread(runner.prepare, "synthetic")
    protocol = runner.verify_protocol_identity()
    directory = runner.run_dir("synthetic", protocol)
    token = runner.token_for(directory)
    return state, protocol, directory, token


def backend_env(root, directory, token, page_url, backend):
    env = harness.backend_env(root, backend, 1, page_url)
    env["DATABASE_URL"] = f"sqlite+aiosqlite:///{(directory / 'experiment.db').as_posix()}"
    env["ALIVE_API_TOKEN"] = token
    env["ALIVE_WORKSPACE"] = str(directory / "workspace")
    env["ALIVE_NATIVE_TEST_PAGES"] = page_url
    env["ALIVE_HEARTBEAT_SECONDS"] = "0.1"
    env["ALIVE_META_API_KEY"] = ""
    env["ALIVE_META_MODEL"] = "muse-spark-1.3"
    env["ALIVE_META_BASE_URL"] = "http://127.0.0.1:1/v1"
    return env


async def api(backend, token, method, path, body=None):
    async with httpx.AsyncClient(timeout=60) as client:
        return await client.request(
            method,
            backend + API + path,
            headers={"Authorization": "Bearer " + token},
            json=body,
        )


async def api_ok(backend, token, method, path, body=None):
    response = await api(backend, token, method, path, body)
    if response.status_code != 200:
        raise RuntimeError(
            f"{method} {path} returned {response.status_code}: {response.text[:2000]}"
        )
    return response.json()


def campaign_task(state, index):
    task_id = state["task_order"][index // 2]
    return next(row for row in state["tasks"] if row["task_id"] == task_id)


async def http_dispatch(backend, token, state, approval, index):
    task = campaign_task(state, index)
    condition = "A" if index % 2 == 0 else "B"
    experiment = {
        "campaign_digest": state["campaign_digest"],
        "approval_id": approval["approval_id"],
        "run_id": state["run_id"],
        "stage": int(approval["stage"]),
        "task_id": task["task_id"],
        "condition": condition,
        "call_index": index,
    }
    body = {
        "snapshot_id": task["snapshot_id"],
        "analysis_mode": "paired",
        "research_question": task["question"],
        "provider": state["provider"],
        "experiment": experiment,
    }
    if condition == "B":
        body["research_id"] = task["memory_id"]
    preview = await api(backend, token, "POST", "/research/outbound/preview", body)
    if preview.status_code != 200:
        return preview
    fresh = preview.json()
    authorized = await api(
        backend,
        token,
        "POST",
        "/research/outbound/authorize",
        {
            "consent_id": fresh["id"],
            "payload_sha256": fresh["payload_sha256"],
            "approved": True,
        },
    )
    if authorized.status_code != 200:
        return authorized
    return await api(
        backend,
        token,
        "POST",
        "/research/relationships",
        {"consent_id": fresh["id"]},
    )


async def launch_panel(playwright, root, profile, extension, backend, page_url):
    context = await playwright.chromium.launch_persistent_context(
        str(root / profile),
        channel="chrome",
        headless=False,
        ignore_default_args=["--disable-extensions"],
        args=["--enable-unsafe-extension-debugging", "--window-size=1440,1100"],
    )
    cdp = await context.browser.new_browser_cdp_session()
    extension_id = (await cdp.send("Extensions.loadUnpacked", {"path": str(extension.resolve())}))[
        "id"
    ]
    target = await context.new_page()
    await target.goto(page_url, wait_until="domcontentloaded")
    await target.bring_to_front()
    panel, meta = await harness.open_panel(context, cdp, extension_id, target, require_docked=True)
    await harness.connect_panel(panel, backend)
    return context, panel, meta


async def load_campaign(panel, digest):
    await panel.click("#campaign-refresh")
    await panel.wait("document.querySelectorAll('#campaign-select option').length > 1")
    await panel.evaluate(
        "(() => { const s=document.querySelector('#campaign-select');"
        "s.value=" + json.dumps(digest) + ";"
        "s.dispatchEvent(new Event('change')); })()"
    )
    await panel.wait(
        "document.querySelector('#campaign-digest').textContent.includes("
        + json.dumps(digest)
        + ")"
    )
    await panel.wait(
        "document.querySelector('#campaign-state').textContent.includes('stage_1_eligible')"
    )


async def assert_disclosure(panel, state):
    digest_text = await panel.evaluate("document.querySelector('#campaign-digest').textContent")
    manifest_text = await panel.evaluate("document.querySelector('#campaign-manifest').textContent")
    disclosure_text = await panel.evaluate(
        "document.querySelector('#campaign-disclosure').textContent"
    )
    content = state["campaign_content"]
    assert state["campaign_digest"] in digest_text
    assert state["protocol_sha256"] in digest_text
    assert state["answer_key_sha256"] in digest_text
    assert "Output cap: 1536 tokens" in digest_text
    assert content["tasks"][0]["question"] in manifest_text
    assert content["cells"][0]["question"] in manifest_text
    assert content["task_order"][0] in manifest_text
    assert '"instructions"' in disclosure_text
    assert '"schema"' in disclosure_text
    assert runner.PAIRED_INSTRUCTIONS.splitlines()[0][:40] in disclosure_text
    return digest_text, manifest_text, disclosure_text


async def campaign_a(root, page_url, evidence):
    state, protocol, directory, token = await prepare_campaign(root, "a")
    backend_port = harness.free_port()
    backend = f"http://127.0.0.1:{backend_port}"
    env = backend_env(root / "a", directory, token, page_url, backend)
    harness.TOKEN = token
    extension = harness.prepare_extension(root / "a", backend, page_url)
    backend_process = backend_log = None
    context = None
    try:
        backend_process, backend_log = harness.start_backend(root / "a", env, backend_port)
        await harness.wait_backend(backend)
        async with async_playwright() as playwright:
            context, panel, meta = await launch_panel(
                playwright,
                root / "a",
                "chrome-profile-a",
                extension,
                backend,
                page_url,
            )
            await load_campaign(panel, state["campaign_digest"])
            digest_text, manifest_text, disclosure_text = await assert_disclosure(panel, state)
            evidence["native_actions"].append(
                "Chrome A: reviewed canonical content, server disclosure, digest and stage limits"
            )

            await panel.evaluate("document.querySelector('#campaign-stage').value='2'")
            await panel.click("#campaign-approve")
            await panel.wait(
                "document.querySelector('#status').textContent.includes('not eligible')"
            )
            evidence["native_actions"].append(
                "Chrome A: server rejected stage 2 before stage 1 eligibility"
            )

            await panel.evaluate("document.querySelector('#campaign-stage').value='1'")
            await panel.click("#campaign-approve")
            await panel.wait(
                "document.querySelector('#campaign-status').textContent.includes("
                + json.dumps("active for stage")
                + ")"
            )
            await panel.screenshot(root / "a" / "native-r5r1-stage1-approval.png")
            evidence["screenshots"].append("native-r5r1-stage1-approval.png")

            evidence["environment"]["campaign_a_chrome"] = context.browser.version
            evidence["environment"]["campaign_a_panel"] = meta
            await context.close()
            context = None

        harness.stop_backend(backend_process, backend_log)
        backend_process = backend_log = None
        await asyncio.to_thread(runner.approve, "synthetic", synthetic=True, stage=1)
        first = await asyncio.to_thread(runner.execute, "synthetic", limit=1)
        assert first["phase"] == "staged", first["phase"]
        assert first["execution"]["attempted_dispatches"] == 1
        approval = runner.read_json(directory / "approval.json")
        evidence["backend_actions"].append(
            "Runner CLI A: imported the panel approval and dispatched exactly one stage-1 cell"
        )

        backend_process, backend_log = harness.start_backend(root / "a", env, backend_port)
        await harness.wait_backend(backend)
        async with async_playwright() as playwright:
            context, panel, meta = await launch_panel(
                playwright,
                root / "a",
                "chrome-profile-a2",
                extension,
                backend,
                page_url,
            )
            await load_campaign(panel, state["campaign_digest"])
            await panel.wait("!document.querySelector('#campaign-revoke').disabled")
            await panel.click("#campaign-revoke")
            await panel.wait(
                "document.querySelector('#campaign-status').textContent.includes('is revoked')"
            )
            await panel.screenshot(root / "a" / "native-r5r1-revoked.png")
            evidence["screenshots"].append("native-r5r1-revoked.png")
            evidence["native_actions"].append(
                "Chrome A: reloaded the active approval after restart and revoked it"
            )
            await context.close()
            context = None

        approval_record = await api_ok(
            backend,
            token,
            "GET",
            f"/research/experiment/approvals/{approval['approval_id']}",
        )
        assert approval_record["data"]["status"] == "revoked"
        inventory = await api_ok(backend, token, "GET", "/research/relationships")
        attempts = [
            row
            for row in inventory["analyses"]
            if row["data"].get("campaign_digest") == state["campaign_digest"]
        ]
        assert len(attempts) == 1
        assert attempts[0]["data"]["call_index"] == 0
        state_view = await api_ok(
            backend,
            token,
            "GET",
            f"/research/experiment/campaigns/{state['campaign_digest']}/state",
        )
        assert state_view["attempts"][0]["call_index"] == 0
        refused = await http_dispatch(backend, token, state, approval, 1)
        assert refused.status_code in (403, 409), refused.text
        evidence["backend_actions"].append(
            "HTTP A: the next dispatch after revocation was refused; attempt count remained one"
        )

        harness.stop_backend(backend_process, backend_log)
        backend_process = backend_log = None
        try:
            runner.execute("synthetic", limit=2)
            raise AssertionError("CLI execution after revocation was not refused")
        except SystemExit as exc:
            assert "no longer active" in str(exc), str(exc)
        settings = runner.build_settings("synthetic", protocol, directory, token)
        with runner.Client(settings, token) as client:
            inventory = runner.call(client, "GET", "/research/relationships")
            attempts = [
                row
                for row in inventory["analyses"]
                if row["data"].get("campaign_digest") == state["campaign_digest"]
            ]
        assert len(attempts) == 1
        assert attempts[0]["data"]["call_index"] == 0
        evidence["campaign_a"] = {
            "campaign_digest": state["campaign_digest"],
            "approval_id": approval["approval_id"],
            "digest_displayed": True,
            "canonical_question": state["campaign_content"]["tasks"][0]["question"],
            "manifest_equals_content": True,
            "disclosure_displayed": True,
            "stage_2_before_stage_1_rejected": True,
            "stage_1_approval_created_by_panel": True,
            "stage_1_cli_calls": 1,
            "revoked_after_first_dispatch": True,
            "next_dispatch_refused_http": refused.status_code,
            "next_dispatch_refused_cli": True,
            "attempt_count_after_revocation": len(attempts),
            "approval_status_after_revocation": approval_record["data"]["status"],
            "technical_state": state_view,
            "synthetic": True,
        }
        evidence["native_actions"].append(
            "Chrome A: revoked approval after one dispatch; HTTP and CLI successor paths refused"
        )
    finally:
        if context:
            try:
                await context.close()
            except Exception:
                pass
        harness.stop_backend(backend_process, backend_log)


async def campaign_b(root, page_url, evidence):
    state, protocol, directory, token = await prepare_campaign(root, "b")
    backend_port = harness.free_port()
    backend = f"http://127.0.0.1:{backend_port}"
    env = backend_env(root / "b", directory, token, page_url, backend)
    harness.TOKEN = token
    extension = harness.prepare_extension(root / "b", backend, page_url)
    backend_process = backend_log = None
    context = None
    try:
        backend_process, backend_log = harness.start_backend(root / "b", env, backend_port)
        await harness.wait_backend(backend)
        async with async_playwright() as playwright:
            context, panel, meta = await launch_panel(
                playwright,
                root / "b",
                "chrome-profile-b1",
                extension,
                backend,
                page_url,
            )
            await load_campaign(panel, state["campaign_digest"])
            await assert_disclosure(panel, state)
            state_view = await api_ok(
                backend,
                token,
                "GET",
                f"/research/experiment/campaigns/{state['campaign_digest']}/state",
            )
            assert state_view["stage_1_eligible"] is False
            assert state_view["stage_2_eligible"] is False
            await panel.evaluate("document.querySelector('#campaign-stage').value='2'")
            await panel.click("#campaign-approve")
            await panel.wait(
                "document.querySelector('#status').textContent.includes('not eligible')"
            )
            evidence["native_actions"].append(
                "Chrome B: reviewed canonical content; stage 2 rejected before stage 1"
            )
            await panel.evaluate("document.querySelector('#campaign-stage').value='1'")
            await panel.click("#campaign-approve")
            await panel.wait(
                "document.querySelector('#campaign-status').textContent.includes("
                + json.dumps("active for stage")
                + ")"
            )
            await panel.screenshot(root / "b" / "native-r5r1-stage1-approval.png")
            evidence["screenshots"].append("native-r5r1-stage1-approval.png")
            evidence["environment"]["campaign_b_chrome"] = context.browser.version
            evidence["environment"]["campaign_b_panel"] = meta
            await context.close()
            context = None

        harness.stop_backend(backend_process, backend_log)
        backend_process = backend_log = None
        await asyncio.to_thread(runner.approve, "synthetic", synthetic=True, stage=1)
        first = await asyncio.to_thread(runner.execute, "synthetic", limit=2)
        assert first["phase"] == "staged", first["phase"]
        assert first["execution"]["attempted_dispatches"] == 2
        evidence["backend_actions"].append(
            "Runner CLI B: imported the panel approval and dispatched exactly two stage-1 calls"
        )

        backend_process, backend_log = harness.start_backend(root / "b", env, backend_port)
        await harness.wait_backend(backend)
        async with async_playwright() as playwright:
            context, panel, meta = await launch_panel(
                playwright,
                root / "b",
                "chrome-profile-b2",
                extension,
                backend,
                page_url,
            )
            await load_campaign(panel, state["campaign_digest"])
            state_view = await api_ok(
                backend,
                token,
                "GET",
                f"/research/experiment/campaigns/{state['campaign_digest']}/state",
            )
            assert state_view["stage_1_eligible"] is True
            assert state_view["stage_2_eligible"] is True
            assert [row["call_index"] for row in state_view["attempts"]] == [0, 1]
            await panel.wait(
                "document.querySelector('#campaign-state').textContent.includes("
                + json.dumps('"stage_1_eligible": true')
                + ")"
            )
            await panel.wait(
                "document.querySelector('#campaign-state').textContent.includes("
                + json.dumps('"stage_2_eligible": true')
                + ")"
            )
            await panel.evaluate("document.querySelector('#campaign-stage').value='2'")
            await panel.click("#campaign-approve")
            await panel.wait(
                "document.querySelector('#campaign-status').textContent.includes("
                + json.dumps("active for stage")
                + ")"
            )
            await panel.screenshot(root / "b" / "native-r5r1-stage2-approval.png")
            evidence["screenshots"].append("native-r5r1-stage2-approval.png")
            evidence["native_actions"].append(
                "Chrome B: technical outcome showed two stage-1 attempts; "
                "separate stage 2 approval succeeded"
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
            "Runner CLI B: dispatched remaining 16 calls, rated, revealed, analysed and archived"
        )

        backend_process, backend_log = harness.start_backend(root / "b", env, backend_port)
        await harness.wait_backend(backend)
        async with async_playwright() as playwright:
            context, panel, meta = await launch_panel(
                playwright,
                root / "b",
                "chrome-profile-b3",
                extension,
                backend,
                page_url,
            )
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
            await panel.screenshot(root / "b" / "native-r5r1-readonly.png")
            evidence["screenshots"].append("native-r5r1-readonly.png")
            evidence["native_actions"].append(
                "Chrome B: loaded archived blind results read-only after restart"
            )
            await context.close()
            context = None
        evidence["campaign_b"] = {
            "campaign_digest": state["campaign_digest"],
            "stage_1_calls": 2,
            "stage_2_calls": 16,
            "total_calls": 18,
            "stage_1_technical_outcome_displayed": True,
            "stage_2_approved_after_eligibility": True,
            "read_only_after_restart": True,
            "blind_run_id": second["blind"]["run_id"],
            "synthetic": True,
            "budget": state["totals"],
        }
    finally:
        if context:
            try:
                await context.close()
            except Exception:
                pass
        harness.stop_backend(backend_process, backend_log)


async def main():
    run_dir = ROOT / ".alive" / f"native14r5r1-{uuid.uuid4().hex[:12]}"
    run_dir.mkdir(parents=True)
    page_server = ThreadingHTTPServer(("127.0.0.1", 0), harness.PageHandler)
    page_port = page_server.server_address[1]
    page_url = f"http://127.0.0.1:{page_port}/native10"
    threading.Thread(target=page_server.serve_forever, daemon=True).start()
    evidence = {
        "provenance": {
            "kind": "genuine docked Chrome side panel with isolated R5-R1 databases",
            "chrome_native": True,
            "provider": "local deterministic stub",
            "paid_calls": 0,
            "real_approval_created": False,
            **source_identity(),
        },
        "native_actions": [],
        "backend_actions": [],
        "screenshots": [],
        "environment": {},
        "campaign_a": {},
        "campaign_b": {},
        "status": "NATIVE_SYNTHETIC_FAIL",
    }
    try:
        await campaign_a(run_dir, page_url, evidence)
        await campaign_b(run_dir, page_url, evidence)
        evidence["status"] = "NATIVE_SYNTHETIC_PASS"
        print("NATIVE_SYNTHETIC_PASS", "paid calls 0")
    except Exception:
        evidence["status"] = "NATIVE_SYNTHETIC_FAIL"
        evidence["error"] = traceback.format_exc()
        raise
    finally:
        page_server.shutdown()
        (run_dir / "evidence.json").write_text(
            json.dumps(evidence, indent=2) + "\n", encoding="utf-8"
        )
        print(run_dir / "evidence.json")


if __name__ == "__main__":
    asyncio.run(main())
