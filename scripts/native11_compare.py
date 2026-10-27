"""Matched controlled-API comparison; synthetic HTTP inference, never Meta utility."""

import asyncio
import functools
import json
import tempfile
import threading
import uuid
from pathlib import Path
from unittest.mock import patch

from fastapi.testclient import TestClient

from alive.app import create_app
from alive.config import Settings
from alive.db import Database
from alive.models import Base
from alive.web_experience import adaptive_recommendation, digest
from scripts.native10 import PageHandler, StubHandler, ThreadingHTTPServer
from scripts.native11_cases import CASES, COMPARISON, GOAL, RATINGS

TOKEN = "controlled-api-" + uuid.uuid4().hex
API = "/api/v1/browser-experience"


def compare_arm(arm, provider, page_url):
    with tempfile.TemporaryDirectory(prefix="alive11-comparison-") as directory:
        settings = Settings(
            _env_file=None,
            alive_api_token=TOKEN,
            alive_meta_api_key="synthetic-only",
            alive_meta_base_url=provider,
            alive_meta_url=provider + "/chat/completions",
            alive_embedding_enabled=False,
            alive_native_test_pages=page_url,
            database_url=f"sqlite+aiosqlite:///{Path(directory).as_posix()}/test.db",
            alive_workspace=Path(directory) / "workspace",
        )

        async def schema():
            db = Database(settings.database_url)
            async with db.engine.begin() as conn:
                await conn.run_sync(Base.metadata.create_all)
            await db.engine.dispose()

        asyncio.run(schema())
        policy = (
            adaptive_recommendation
            if arm == "adaptive"
            else functools.partial(
                adaptive_recommendation,
                minimum_support=1000000,
            )
        )
        rows = []
        with patch("alive.web_experience.adaptive_recommendation", policy):
            with TestClient(
                create_app(settings), headers={"Authorization": "Bearer " + TOKEN}
            ) as c:

                def post(path, body):
                    response = c.post(API + path, json=body)
                    assert response.status_code == 200, response.text
                    return response.json()

                goal = post("/goals", {"instruction": GOAL})
                grant = post(
                    "/grants",
                    {
                        "goal_id": goal["id"],
                        "url": page_url,
                        "tab_key": "controlled-api-context",
                        "approved": True,
                    },
                )
                for index, marker in enumerate(COMPARISON):
                    text, adequate, _ = CASES[marker]
                    shot = post(
                        "/snapshots",
                        {
                            "grant_id": grant["id"],
                            "url": page_url,
                            "title": "Controlled research observation",
                            "text": text,
                            "reviewed_sha256": digest(text),
                        },
                    )
                    action = shot["decision"]["action"]
                    correction = marker == "suppressed-2" or arm == "constant"
                    dispatch = (
                        arm == "constant"
                        or action == "analyse"
                        or (correction and action == "no_action")
                    )
                    note, call = shot["decision"].get("note"), False
                    if dispatch:
                        attempt = post(
                            "/analyse",
                            {
                                "snapshot_id": shot["snapshot"]["id"],
                                "reviewed_sha256": digest(text),
                                "send_to_meta": True,
                                "owner_correction": correction,
                                "allow_uncertain_analysis": correction,
                            },
                        )
                        for _ in range(200):
                            note = c.get(API + "/notes/" + attempt["id"]).json()
                            if note["status"] != "reserved":
                                break
                            import time

                            time.sleep(0.01)
                        assert note["status"] == "validated"
                        call = True
                    if marker in RATINGS and note:
                        post("/feedback", {"note_id": note["id"], "useful": RATINGS[marker]})
                    available = bool(note and note["status"] == "validated")
                    rows.append(
                        {
                            "index": index,
                            "case": marker,
                            "source_sha256": digest(text),
                            "companion_recommendation": action,
                            "controller_action": "analyse" if dispatch else action,
                            "call_made": call,
                            "quote_validated_note_available": available,
                            "predeclared_source_adequate": adequate,
                            "missed_source_adequate_opportunity": adequate and not available,
                            "owner_usefulness_measured": False,
                            "owner_correction_applied": bool(
                                note and note["data"].get("owner_correction")
                            ),
                            "usage": note["data"]["usage"] if call else None,
                            "estimated_usd": note["data"]["estimated_usd"] if call else 0,
                        }
                    )
        return {
            "rows": rows,
            "summary": {
                "calls": sum(r["call_made"] for r in rows),
                "source_adequate_opportunities_met": sum(
                    r["predeclared_source_adequate"] and r["quote_validated_note_available"]
                    for r in rows
                ),
                "missed_source_adequate_opportunities": sum(
                    r["missed_source_adequate_opportunity"] for r in rows
                ),
                "total_tokens": sum(r["usage"]["total_tokens"] for r in rows if r["usage"]),
                "synthetic_model_price_estimate": sum(r["estimated_usd"] for r in rows),
            },
        }


def main():
    pages = ThreadingHTTPServer(("127.0.0.1", 0), PageHandler)
    provider = ThreadingHTTPServer(("127.0.0.1", 0), StubHandler)
    provider.calls = []
    for server in [pages, provider]:
        threading.Thread(target=server.serve_forever, daemon=True).start()
    result = {
        "kind": "controlled API + synthetic HTTP provider",
        "native": False,
        "paid_calls": 0,
        "owner_usefulness_measured": False,
        "arms": {},
        "interpretation": "Source-adequacy fixture labels are not measured user utility. "
        "Do not claim utility superiority from these engineering cases.",
    }
    try:
        for arm in ["adaptive", "frozen_nonadaptive", "constant"]:
            result["arms"][arm] = compare_arm(
                arm,
                f"http://127.0.0.1:{provider.server_port}/v1",
                f"http://127.0.0.1:{pages.server_port}/native10",
            )
        hashes = [[r["source_sha256"] for r in a["rows"]] for a in result["arms"].values()]
        assert hashes[0] == hashes[1] == hashes[2]
        result["actual_synthetic_http_requests"] = len(provider.calls)
        result["status"] = "CONTROLLED_API_COMPARISON_PASS"
    finally:
        pages.shutdown()
        provider.shutdown()
        out = Path(".alive") / f"native11-comparison-{uuid.uuid4().hex[:12]}.json"
        out.parent.mkdir(exist_ok=True)
        out.write_text(json.dumps(result, indent=2), encoding="utf-8")
        print(out)
        for arm, data in result["arms"].items():
            print(arm, data["summary"])


if __name__ == "__main__":
    main()
