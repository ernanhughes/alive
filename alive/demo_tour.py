"""ALIVE-DEMO-INTEGRATION-01: a one-click, offline walk through the evidence lifecycle.

The tour is a *client of ALIVE's own public API*. It calls the real browser-experience
endpoints in-process with the caller's own credentials, so every grant, snapshot, saved
memory, anchor, consent, comparison and withdrawal is an ordinary backend row that passes
the ordinary guards. It adds no privilege and has no code path to a paid provider: the only
comparison provider it can name is the deterministic local fixture, which the runtime also
refuses unless the owner enabled it. Matching pinned bytes establish a source's identity,
never that its statements are true, and a fixture result is not live model reasoning.
"""

import hashlib
import json
import uuid
from pathlib import Path

import httpx
from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, ConfigDict
from sqlalchemy import select

from alive.demo_live_01 import DIRECTORY, manifest
from alive.models import Event, now, record
from alive.web_models import WebExperience

RUN_KIND = "demo_tour_run"
ROOT = "/api/v1/browser-experience"
IDENTITY_HOST = "http://127.0.0.1:8000/demo-live-01/"
PROVIDER = "local_fixture_claim"
FIXTURE_LABEL = "DETERMINISTIC LOCAL FIXTURE — NOT LIVE META"
BEHAVIOR = "Return the current UTC date and time, with tzinfo None."
ORIGINAL, LATER, NEUTRAL = "python-3.11", "python-3.12", "synthetic-no-change"
SOURCES = (ORIGINAL, LATER, NEUTRAL)
CONSENT_TEXT = (
    "Starting the demonstration authorises ONE local fixture comparison per later source, of "
    "exactly the two pinned sources shown. Nothing leaves this machine, no model is called, "
    "and no provider credential is used."
)
LABELS = {
    "backend_row": "Persisted by ALIVE's public API",
    "pinned_source": "Pinned local mirror (identity by bytes, not truth)",
    "fixture_provider": FIXTURE_LABEL,
    "ordinary_read": "Ordinary active read",
    "audit_read": "Separate audit read (retained originals, no source text)",
}


class RunRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    pause_before_withdrawal: bool = False


class StepFailed(Exception):
    def __init__(self, key, message):
        super().__init__(message)
        self.key, self.message = key, message


def enabled(settings):
    return bool(
        settings.alive_demo_tour_enabled and settings.alive_relationship_allow_test_providers
    )


def disabled_reason(settings):
    if not settings.alive_demo_tour_enabled:
        return "The demonstration is disabled (ALIVE_DEMO_TOUR_ENABLED is off)."
    if not settings.alive_relationship_allow_test_providers:
        return "Local fixture providers are disabled on this runtime."
    return ""


def load_captures():
    """Read and verify every pinned capture before any row is written (fail closed)."""
    sources = {item["id"]: item for item in manifest()["sources"]}
    captures = {}
    for name in SOURCES:
        path = Path(DIRECTORY) / (name + ".capture.json")
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, ValueError) as exc:
            raise ValueError(f"Pinned demonstration source '{name}' is unavailable") from exc
        pinned = sources.get(name, {}).get("captured_text_sha256")
        if not pinned or hashlib.sha256(data.get("text", "").encode()).hexdigest() != pinned:
            raise ValueError(
                f"Pinned demonstration source '{name}' does not match its recorded hash"
            )
        captures[name] = data
    return captures


def source_summary():
    out = []
    for item in manifest()["sources"]:
        out.append(
            {
                "id": item["id"],
                "kind": item["kind"],
                "mirror_path": "/demo-live-01/" + item["file"],
                "identity_url": IDENTITY_HOST + item["file"],
                "canonical_url": item.get("canonical_url"),
                "mirror_html_sha256": item["mirror_html_sha256"],
                "captured_text_sha256": item["captured_text_sha256"],
                "verification": item.get("verification"),
            }
        )
    return out


def _sha(text):
    return hashlib.sha256(text.encode()).hexdigest()


