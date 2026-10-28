"""Acquire attributed focused mirrors and capture them with production capture-v2.

Network retrieval is explicit; tests use the resulting pinned offline artifacts.
No model provider is used. Upstream git revision is not inferred from a URL/tag.
"""

import asyncio
import hashlib
import json
from datetime import UTC, datetime
from pathlib import Path

import httpx
from bs4 import BeautifulSoup
from playwright.async_api import async_playwright

ROOT = Path(__file__).resolve().parents[1]
DEST = ROOT / "fixtures/demo_live_01"
SUBJECTS = ["datetime.datetime.utcnow", "datetime.datetime.utcfromtimestamp"]


def digest(data):
    return hashlib.sha256(data if isinstance(data, bytes) else data.encode()).hexdigest()


def document(title, banner, attribution, content):
    return (
        "<!doctype html><html lang='en'><meta charset='utf-8'>"
        f"<title>{title}</title><style>"
        "body{font:16px system-ui;max-width:850px;margin:30px auto;padding:16px}"
        "header{border:2px solid #786321;padding:16px;background:#fff6d6}"
        "dt{font-weight:bold;margin-top:24px}dd{margin-left:20px}p{line-height:1.6}"
        ".versionmodified{font-weight:bold}code{font-family:monospace}</style>"
        f"<header><strong>{banner}</strong><p>{attribution}</p></header>"
        f"<h1>{title}</h1><main>{content}</main></html>"
    )


async def main():
    DEST.mkdir(parents=True, exist_ok=True)
    sources = []
    with httpx.Client(follow_redirects=True, timeout=60) as client:
        for version in ("3.11", "3.12"):
            url = f"https://docs.python.org/{version}/library/datetime.html"
            response = client.get(url)
            response.raise_for_status()
            raw = response.content
            (DEST / f"upstream-{version}.html").write_bytes(raw)
            soup = BeautifulSoup(raw, "html.parser")
            title = soup.title.get_text()
            entries = []
            for subject in SUBJECTS:
                entry = soup.find(id=subject).parent
                for link in entry.select(".headerlink"):
                    link.decompose()
                entries.append(str(entry))
            name = f"python-{version}.html"
            attribution = (
                f"Focused local mirror of two entries from <a href='{url}'>{title}</a>. "
                "Other entries are omitted. Copyright © Python Software Foundation. "
                f"<a href='https://docs.python.org/{version}/license.html'>"
                "PSF License Version 2</a>. "
                "Captured text is evidence of this pinned mirror, not verified factual truth."
            )
            mirror = document(
                title, "LOCAL MIRROR — PYTHON DOCUMENTATION", attribution, "".join(entries)
            )
            (DEST / name).write_bytes(mirror.encode())
            license_response = client.get(f"https://docs.python.org/{version}/license.html")
            license_response.raise_for_status()
            (DEST / f"license-{version}.html").write_bytes(license_response.content)
            sources.append(
                {
                    "id": f"python-{version}",
                    "file": name,
                    "kind": "local_mirror",
                    "canonical_url": str(response.url),
                    "documentation_build": title,
                    "retrieved_at": datetime.now(UTC).isoformat(),
                    "upstream_revision": None,
                    "upstream_revision_status": "not_independently_established",
                    "source_html_file": f"upstream-{version}.html",
                    "source_html_sha256": digest(raw),
                    "mirror_html_sha256": digest(mirror),
                    "capture_format_version": 2,
                    "license": "PSF License Version 2; documentation code examples also 0BSD",
                    "license_url": f"https://docs.python.org/{version}/license.html",
                    "attribution": "Copyright © Python Software Foundation; All Rights Reserved",
                    "last_modified_header": response.headers.get("last-modified"),
                }
            )
    synthetic = document(
        "Synthetic newer research — no deprecation evidence",
        "SYNTHETIC TEST FIXTURE — NOT PYTHON DOCUMENTATION",
        "Constructed by ALIVE solely to demonstrate abstention. "
        "No upstream source or model result.",
        '<dl><dt id="datetime.datetime.utcnow">classmethod datetime.utcnow()</dt><dd>'
        "<p>Return the current UTC date and time, with <code>tzinfo</code> <code>None</code>.</p>"
        "<p>This synthetic publication adds no status or recommendation change.</p></dd></dl>",
    )
    (DEST / "synthetic-no-change.html").write_bytes(synthetic.encode())
    sources.append(
        {
            "id": "synthetic-no-change",
            "file": "synthetic-no-change.html",
            "kind": "synthetic",
            "canonical_url": None,
            "documentation_build": None,
            "retrieved_at": None,
            "upstream_revision": None,
            "source_html_sha256": None,
            "mirror_html_sha256": digest(synthetic),
            "capture_format_version": 2,
            "license": "Repository license",
            "attribution": "ALIVE constructed fixture",
        }
    )
    async with async_playwright() as playwright:
        browser = await playwright.chromium.launch(channel="chrome", headless=True)
        page = await browser.new_page()
        for source in sources:
            await page.goto((DEST / source["file"]).as_uri())
            await page.add_script_tag(path=str(ROOT / "extension/capture.js"))
            capture = await page.evaluate("__aliveCaptureV2(document.querySelector('main'))")
            text = capture["text"]
            (DEST / (source["id"] + ".capture.json")).write_text(
                json.dumps(capture, indent=2) + "\n", encoding="utf-8"
            )
            source |= {
                "captured_text_sha256": digest(text),
                "capture_entries": capture["capture_entries"],
                "capture_file": source["id"] + ".capture.json",
                "capture_browser": browser.version,
                "verification": "browser_capture_of_pinned_local_mirror"
                if source["kind"] == "local_mirror"
                else "synthetic_fixture",
            }
            print(
                source["id"], len(text), source["captured_text_sha256"], capture["capture_entries"]
            )
        await browser.close()
    (DEST / "manifest.json").write_text(
        json.dumps({"format": 1, "sources": sources}, indent=2) + "\n", encoding="utf-8"
    )


if __name__ == "__main__":
    asyncio.run(main())
