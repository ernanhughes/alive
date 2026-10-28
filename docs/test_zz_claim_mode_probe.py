"""Reviewer probe: claim mode end-to-end on main 767596c (+ minimal syntax repairs). Throwaway."""
import json
from types import SimpleNamespace

from fastapi.testclient import TestClient
from sqlalchemy import select

from alive.app import create_app
from alive.models import Base
from tests.conftest import TOKEN
from tests.test_research_memory import ROOT, goal, grant, post, snapshot, wait, analyse, fake_model

PY = "https://docs.python.org/3/tutorial/"
MDN = "https://developer.mozilla.org/en-US/docs/Web/JavaScript/Guide"
BEH = "Return the current UTC date and time, with tzinfo None."
HIST = "Intro text here. " + BEH + " This is like now(), but naive."
DEP = "Deprecated since version 3.12: Use datetime.now() with UTC instead."
CUR = "Intro text here. " + BEH + " This is like now(), but naive. " + DEP
MARK = "tzinfo None"


def setup(client, monkeypatch):
    async def structured(*args, **kwargs):
        data = args[2] if len(args) > 2 else kwargs.get("data") or {}
        excerpt = data.get("untrusted_excerpt", HIST)
        return SimpleNamespace(text=json.dumps({"summary": "Controlled note.", "evidence_quote": excerpt[:60],
                               "limitations": "Controlled excerpt only."}),
                               usage={"prompt_tokens": 10, "completion_tokens": 10, "total_tokens": 20})
    monkeypatch.setattr("alive.web_experience.MetaProvider.structured", structured)
    s = client.app.state.kernel.settings
    s.alive_relationship_allow_test_providers = True
    g = goal(client)
    hg = grant(client, g["id"], PY)
    hs = snapshot(client, hg, PY, HIST)
    note = wait(client, post(client, "/analyse", {"snapshot_id": hs["snapshot"]["id"],
        "reviewed_sha256": hs["snapshot"]["data"]["sha256"], "send_to_meta": True, "owner_correction": True})["id"])
    saved = post(client, "/research/memories", {"note_id": note["id"]})
    a = client.post(ROOT + f"/research/memories/{saved['id']}/anchor", json={
        "quote": BEH, "expected_sha256": saved["data"]["sha256"], "expected_revision": 0})
    print("\nanchor:", a.status_code, a.text[:160] if a.status_code != 200 else "ok")
    cg = grant(client, g["id"], MDN)
    cs = snapshot(client, cg, MDN, CUR)
    return g, saved, cs, cg


def fixture_for(rel):
    return {"relationship": rel, "claim_aspect": "status",
            "historical_claim_quote": BEH, "current_claim_quote": DEP,
            "scope_alignment": "same", "scope_note": "Same method, 3.11 vs 3.12 docs",
            "supersession_basis_quote": DEP, "reason": "Newer page adds a deprecation note.",
            "limitations": "Status change only.", "confidence": 0.5}


def run_claim(client, saved, cs, monkeypatch, calls):
    async def meta(*a, **k):
        calls.append(k.get("model"))
        raise RuntimeError("meta reached")
    monkeypatch.setattr("alive.research_relationships.MetaProvider.structured", meta)
    rel = client.app.state.relationships
    pv = client.post(ROOT + "/research/outbound/preview", json={
        "snapshot_id": cs["snapshot"]["id"], "research_id": saved["id"],
        "provider": "local_fixture_claim", "analysis_mode": "claim_comparison"})
    print("preview:", pv.status_code, pv.text[:200] if pv.status_code != 200 else "ok")
    if pv.status_code != 200:
        return None
    p = pv.json()
    rel._claim_fixture_map = {(p["preview"]["current_sha256"], p["preview"]["historical_sha256"]):
                              fixture_for("explicit_supersession")}
    post(client, "/research/outbound/authorize", {"consent_id": p["id"], "payload_sha256": p["payload_sha256"], "approved": True})
    r = client.post(ROOT + "/research/relationships", json={"consent_id": p["id"]})
    out = r.json()
    print("analyze:", r.status_code, "attempt:", out.get("analysis", {}).get("status"),
          "error:", out.get("analysis", {}).get("data", {}).get("error"),
          "| connection:", (out.get("connection") or {}).get("status"),
          "| meta calls:", calls)
    return out


def test_probe_1_fixture_provider_reaches_meta(client, monkeypatch):
    g, saved, cs, _ = setup(client, monkeypatch)
    calls = []
    run_claim(client, saved, cs, monkeypatch, calls)
    print("PROBE_1 fixture provider dispatched to MetaProvider:", bool(calls), calls)


def test_probe_2_meta_gate(client, monkeypatch):
    g, saved, cs, _ = setup(client, monkeypatch)
    client.app.state.kernel.settings.alive_research_meta_enabled = True
    pv = client.post(ROOT + "/research/outbound/preview", json={
        "snapshot_id": cs["snapshot"]["id"], "research_id": saved["id"],
        "provider": "meta", "analysis_mode": "claim_comparison"})
    print("\nPROBE_2 claim+meta with research meta on, claim meta off ->", pv.status_code)