class TourRun:
    def __init__(self, app, auth, number, pause):
        self.app, self.auth, self.number, self.pause = app, auth, number, pause
        self.run_id = uuid.uuid4().hex
        self.steps, self.ids = [], {"consents": [], "analyses": []}
        self.client = None

    # -- persistence of the run log (itself an ordinary row) ---------------------------------
    async def _save(self, **changes):
        web = self.app.state.web
        async with web.k.lock, web.k.db.sessions.begin() as s:
            row = await s.get(WebExperience, self.run_id)
            row.data = row.data | {"steps": self.steps, "ids": self.ids} | changes
            if "status" in changes:
                row.status = changes["status"]

    async def _create(self):
        web = self.app.state.web
        async with web.k.lock, web.k.db.sessions.begin() as s:
            web.add(
                s,
                RUN_KIND,
                {
                    "number": self.number,
                    "provider": PROVIDER,
                    "label": FIXTURE_LABEL,
                    "consent_text": CONSENT_TEXT,
                    "pause_before_withdrawal": self.pause,
                    "started_at": now().isoformat(),
                    "steps": [],
                    "ids": self.ids,
                },
                None,
                "running",
                row_id=self.run_id,
            )

    async def step(self, key, title, summary, provenance, evidence):
        self.steps.append(
            {
                "n": len(self.steps) + 1,
                "key": key,
                "title": title,
                "summary": summary,
                "status": "ok",
                "at": now().isoformat(),
                "provenance": provenance,
                "evidence": evidence,
            }
        )
        await self._save()

    # -- calls to the real public API --------------------------------------------------------
    async def call(self, key, method, path, body=None, params=None):
        response = await self.client.request(method, ROOT + path, json=body, params=params)
        if response.status_code >= 400:
            try:
                message = response.json()["error"]["message"]
            except (ValueError, KeyError, TypeError):
                message = "HTTP " + str(response.status_code)
            raise StepFailed(key, f"{method} {path} refused ({response.status_code}): {message}")
        return response.json()

    async def observe(self, key, goal_id, name, captures):
        url = IDENTITY_HOST + name + ".html"
        data = captures[name]
        grant = await self.call(
            key,
            "POST",
            "/grants",
            {"goal_id": goal_id, "url": url, "tab_key": "demo-tour-" + name, "approved": True},
        )
        snapshot = (
            await self.call(
                key,
                "POST",
                "/snapshots",
                {
                    "grant_id": grant["id"],
                    "url": url,
                    "title": name,
                    **data,
                    "reviewed_sha256": _sha(data["text"]),
                },
            )
        )["snapshot"]
        return url, grant, snapshot

    async def compare(self, key, snapshot, memory):
        request = {
            "snapshot_id": snapshot["id"],
            "research_id": memory["id"],
            "analysis_mode": "claim_comparison",
            "provider": PROVIDER,
        }
        consent = await self.call(key, "POST", "/research/outbound/preview", request)
        identity = consent.get("provider") or {}
        if identity.get("id") != PROVIDER or identity.get("external") is not False:
            raise StepFailed(key, "Refusing a comparison that is not the local fixture provider")
        payload = consent["preview"]
        bound = {
            "goal_id": snapshot["data"]["goal_id"],
            "current_url": snapshot["data"]["url"],
            "current_sha256": snapshot["data"]["sha256"],
            "historical_memory_id": memory["id"],
        }
        if any(payload.get(field) != value for field, value in bound.items()):
            raise StepFailed(key, "The consent preview is not bound to this exact source pair")
        self.ids["consents"].append(consent["id"])
        await self.step(
            key + "_consent",
            "Show the exact payload and record demo-scoped consent",
            "The owner-visible preview names the exact pair; the Start click authorises it.",
            ["backend_row", "fixture_provider"],
            {
                "consent_id": consent["id"],
                "payload_sha256": consent["payload_sha256"],
                "provider": identity,
                "external": consent.get("external"),
                "bound_pair": bound,
                "scope": CONSENT_TEXT,
            },
        )
        await self.call(
            key,
            "POST",
            "/research/outbound/authorize",
            {
                "consent_id": consent["id"],
                "payload_sha256": consent["payload_sha256"],
                "approved": True,
            },
        )
        result = await self.call(
            key, "POST", "/research/relationships", {"consent_id": consent["id"]}
        )
        analysis = result["analysis"]
        if analysis["status"] != "validated":
            raise StepFailed(key, "The comparison was not validated; nothing is shown as a finding")
        self.ids["analyses"].append(analysis["id"])
        data = analysis["data"]
        if result.get("connection"):
            if result["connection"]["data"].get("historical_memory_id") != memory["id"]:
                raise StepFailed(key, "The finding is not bound to the saved memory")
        elif any(data.get(field) != value for field, value in bound.items()):
            raise StepFailed(key, "The abstention is not bound to this exact source pair")
        return consent, result, bound

    async def ordinary(self, goal_id, memory_id, snapshot_id):
        memories = (
            await self.call("read", "GET", "/research/memories", params={"goal_id": goal_id})
        )["memories"]
        listed = await self.call(
            "read", "GET", "/research/relationships", params={"goal_id": goal_id}
        )
        retrieved = await self.call(
            "read", "POST", "/research/retrieve", {"snapshot_id": snapshot_id, "top_k": 3}
        )
        return {
            "memory_active": memory_id in {m["id"] for m in memories},
            "active_memory_ids": [m["id"] for m in memories],
            "connection_ids": [c["id"] for c in listed["connections"]],
            "analysis_ids": [a["id"] for a in listed["analyses"]],
            "retrieval_memory_ids": [r["memory_id"] for r in retrieved["results"]],
            "retrieval_abstained": retrieved["abstained"],
        }

    # -- the journey -------------------------------------------------------------------------
    async def run(self, captures):
        self.client = httpx.AsyncClient(
            transport=httpx.ASGITransport(app=self.app),
            base_url="http://alive.internal",
            headers={"Authorization": self.auth},
            timeout=60,
        )
        await self._create()
        try:
            async with self.client:
                await self._journey(captures)
        except (StepFailed, PermissionError, ValueError, KeyError) as exc:
            key = getattr(exc, "key", "run")
            message = getattr(exc, "message", None) or str(exc)
            self.steps.append(
                {
                    "n": len(self.steps) + 1,
                    "key": key,
                    "title": "Stopped (fail closed)",
                    "summary": message,
                    "status": "failed",
                    "at": now().isoformat(),
                    "provenance": [],
                    "evidence": {},
                }
            )
            await self._save(status="failed", error=message, finished_at=now().isoformat())

    async def _journey(self, captures):
        goal = await self.call(
            "observe_original",
            "POST",
            "/goals",
            {
                "instruction": f"Demonstration {self.number}: did the standing of "
                "datetime.utcnow change?"
            },
        )
        url, grant, snap = await self.observe("observe_original", goal["id"], ORIGINAL, captures)
        await self._save(goal_id=goal["id"])
        await self.step(
            "observe_original",
            "Observe the original source",
            "A reviewed, read-only snapshot of the pinned Python 3.11 mirror was recorded.",
            ["pinned_source", "backend_row"],
            {
                "goal_id": goal["id"],
                "grant_id": grant["id"],
                "snapshot_id": snap["id"],
                "url": url,
                "text_sha256": snap["data"]["sha256"],
                "mirror_path": "/demo-live-01/python-3.11.html",
            },
        )

        memory = await self.call(
            "save_memory", "POST", "/research/memories", {"snapshot_id": snap["id"]}
        )
        identity = memory["data"].get("source_identity") or {}
        if identity.get("id") != ORIGINAL:
            raise StepFailed(
                "save_memory", "The source identity was not verified against pinned bytes"
            )
        self.ids["memory"] = memory["id"]
        await self._save()
        await self.step(
            "save_memory",
            "Remember the source as research memory",
            "Identity matched the pinned bytes. That proves which document this is, "
            "not that it is true.",
            ["backend_row", "pinned_source"],
            {
                "memory_id": memory["id"],
                "sha256": memory["data"]["sha256"],
                "source_identity": identity,
                "model_note_created": memory["data"].get("note_id") is not None,
            },
        )

        excerpt = memory["data"]["excerpt"]
        if BEHAVIOR not in excerpt:
            raise StepFailed("anchor", "The statement to anchor is not in the saved excerpt")
        start = excerpt.index(BEHAVIOR)
        await self.call(
            "anchor",
            "POST",
            f"/research/memories/{memory['id']}/anchor",
            {
                "quote": BEHAVIOR,
                "expected_sha256": memory["data"]["sha256"],
                "expected_revision": 0,
                "occurrence_start": start,
            },
        )
        await self.step(
            "anchor",
            "Anchor the statement being relied on",
            "ALIVE will watch whether later evidence changes this exact sentence's standing.",
            ["backend_row"],
            {"quote": BEHAVIOR, "start": start, "end": start + len(BEHAVIOR), "revision": 1},
        )

        later_url, later_grant, later = await self.observe(
            "observe_later", goal["id"], LATER, captures
        )
        await self.step(
            "observe_later",
            "Observe a later source",
            "A reviewed snapshot of the pinned Python 3.12 mirror was recorded under "
            "the same goal.",
            ["pinned_source", "backend_row"],
            {
                "grant_id": later_grant["id"],
                "snapshot_id": later["id"],
                "url": later_url,
                "text_sha256": later["data"]["sha256"],
                "mirror_path": "/demo-live-01/python-3.12.html",
            },
        )

        consent, result, bound = await self.compare("compare", later, memory)
        connection = result.get("connection")
        if not connection:
            raise StepFailed(
                "compare", "The fixture comparison found no change; the demo cannot continue"
            )
        cdata = connection["data"]
        self.ids["connection"] = connection["id"]
        await self._save()
        await self.step(
            "compare",
            "Compare the anchored statement with the later source",
            "The standing changed while the described behaviour is still "
            "present: not a contradiction.",
            ["fixture_provider", "backend_row"],
            {
                "analysis_id": result["analysis"]["id"],
                "connection_id": connection["id"],
                "connection_status": connection["status"],
                "relation_type": cdata.get("relation_type"),
                "claim_aspect": cdata.get("claim_aspect"),
                "historical_quote": cdata.get("historical_quote"),
                "current_quote": cdata.get("current_quote"),
                "supersession_basis_quote": cdata.get("supersession_basis_quote"),
                "historical_quote_retained_in_current": cdata.get(
                    "historical_quote_retained_in_current"
                ),
                "explanation": cdata.get("explanation"),
                "limitations": cdata.get("limitations"),
                "bound_pair": bound,
                "is_candidate_not_truth": True,
            },
        )

        neutral_url, neutral_grant, neutral = await self.observe(
            "abstention", goal["id"], NEUTRAL, captures
        )
        n_consent, n_result, n_bound = await self.compare("abstention", neutral, memory)
        if n_result.get("connection") is not None or not n_result.get("abstained"):
            raise StepFailed("abstention", "The no-change source unexpectedly produced a finding")
        validation = n_result["analysis"]["data"].get("validation", {})
        await self.step(
            "abstention",
            "Decline to infer when evidence is insufficient",
            "A second later source says nothing about the anchored statement, so ALIVE abstains.",
            ["fixture_provider", "backend_row", "pinned_source"],
            {
                "snapshot_id": neutral["id"],
                "url": neutral_url,
                "text_sha256": neutral["data"]["sha256"],
                "analysis_id": n_result["analysis"]["id"],
                "relationship": validation.get("relationship"),
                "abstained": True,
                "connection": None,
                "charged_tokens": n_result["analysis"]["data"].get("charged_tokens"),
                "bound_pair": n_bound,
            },
        )

        before = await self.ordinary(goal["id"], memory["id"], later["id"])
        if not (
            before["memory_active"]
            and connection["id"] in before["connection_ids"]
            and result["analysis"]["id"] in before["analysis_ids"]
        ):
            raise StepFailed("before_withdrawal", "The finding is not visible before withdrawal")
        await self.step(
            "before_withdrawal",
            "Show what an ordinary read returns before withdrawal",
            "The memory, the finding and the abstention are all active.",
            ["ordinary_read"],
            before,
        )
        await self._save(retrieval_snapshot_id=later["id"], memory_id=memory["id"])
        if self.pause:
            await self._save(status="paused", paused_at=now().isoformat())
            return
        await self._withdraw_steps(goal["id"], memory["id"], later["id"], connection["id"])

    async def _withdraw_steps(self, goal_id, memory_id, snapshot_id, connection_id):
        withdrawn = await self.call(
            "withdraw", "POST", f"/research/memories/{memory_id}/withdraw", {}
        )
        await self.step(
            "withdraw",
            "Withdraw the original memory",
            "One call retires the memory and invalidates its dependent consent, "
            "comparisons and finding.",
            ["backend_row"],
            {
                "memory_id": memory_id,
                "status": withdrawn.get("status"),
                "idempotent": withdrawn.get("idempotent", False),
            },
        )
        after = await self.ordinary(goal_id, memory_id, snapshot_id)
        if (
            after["memory_active"]
            or after["connection_ids"]
            or after["analysis_ids"]
            or memory_id in after["retrieval_memory_ids"]
        ):
            raise StepFailed(
                "after_withdrawal",
                "A retired source or its finding is still returned by an ordinary read",
            )
        await self.step(
            "after_withdrawal",
            "Show what an ordinary read returns after withdrawal",
            "The memory, the finding and the abstention no longer appear, and retrieval cannot "
            "surface the source.",
            ["ordinary_read"],
            after,
        )
        audit = await audit_view(self.app, self.ids)
        await self.step(
            "audit",
            "Separate audit view",
            "Originals are retained for audit as rows with a retired status. They are hidden "
            "from ordinary reads, "
            "not erased, and no source text is shown here.",
            ["audit_read"],
            audit,
        )
        await self._save(status="completed", finished_at=now().isoformat())

    async def finish_paused(self, goal_id, memory_id, snapshot_id, connection_id, client):
        self.client = client
        await self._withdraw_steps(goal_id, memory_id, snapshot_id, connection_id)


