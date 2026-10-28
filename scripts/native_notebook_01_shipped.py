"""Native load smoke with byte-identical shipped extension; no toolbar qualification.

CDP can load Chrome's unpacked extension but cannot reliably grant activeTab through
an authentic toolbar click. This test deliberately does not substitute authorization.
See docs/ALIVE-NOTEBOOK-01-R1-REPORT.md for the manual acceptance procedure.
"""

import asyncio
import hashlib
import json
import shutil
import subprocess
import uuid
from pathlib import Path

from playwright.async_api import async_playwright

from scripts.native_notebook_01 import URLS, start_hugo, wait_url

ROOT = Path(__file__).resolve().parents[1]
EVIDENCE = ROOT / "docs/validation/alive-notebook-01-r1/shipped-smoke"


async def main():
    EVIDENCE.mkdir(parents=True, exist_ok=True)
    work = ROOT / ".alive" / ("notebook-shipped-" + uuid.uuid4().hex)
    extension = work / "extension"
    shutil.copytree(ROOT / "extension", extension)
    hashes = {}
    for source in sorted((ROOT / "extension").rglob("*")):
        if source.is_file():
            relative = source.relative_to(ROOT / "extension")
            assert (extension / relative).read_bytes() == source.read_bytes()
            hashes[relative.as_posix()] = hashlib.sha256(source.read_bytes()).hexdigest()
    report = {
        "commit": subprocess.check_output(["git", "rev-parse", "HEAD"], text=True).strip(),
        "extension_sha256": hashes,
        "substitutions": [],
        "backend_started": False,
        "external_model_calls": 0,
        "paid_inference_spend_usd": 0,
        "shipped_toolbar_activeTab_capture_rejection_revocation": "NOT QUALIFIED",
        "reason": "No reliable authentic toolbar interaction in the CDP harness. "
        "No Extensions.triggerAction or synthetic activeTab grant attempted.",
        "manual_procedure": "docs/ALIVE-NOTEBOOK-01-R1-REPORT.md",
    }
    hugo, log = start_hugo(work / "hugo.log")
    try:
        await wait_url(URLS["alive-12-status"])
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
                await page.goto(URLS["alive-12-status"])
                assert await page.locator("main h1").count() == 1
                ui = await context.new_page()
                await ui.goto(f"chrome-extension://{extension_id}/panel.html")
                report["runtime"] = await ui.evaluate("""async () => ({
                    manifest: chrome.runtime.getManifest(),
                    permissions: await chrome.permissions.getAll(),
                    config: await import('./config.js').then(m => ({
                        backend: m.DEFAULT_BACKEND, backends: m.DEFAULT_BACKENDS,
                        pages: m.AUTHORISED_PAGES,
                        notebookIsDemo: m.isLocalDemo(
                            'http://127.0.0.1:1313/chapters/alive-12-status/')
                    }))
                })""")
                shipped = json.loads((extension / "manifest.json").read_text())
                assert report["runtime"]["manifest"] == shipped
                assert report["runtime"]["config"]["notebookIsDemo"] is False
                assert not any("1313" in p for p in report["runtime"]["permissions"]["origins"])
                report["load_smoke"] = "PASS"
                await page.screenshot(path=str(EVIDENCE / "chapter.png"))
            finally:
                await context.close()
    except BaseException as error:
        report["load_smoke"] = "FAIL"
        report["error"] = type(error).__name__ + ": " + str(error)
        raise
    finally:
        hugo.terminate()
        try:
            hugo.wait(timeout=10)
        except subprocess.TimeoutExpired:
            hugo.kill()
            hugo.wait(timeout=10)
        log.close()
        (EVIDENCE / "result.json").write_text(json.dumps(report, indent=2) + "\n")
        print(json.dumps(report, indent=2))


if __name__ == "__main__":
    asyncio.run(main())
