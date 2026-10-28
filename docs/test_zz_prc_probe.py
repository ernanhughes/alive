"""PR-C review probes against main 65fc0f0. Throwaway; reviewer's local clone only."""

import asyncio
import json
from types import SimpleNamespace

from sqlalchemy import select

from alive.models import Base
from alive.research_relationships import ATTEMPT_KIND
from alive.web_models import WebExperience
from tests.test_research_memory import MDN, MDN_TEXT, ROOT, grant, historical, post, snapshot

MARK = "cycle collector"  # distinctive substring of the withdrawn historical source (PY_TEXT)


def _out(payload):
    return SimpleNamespace(
        text=json.dumps({
            "relationship": "possible_disagreement",
            "explanation": "Probe hypothesis.",
            "current_quote": payload["current_excerpt"],
            "historical_quote": payload["historical_excerpt"],
            "limitations": "Probe fixture.",
            "confidence": 0.4,
        }),
        usage={"prompt_tokens": 10, "completion_tokens": 10, "total_tokens": 20},
    )


def _authorised(client, monkeypatch, provider="meta"):
    g, _, py_shot, py_note, saved = historical(client, monkeypatch)
    mdn_grant = grant(client, g["id"], MDN)
    current = snapshot(client, mdn_grant, MDN, MDN_TEXT)
    client.app.state.kernel.settings.alive_research_meta_enabled = True
    preview = post(client, "/research/outbound/preview", {
        "snapshot_id": current["snapshot"]["id"], "research_id": saved["id"], "provider": provider})
    post(client, "/research/outbound/authorize", {
        "consent_id": preview["id"], "payload_sha256": preview["payload_sha256"], "approved": True})
    return g, py_shot, py_note, saved, mdn_grant, current, preview


def test_probe_C_real_midflight_crash_is_charged(client, monkeypatch):
    *_, preview = _authorised(client, monkeypatch)

    async def scenario():
        started = asyncio.Event()

        async def hang(*a, **k):
            started.set()
            await asyncio.Event().wait()

        monkeypatch.setattr("alive.research_relationships.MetaProvider.structured", hang)
        task = asyncio.create_task(client.app.state.relationships.analyze(preview["id"]))
        await started.wait()
        async with client.app.state.kernel.db.sessions() as s:
            row = (await s.scalars(select(WebExperience).where(WebExperience.kind == ATTEMPT_KIND))).one()
            mid = row.data.get("dispatch_status")
        await client.app.state.relationships.initialize()  # what a restart would do
        async with client.app.state.kernel.db.sessions() as s:
            row = (await s.scalars(select(WebExperience).where(WebExperience.kind == ATTEMPT_KIND))).one()
            after = (row.status, row.data.get("charged_tokens"), row.data.get("reserved_tokens"))
        task.cancel()
        return mid, after

    mid, after = client.portal.call(scenario)
    print("\nPROBE_C_REAL mid-flight dispatch_status:", mid, "| after restart recovery:", after)


def test_probe_E_egress_after_revocation_window(client, monkeypatch):
    *_, mdn_grant, _, preview = _authorised(client, monkeypatch)
    rel = client.app.state.relationships
    calls = []

    async def scenario():
        gate, in_guard = asyncio.Event(), asyncio.Event()
        original_ledger = rel._ledger

        async def held_ledger(session, exclude_attempt_id=None):
            if exclude_attempt_id:  # only the dispatch guard passes this
                in_guard.set()
                await gate.wait()
            return await original_ledger(session, exclude_attempt_id=exclude_attempt_id)

        async def record_call(*a, **k):
            async with client.app.state.kernel.db.sessions() as s:
                g = await s.get(WebExperience, mdn_grant["id"])
                calls.append(g.status)
            return _out(a[2])

        monkeypatch.setattr(rel, "_ledger", held_ledger)
        monkeypatch.setattr("alive.research_relationships.MetaProvider.structured", record_call)
        task = asyncio.create_task(rel.analyze(preview["id"]))
        await in_guard.wait()
        revoke = asyncio.create_task(client.app.state.web.revoke(mdn_grant["id"]))
        await asyncio.sleep(0.05)  # revoke is now queued on the kernel lock
        gate.set()
        await revoke
        return await task

    result = client.portal.call(scenario)
    print("\nPROBE_E provider called with grant status:", calls,
          "| attempt:", result["analysis"]["status"],
          "| finding:", (result["connection"] or {}).get("status"))


def test_probe_D_full_database_scan_after_withdrawal(client, monkeypatch):
    g, py_shot, py_note, saved, mdn_grant, current, preview = _authorised(client, monkeypatch)

    async def fast(*a, **k):
        return _out(a[2])

    monkeypatch.setattr("alive.research_relationships.MetaProvider.structured", fast)
    post(client, "/research/relationships", {"consent_id": preview["id"]})
    post(client, "/research/connections",
         {"snapshot_id": current["snapshot"]["id"], "memory_id": saved["id"]})
    post(client, f"/research/memories/{saved['id']}/withdraw", {})

    async def scan():
        hits = []
        async with client.app.state.kernel.db.sessions() as s:
            for table in Base.metadata.sorted_tables:
                for row in (await s.execute(select(table))).mappings():
                    blob = json.dumps({k: str(v) for k, v in row.items()})
                    if MARK in blob:
                        hits.append((table.name, row.get("kind"), row.get("status"),
                                     row.get("id") == saved["id"]))
        return hits

    print("\nPROBE_D stored copies of withdrawn text:")
    for hit in client.portal.call(scan):
        print("   ", hit)

    exposed = {}
    for path in ["/research/relationships", "/research/memories",
                 f"/notes/{py_note['id']}", "", "/research/blind/runs"]:
        r = client.get(ROOT + path)
        exposed[path or "/"] = (r.status_code, MARK in r.text)
    print("PROBE_D API exposure (status, contains withdrawn text):", json.dumps(exposed))


def test_probe_F_paired_analysis_survives_withdrawal(client, monkeypatch):
    g, _, _, _, saved = historical(client, monkeypatch)
    mdn_grant = grant(client, g["id"], MDN)
    current = snapshot(client, mdn_grant, MDN, MDN_TEXT)
    preview = post(client, "/research/outbound/preview", {
        "snapshot_id": current["snapshot"]["id"], "research_id": saved["id"],
        "provider": "local_stub", "analysis_mode": "paired",
        "research_question": "How do the two runtimes reclaim memory?"})
    post(client, "/research/outbound/authorize", {
        "consent_id": preview["id"], "payload_sha256": preview["payload_sha256"], "approved": True})
    result = post(client, "/research/relationships", {"consent_id": preview["id"]})
    print("\nPROBE_F paired result keys:", sorted(result)[:8])
    post(client, f"/research/memories/{saved['id']}/withdraw", {})
    listing = client.get(ROOT + "/research/relationships").json()
    paired = listing.get("paired_analyses", [])
    print("PROBE_F paired rows after withdrawal:",
          [(r["status"], MARK in json.dumps(r)) for r in paired],
          "| listing contains withdrawn text:", MARK in json.dumps(listing))