async def audit_view(app, ids):
    """Rows and events retained for audit. Statuses and ids only: never source text."""
    wanted = [("memory", ids.get("memory"))]
    wanted += [("consent", i) for i in ids.get("consents", [])]
    wanted += [("analysis", i) for i in ids.get("analyses", [])]
    wanted += [("connection", ids.get("connection"))]
    kernel = app.state.kernel
    async with kernel.db.sessions() as s:
        rows = []
        for label, row_id in wanted:
            row = await s.get(WebExperience, row_id) if row_id else None
            if row is not None and row.instance_id == kernel.instance_id:
                rows.append({"label": label, "id": row.id, "kind": row.kind, "status": row.status})
        events = (
            await s.scalars(
                select(Event)
                .where(
                    Event.instance_id == kernel.instance_id,
                    Event.event_type == "research.memory_withdrawn",
                )
                .order_by(Event.sequence_number.desc())
                .limit(500)
            )
        ).all()
        withdrawn = [
            {
                "sequence_number": e.sequence_number,
                "event_id": e.id,
                "occurred_at": e.occurred_at.isoformat(),
            }
            for e in events
            if e.payload.get("research_memory_id") == ids.get("memory")
        ]
    return {"rows": rows, "withdrawal_events": withdrawn, "physically_deleted": False}


