"""ALIVE-01 — First Contact. Owns backend processes; adds data, never resets the database."""

import argparse
import asyncio
import json
import shutil
import subprocess
import sys
import time
import uuid
from contextlib import asynccontextmanager
from pathlib import Path

import httpx
from playwright.async_api import async_playwright, expect

from alive.config import Settings, prepare_local
from scripts.alive_logs import ensure_log_dir, log_path


def wait_http(url):
    for _ in range(100):
        try:
            if httpx.get(url, timeout=1).is_success:
                return
        except httpx.HTTPError:
            pass
        time.sleep(0.2)
    raise RuntimeError(f"Service did not start: {url}")


async def demonstrate(runner, restart):
    settings = Settings()
    token = prepare_local(settings)
    async with httpx.AsyncClient(
        base_url="http://127.0.0.1:8000/api/v1",
        timeout=40,
        headers={"Authorization": f"Bearer {token}"},
    ) as client:

        async def get(path):
            response = await client.get(path)
            response.raise_for_status()
            return response.json()

        async def post(path, body=None):
            response = await client.post(path, json=body or {})
            response.raise_for_status()
            return response.json()

        capabilities = await get("/capabilities")
        assert capabilities["database"]["backend"] == "postgresql"
        await post("/alive/start")
        before = await get("/alive")
        identity = before["identity"]["id"]
        marker = "green beacon " + uuid.uuid4().hex[:10]
        browser = await post("/browser/sessions")
        session_id = browser["id"]
        path = f"/browser/sessions/{session_id}"
        await post(path + "/navigate", {"url": "http://127.0.0.1:8000/demo"})
        await post(
            path + "/actions", {"operation": "fill", "selector": "#message", "value": marker}
        )
        observation = await post(path + "/actions", {"operation": "click", "selector": "#change"})
        assert marker in observation["text"]
        screenshot = await post(path + "/actions", {"operation": "screenshot"})
        assert screenshot["image"].startswith("data:image/png;base64,")
        denied = await client.post(path + "/navigate", json={"url": "https://example.com"})
        assert denied.status_code == 403
        denied = await client.post(path + "/actions", json={"operation": "click", "selector": "h1"})
        assert denied.status_code == 403
        search = await post("/memories/search", {"query": marker})
        assert search["mode"] == "postgresql_fts" and search["results"]
        memory_id = search["results"][0]["id"]
        source_event_id = search["results"][0]["source_event_id"]
        run_id = (
            await post(
                "/agents/runs",
                {
                    "runner": runner,
                    "objective": f"Examine this controlled observation: {marker}. "
                    "Propose one verification goal.",
                },
            )
        )["id"]
        for _ in range(300):
            run = await get("/agents/runs/" + run_id)
            if run["status"] != "running":
                break
            await asyncio.sleep(0.5)
        assert run["status"] == "completed", run["error"]
        goals = await get("/goals")
        unfinished = [g for g in goals if g["status"] == "proposed" and marker in g["description"]]
        assert unfinished
        goal_id = unfinished[0]["id"]
        await post(f"/goals/{goal_id}/transition", {"status": "accepted"})
        await client.delete(path)
        for _ in range(40):
            capabilities = await get("/capabilities")
            if capabilities["zeromq"]["received"] > 0:
                break
            await asyncio.sleep(0.1)
        assert capabilities["zeromq"]["received"] > 0
        async with async_playwright() as p:
            chrome = await p.chromium.launch(channel="chrome", headless=True)
            context = await chrome.new_context(viewport={"width": 1440, "height": 1050})
            await context.add_init_script(
                f"sessionStorage.setItem('alive-token',{json.dumps(token)})"
            )
            page = await context.new_page()
            await page.goto("http://127.0.0.1:5173")
            await expect(page.locator(".connection")).to_contain_text("Backend connected")
            await page.get_by_role("button", name="Live events").click()
            await expect(page.locator(".events")).to_contain_text("browser.dom_changed")
            await page.get_by_role("button", name="Memory", exact=True).click()
            await page.get_by_label("Search memories").fill(marker)
            await page.get_by_role("button", name="Search", exact=True).click()
            await expect(page.locator(".memory").first).to_contain_text(marker)
            await page.get_by_role("button", name="Overview", exact=True).click()
            await page.evaluate("window.scrollTo(0,0)")
            await page.screenshot(path=".alive/first-contact.png", full_page=True)
            await chrome.close()
        print("Browser → PostgreSQL → ZeroMQ → dashboard → memory → agent → accepted goal: PASS")
        await asyncio.to_thread(restart)
        after = await get("/alive")
        assert after["identity"]["id"] == identity
        search_after = await post("/memories/search", {"query": marker})
        assert any(m["id"] == memory_id for m in search_after["results"])
        assert any(g["id"] == goal_id and g["status"] == "accepted" for g in await get("/goals"))
        # Cursor replay recovers a specific observation even after process restart.
        async with settings_database(settings) as db:
            from sqlalchemy import select

            from alive.models import Event

            async with db.sessions() as session:
                event = await session.scalar(select(Event).where(Event.id == source_event_id))
                assert event is not None
                sequence = event.sequence_number
        replay = await get(f"/events?after={sequence - 1}&limit=1")
        assert replay[0]["event_id"] == source_event_id
        evidence = {
            "identity": identity,
            "runner": runner,
            "run_id": run_id,
            "run_status": run["status"],
            "event_id": source_event_id,
            "memory_id": memory_id,
            "goal_id": goal_id,
            "postgresql_fts": True,
            "pgvector_storage": capabilities["pgvector"]["storage"],
            "zeromq_received_before_restart": capabilities["zeromq"]["received"],
            "restart_continuity": True,
            "dashboard_live": True,
            "marker": marker,
        }
        Path(".alive/first-contact.json").write_text(json.dumps(evidence, indent=2))
        print(
            "Identity, event cursor replay, memory and accepted unfinished goal after restart: PASS"
        )
        print(f"Agent runner: {runner}; evidence: .alive/first-contact.json")


