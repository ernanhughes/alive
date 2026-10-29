"""Authenticated, read-only receipts for Pi runs (ALIVE-PI-01B). No execution or cancel endpoint.

Nothing here discloses a credential, a run token, or prompt text: free text in retained events was
already hashed, and the approved request is shown only as hashes.
"""

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select

from alive.models import Event
from alive.pi import states
from alive.pi.models import PiProviderRequest, PiRun
from alive.pi.runner import MODEL_ID, PROVIDER_ID

COST_NOTE = (
    "ALIVE has no price table for this transport. Cost is unknown, not zero; Pi's own cost "
    "figure for an unpriced custom model is zero and is deliberately not used."
)


def _request(row):
    return {
        "seq": row.seq,
        "state": row.state,
        "body_sha256_in": row.body_sha256_in,
        "approved_request_sha256": row.approved_request_sha256,
        "model_requested": row.model_requested,
        "http_status": row.http_status,
        "usage": row.usage_json,  # null = unknown, never 0
        "cost_usd": None,
        "latency_ms": row.latency_ms,
        "error_category": row.error_category,
        "response_sha256": row.response_sha256,
    }


def receipt(run, requests):
    facts = run.result_json or {}
    observed = (facts.get("pi_observed_provider"), facts.get("pi_observed_model"))
    expected = (PROVIDER_ID, MODEL_ID)
    counts = {
        state: sum(1 for r in requests if r.state == state)
        for state in (
            states.R_SETTLED,
            states.R_FAILED,
            states.R_AMBIGUOUS,
            states.R_REJECTED,
            states.R_DISPATCHED,
            states.R_ADMITTED,
        )
    }
    return {
        "run_id": run.id,
        "operation": run.operation,
        "reservation_ref": run.reservation_ref,
        "state": run.state,
        "terminal": run.state in states.RUN_TERMINAL,
        "terminal_reason": run.terminal_reason,
        "created_at": run.created_at.isoformat(),
        "finished_at": run.finished_at.isoformat() if run.finished_at else None,
        "pi": {
            "version": run.pi_version,
            "bundle_sha256": run.pi_bundle_sha256,
            "flags_sha256": run.flags_sha256,
        },
        "identity": {
            "requested_upstream_model": (run.requested_json or {}).get("upstream_model"),
            "pi_observed": {"provider": observed[0], "model": observed[1]},
            "pi_expected_alias": {"provider": expected[0], "model": expected[1]},
            "matches_expected_alias": observed == expected,
            "note": "The upstream model is chosen by ALIVE; Pi only ever sees its local alias.",
        },
        "approved_request_sha256": run.approved_request_sha256,
        "approved_request": run.approved_request_json,
        "requests": {
            "ceiling": run.max_provider_requests,
            "inbound": run.inbound_requests,
            "admitted": run.provider_requests,
            "counts": counts,
            "items": [_request(r) for r in requests],
        },
        "settlement": {
            "cleanup_confirmed": facts.get("cleanup_confirmed"),
            "pi_settled": facts.get("pi_settled"),
            "matches_egress_record": facts.get("matches_egress_record"),
            "tool_events": facts.get("tool_events"),
            "malformed_frames": facts.get("malformed_frames"),
            "duration_s": facts.get("duration_s"),
            "recovered": run.terminal_reason in ("restart", "restart_after_possible_dispatch"),
        },
        "cost": {"usd": None, "note": COST_NOTE},
    }


def router(app, ready):
    api = APIRouter(prefix="/api/v1/pi", dependencies=[Depends(ready)])

    async def load(session, run_id):
        run = await session.get(PiRun, run_id)
        if run is None or run.instance_id != app.state.kernel.instance_id:
            raise HTTPException(404, "Unknown Pi run")
        return run

    @api.get("/runs")
    async def runs(limit: int = Query(20, ge=1, le=100)):
        async with app.state.kernel.db.sessions() as session:
            rows = (
                await session.scalars(
                    select(PiRun)
                    .where(PiRun.instance_id == app.state.kernel.instance_id)
                    .order_by(PiRun.created_at.desc())
                    .limit(limit)
                )
            ).all()
            return [
                {
                    "run_id": r.id,
                    "operation": r.operation,
                    "state": r.state,
                    "terminal_reason": r.terminal_reason,
                    "created_at": r.created_at.isoformat(),
                }
                for r in rows
            ]

    @api.get("/runs/{run_id}")
    async def run_receipt(run_id: str):
        async with app.state.kernel.db.sessions() as session:
            run = await load(session, run_id)
            requests = (
                await session.scalars(
                    select(PiProviderRequest)
                    .where(PiProviderRequest.run_id == run.id)
                    .order_by(PiProviderRequest.seq)
                )
            ).all()
            return receipt(run, requests)

    @api.get("/runs/{run_id}/events")
    async def run_events(run_id: str, limit: int = Query(500, ge=1, le=2000)):
        async with app.state.kernel.db.sessions() as session:
            run = await load(session, run_id)
            rows = (
                await session.scalars(
                    select(Event)
                    .where(Event.source == "pi", Event.correlation_id == run.id)
                    .order_by(Event.sequence_number)
                    .limit(limit)
                )
            ).all()
            return [
                {
                    "sequence_number": e.sequence_number,
                    "event_type": e.event_type,
                    "occurred_at": e.occurred_at.isoformat(),
                    "payload": e.payload,
                }
                for e in rows
            ]

    return api