def router(app, ready):
    api = APIRouter(prefix="/api/v1/demo-tour", dependencies=[Depends(ready)])
    boot = {"id": uuid.uuid4().hex[:12], "started_at": now().isoformat()}
    running = {"lock": False}

    def summary(row):
        data = row.data
        return {
            "run_id": row.id,
            "number": data.get("number"),
            "status": row.status,
            "goal_id": data.get("goal_id"),
            "started_at": data.get("started_at"),
            "finished_at": data.get("finished_at"),
            "steps": len(data.get("steps", [])),
        }

    async def runs():
        web = app.state.web
        async with web.k.db.sessions() as s:
            return list(await web.rows(s, RUN_KIND))

    @api.get("")
    async def info():
        settings = app.state.kernel.settings
        return {
            "enabled": enabled(settings),
            "reason": disabled_reason(settings),
            "label": FIXTURE_LABEL,
            "labels": LABELS,
            "provider": {"id": PROVIDER, "external": False},
            "consent_text": CONSENT_TEXT,
            "sources": source_summary(),
            "boot": boot,
            "runs": [summary(r) for r in reversed(await runs())],
        }

    @api.post("/runs")
    async def start(request: Request, data: RunRequest):
        settings = app.state.kernel.settings
        if not enabled(settings):
            raise PermissionError(disabled_reason(settings))
        if running["lock"]:
            raise ValueError("A demonstration is already running")
        captures = load_captures()
        running["lock"] = True
        try:
            number = len(await runs()) + 1
            tour = TourRun(
                app, request.headers.get("authorization", ""), number, data.pause_before_withdrawal
            )
            await tour.run(captures)
        finally:
            running["lock"] = False
        return await state(request, tour.run_id)

    async def load_run(run_id):
        web = app.state.web
        async with web.k.db.sessions() as s:
            return record(await web.get(s, run_id, RUN_KIND))

    @api.get("/runs/{run_id}")
    async def state(request: Request, run_id: str):
        row = await load_run(run_id)
        data = row["data"]
        ids = data.get("ids", {})
        live = None
        if data.get("goal_id") and ids.get("memory") and data.get("retrieval_snapshot_id"):
            probe = TourRun(app, request.headers.get("authorization", ""), 0, False)
            probe.client = httpx.AsyncClient(
                transport=httpx.ASGITransport(app=app),
                base_url="http://alive.internal",
                headers={"Authorization": probe.auth},
                timeout=60,
            )
            async with probe.client:
                live = await probe.ordinary(
                    data["goal_id"], ids["memory"], data["retrieval_snapshot_id"]
                )
        return {
            "run_id": row["id"],
            "status": row["status"],
            "number": data.get("number"),
            "provider": data.get("provider"),
            "label": data.get("label"),
            "consent_text": data.get("consent_text"),
            "goal_id": data.get("goal_id"),
            "started_at": data.get("started_at"),
            "finished_at": data.get("finished_at"),
            "error": data.get("error"),
            "steps": data.get("steps", []),
            "live": live,
            "audit": await audit_view(app, ids) if ids.get("memory") else None,
            "boot": boot,
        }

    @api.post("/runs/{run_id}/withdraw")
    async def withdraw(request: Request, run_id: str):
        settings = app.state.kernel.settings
        if not enabled(settings):
            raise PermissionError(disabled_reason(settings))
        row = await load_run(run_id)
        data = row["data"]
        if row["status"] == "completed":
            return await state(request, run_id)
        if row["status"] != "paused":
            raise ValueError("This demonstration run is not waiting for withdrawal")
        if running["lock"]:
            raise ValueError("A demonstration is already running")
        running["lock"] = True
        try:
            tour = TourRun(app, request.headers.get("authorization", ""), data["number"], False)
            tour.run_id, tour.steps, tour.ids = run_id, data["steps"], data["ids"]
            client = httpx.AsyncClient(
                transport=httpx.ASGITransport(app=app),
                base_url="http://alive.internal",
                headers={"Authorization": tour.auth},
                timeout=60,
            )
            try:
                async with client:
                    await tour.finish_paused(
                        data["goal_id"],
                        data["ids"]["memory"],
                        data["retrieval_snapshot_id"],
                        data["ids"]["connection"],
                        client,
                    )
            except (StepFailed, PermissionError, ValueError, KeyError) as exc:
                message = getattr(exc, "message", None) or str(exc)
                tour.steps.append(
                    {
                        "n": len(tour.steps) + 1,
                        "key": getattr(exc, "key", "withdraw"),
                        "title": "Stopped (fail closed)",
                        "summary": message,
                        "status": "failed",
                        "at": now().isoformat(),
                        "provenance": [],
                        "evidence": {},
                    }
                )
                await tour._save(status="failed", error=message, finished_at=now().isoformat())
        finally:
            running["lock"] = False
        return await state(request, run_id)

    return api


__all__ = ["router", "enabled", "load_captures", "FIXTURE_LABEL", "PROVIDER", "HTTPException"]
