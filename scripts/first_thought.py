"""ALIVE-02 — The First Autonomous Thought. Real DOM perception, bounded roles and restart."""

import argparse
import asyncio
import json
import shutil
import subprocess
import sys
import time
from pathlib import Path

import httpx
from playwright.async_api import async_playwright, expect

from alive.config import Settings, prepare_local
from scripts.first_contact import wait_http


async def demonstrate(provider, restart):
    token = prepare_local(Settings())
    async with httpx.AsyncClient(
        base_url="http://127.0.0.1:8000/api/v1",
        headers={"Authorization": "Bearer " + token},
        timeout=60,
    ) as client:

        async def get(path):
            response = await client.get(path)
            response.raise_for_status()
            return response.json()

        async def post(path, data=None):
            response = await client.post(path, json=data or {})
            response.raise_for_status()
            return response.json()

        assert (await get("/capabilities"))["database"]["backend"] == "postgresql"
        await post("/cognition/control", {"command": "pause"})
        await post("/cognition/control", {"command": "new_session"})
        await post("/cognition/configuration", {})
        identity = (await get("/alive"))["identity"]["id"]
        await post("/cognition/control", {"command": "start", "provider": provider})
        results = []
        for scenario in ["relevant", "noise", "contradiction"]:
            lab = await post("/lab", {"scenario": scenario, "seed": 29})
            await post("/memories/index")
            browser = await post("/browser/sessions")
            path = "/browser/sessions/" + browser["id"]
            await post(path + "/navigate", {"url": "http://127.0.0.1:8000/world/" + lab["id"]})
            await post(path + "/observation", {"approved": True})
            before = (await get("/cognition"))["control"]["spent"].get("experiment_calls", 0)
            await asyncio.sleep(0.8)
            await post("/lab/" + lab["id"] + "/inject")
            if scenario == "noise":
                for _ in range(12):
                    await post("/lab/" + lab["id"] + "/inject")
                await asyncio.sleep(2)
                after = (await get("/cognition"))["control"]["spent"].get("experiment_calls", 0)
                assert after == before, "Noise unexpectedly spent model calls"
                observations = await get("/cognition/observations")
                matches = [o for o in observations if lab["id"] in o["provenance"]["url"]]
                assert matches and all(o["status"] == "IGNORED" for o in matches)
                result = {
                    "scenario": scenario,
                    "model_calls": 0,
                    "decision": "NO ACTION WARRANTED",
                    "observations": len(matches),
                }
            else:
                run = None
                deadline = time.monotonic() + 120
                while time.monotonic() < deadline:
                    runs = await get("/cognition/investigations")
                    matching = [r for r in runs if r["snapshot"].get("environment_id") == lab["id"]]
                    if matching and matching[0]["state"] in (
                        "COMPLETED",
                        "ABSTAINED",
                        "FAILED",
                        "CANCELLED",
                    ):
                        run = await get("/cognition/investigations/" + matching[0]["id"])
                        break
                    await asyncio.sleep(0.4)
                assert run is not None, "No autonomous investigation completed"
                assert run["state"] in ("COMPLETED", "ABSTAINED"), run.get("error")
                assert run["experiences"], "No experience recorded"
                if scenario == "contradiction":
                    assert run["evaluation"]["status"] == "CONTRADICTED", run["evaluation"]
                assert {m["sender"] for m in run["messages"]} >= {
                    "observer",
                    "proposer",
                    "critic",
                    "investigator",
                    "evaluator",
                    "governor",
                }
                assert run["usage"]["calls"] <= run["budget"]["calls"]
                assert all(
                    call["status"] == "validated" and call["provider"] == provider
                    for call in run["invocations"]
                )
                result = {
                    "scenario": scenario,
                    "investigation_id": run["id"],
                    "state": run["state"],
                    "evaluation": run["evaluation"],
                    "usage": run["usage"],
                    "experience_id": run["experiences"][0]["id"],
                    "goal_id": run["goal_id"],
                    "models": sorted({c["model"] for c in run["invocations"]}),
                    "reported_tokens": sum(
                        c["usage"].get("total_tokens", 0) for c in run["invocations"]
                    ),
                    "trace": run,
                }
                for call in run["invocations"]:
                    assert "api_key" not in json.dumps(call["input_json"]).lower()
            await post(path + "/observation", {"approved": False})
            await client.delete(path)
            results.append(result)
            print(
                f"{scenario}: {result.get('state', result.get('decision'))}; "
                f"calls={result.get('usage', {}).get('calls', 0)}",
                flush=True,
            )
        await post("/cognition/control", {"command": "pause"})
        async with async_playwright() as p:
            browser = await p.chromium.launch(channel="chrome", headless=True)
            context = await browser.new_context(viewport={"width": 1440, "height": 1050})
            await context.add_init_script(
                f'sessionStorage.setItem("alive-token",{json.dumps(token)})'
            )
            page = await context.new_page()
            await page.goto("http://127.0.0.1:5173")
            await page.get_by_role("button", name="Cognition", exact=True).click()
            await expect(page.get_by_role("heading", name="Cognitive control")).to_be_visible()
            await page.get_by_label("Investigation", exact=True).select_option(
                results[-1]["investigation_id"]
            )
            await expect(page.get_by_role("heading", name="Structured exchanges")).to_be_visible()
            await page.evaluate("window.scrollTo(0,0)")
            await page.screenshot(path=".alive/first-thought.png", full_page=True)
            await browser.close()
        spent = (await get("/cognition"))["control"]["spent"]
        await asyncio.to_thread(restart)
        assert (await get("/alive"))["identity"]["id"] == identity
        assert (await get("/cognition"))["control"]["spent"] == spent
        for result in results:
            if "investigation_id" in result:
                recovered = await get("/cognition/investigations/" + result["investigation_id"])
                assert recovered["experiences"][0]["id"] == result["experience_id"]
                assert recovered["goal_id"] == result["goal_id"]
        evidence = {
            "demonstration": "The First Autonomous Thought",
            "provider": provider,
            "identity": identity,
            "restart_continuity": True,
            "persistent_budget": spent,
            "results": results,
            "dollar_cost": None,
            "dollar_cost_note": "API reports token usage; no configured price/billing data",
            "cognitive_logic": "model roles plus deterministic attention, "
            "evidence evaluation and Governor",
        }
        Path(".alive/first-thought.json").write_text(json.dumps(evidence, indent=2))
        print("Identity, investigations, goals, experience and budget continuity: PASS", flush=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--provider", choices=["mock", "meta"], default="mock")
    args = parser.parse_args()
    try:
        httpx.get("http://127.0.0.1:8000/api/v1/health", timeout=1)
    except httpx.HTTPError:
        pass
    else:
        raise SystemExit("Stop the existing backend/dashboard before this owned restart demo.")
    subprocess.run([sys.executable, "-m", "alembic", "upgrade", "head"], check=True)
    Path(".alive").mkdir(exist_ok=True)
    log = Path(".alive/first-thought-backend.log").open("w", encoding="utf-8")
    backend = dashboard = None

    def launch():
        process = subprocess.Popen(
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
        return process

    def restart():
        nonlocal backend
        backend.terminate()
        backend.wait(timeout=15)
        backend = launch()

    try:
        backend = launch()
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
        asyncio.run(demonstrate(args.provider, restart))
    finally:
        for process in [backend, dashboard]:
            if process and process.poll() is None:
                process.terminate()
                process.wait(timeout=15)
        log.close()


if __name__ == "__main__":
    main()