def test_probe_3_e2e_with_fixture_branch(client, settings, monkeypatch):
    """Patch a fixture branch into analyze() to test the rest of the lifecycle."""
    rel = client.app.state.relationships
    import alive.research_relationships as rr
    orig = rr.MetaProvider.structured

    async def as_fixture(self_, instructions, payload, schema, **k):
        out = rel._local_fixture_claim(payload)
        return SimpleNamespace(text=out.model_dump_json(),
                               usage={"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0})
    g, saved, cs, cg = setup(client, monkeypatch)
    calls = []
    out = None
    monkeypatch.setattr("alive.research_relationships.MetaProvider.structured", as_fixture)
    pv = post(client, "/research/outbound/preview", {
        "snapshot_id": cs["snapshot"]["id"], "research_id": saved["id"],
        "provider": "local_fixture_claim", "analysis_mode": "claim_comparison"})
    print("\npreview payload keys:", sorted(pv["preview"]), "| reliance:", pv["preview"].get("reliance", {}).get("revision"),
          "| schema is claim:", "claim_aspect" in json.dumps(pv["request"]["schema"]))
    rel._claim_fixture_map = {(pv["preview"]["current_sha256"], pv["preview"]["historical_sha256"]):
                              fixture_for("explicit_supersession")}
    post(client, "/research/outbound/authorize", {"consent_id": pv["id"], "payload_sha256": pv["payload_sha256"], "approved": True})
    out = post(client, "/research/relationships", {"consent_id": pv["id"]})
    conn = out.get("connection") or {}
    print("PROBE_3 attempt:", out["analysis"]["status"], "| candidate:", conn.get("status"),
          "| relation:", conn.get("data", {}).get("relation_type"),
          "| retained:", conn.get("data", {}).get("historical_quote_retained_in_current"),
          "| validation:", conn.get("data", {}).get("validation", {}).get("decision"))
    listed = client.get(ROOT + f"/research/relationships?goal_id={g['id']}").json()["connections"]
    print("PROBE_3 listed claim candidates:", [c["data"].get("relation_type") for c in listed])

    # Re-anchor (same quote, new revision) must invalidate the candidate
    re = client.post(ROOT + f"/research/memories/{saved['id']}/anchor", json={
        "quote": BEH, "expected_sha256": saved["data"]["sha256"], "expected_revision": 1})
    listed = client.get(ROOT + f"/research/relationships?goal_id={g['id']}").json()["connections"]
    print("PROBE_3 re-anchor:", re.status_code, "| candidates after re-anchor:", len(listed))

    # Fresh run at revision 2, then withdraw and scan for withdrawn text in derived rows
    pv2 = post(client, "/research/outbound/preview", {
        "snapshot_id": cs["snapshot"]["id"], "research_id": saved["id"],
        "provider": "local_fixture_claim", "analysis_mode": "claim_comparison"})
    post(client, "/research/outbound/authorize", {"consent_id": pv2["id"], "payload_sha256": pv2["payload_sha256"], "approved": True})
    out2 = post(client, "/research/relationships", {"consent_id": pv2["id"]})
    print("PROBE_3 rerun candidate:", (out2.get("connection") or {}).get("status"))
    post(client, f"/research/memories/{saved['id']}/withdraw", {})

    async def scan():
        hits = []
        async with client.app.state.kernel.db.sessions() as s:
            for table in Base.metadata.sorted_tables:
                for row in (await s.execute(select(table))).mappings():
                    blob = json.dumps({k: str(v) for k, v in row.items()})
                    if MARK in blob:
                        hits.append((table.name, row.get("kind"), row.get("status")))
        return hits
    print("PROBE_3 rows holding withdrawn text:", client.portal.call(scan))
    listing = client.get(ROOT + f"/research/relationships?goal_id={g['id']}").text
    print("PROBE_3 relationships listing contains withdrawn text:", MARK in listing)
    client.__exit__(None, None, None)
    with TestClient(create_app(settings), headers={"Authorization": f"Bearer {TOKEN}"}) as c2:
        l2 = c2.get(ROOT + f"/research/relationships?goal_id={g['id']}").json()["connections"]
        print("PROBE_3 after restart active candidates:", len(l2))


def test_probe_4_which_field_leaks(client, monkeypatch):
    rel = client.app.state.relationships
    async def as_fixture(self_, instructions, payload, schema, **k):
        out = rel._local_fixture_claim(payload)
        return SimpleNamespace(text=out.model_dump_json(), usage={"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0})
    g, saved, cs, cg = setup(client, monkeypatch)
    monkeypatch.setattr("alive.research_relationships.MetaProvider.structured", as_fixture)
    pv = post(client, "/research/outbound/preview", {"snapshot_id": cs["snapshot"]["id"], "research_id": saved["id"],
              "provider": "local_fixture_claim", "analysis_mode": "claim_comparison"})
    rel._claim_fixture_map = {(pv["preview"]["current_sha256"], pv["preview"]["historical_sha256"]): fixture_for("explicit_supersession")}
    post(client, "/research/outbound/authorize", {"consent_id": pv["id"], "payload_sha256": pv["payload_sha256"], "approved": True})
    post(client, "/research/relationships", {"consent_id": pv["id"]})
    post(client, f"/research/memories/{saved['id']}/withdraw", {})
    from alive.web_models import WebExperience
    async def leaks():
        async with client.app.state.kernel.db.sessions() as s:
            rows = (await s.scalars(select(WebExperience).where(WebExperience.kind == "research_connection"))).all()
            return [(r.status, [k for k, v in r.data.items() if MARK in json.dumps(v)]) for r in rows]
    print("\nPROBE_4 invalidated connection keys holding withdrawn text:", client.portal.call(leaks))