@asynccontextmanager
async def settings_database(settings):
    from alive.db import Database

    db = Database(settings.database_url)
    try:
        yield db
    finally:
        await db.engine.dispose()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--runner", choices=["pi", "mock"], default="mock")
    parser.add_argument("--existing-dashboard", action="store_true")
    args = parser.parse_args()
    try:
        httpx.get("http://127.0.0.1:8000/api/v1/health", timeout=1)
    except httpx.HTTPError:
        pass
    else:
        raise SystemExit(
            "Stop your existing backend before running the owned restart demonstration."
        )
    Path(".alive").mkdir(exist_ok=True)
    ensure_log_dir()
    subprocess.run([sys.executable, "-m", "alembic", "upgrade", "head"], check=True)
    log = log_path("first-contact-backend.log").open("w", encoding="utf-8")
    backend = None
    dashboard = None

    def start_backend():
        proc = subprocess.Popen(
            [
                sys.executable,
                "-m",
                "uvicorn",
                "alive.app:app",
                "--host",
                "127.0.0.1",
                "--port",
                "8000",
            ],
            stdout=log,
            stderr=log,
        )
        wait_http("http://127.0.0.1:8000/api/v1/health")
        return proc

    def restart():
        nonlocal backend
        backend.terminate()
        backend.wait(timeout=10)
        backend = start_backend()

    try:
        backend = start_backend()
        if not args.existing_dashboard:
            # Direct Node entry avoids npm shell wrappers and orphan process trees on Windows.
            dashboard = subprocess.Popen(
                [
                    shutil.which("node"),
                    "node_modules/vite/bin/vite.js",
                    "--host",
                    "127.0.0.1",
                    "--port",
                    "5173",
                    "--strictPort",
                ],
                cwd="dashboard",
                stdout=log,
                stderr=log,
            )
        wait_http("http://127.0.0.1:5173")
        asyncio.run(demonstrate(args.runner, restart))
    finally:
        for proc in [backend, dashboard]:
            if proc and proc.poll() is None:
                proc.terminate()
                proc.wait(timeout=10)
        log.close()


if __name__ == "__main__":
    main()
