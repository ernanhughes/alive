"""PiGateway: a ModelGateway that runs one model operation through a governed Pi child (PI-01B).

Path: Cognition -> ModelGateway -> PiGateway -> PiRunner -> Pi -> ALIVE egress -> existing
DirectMetaGateway -> provider. The caller's contract is unchanged: it hands in a StructuredRequest
under an existing Governor reservation and gets a `Generation` or a typed `ProviderError`.

This module never touches a provider credential or constructs a provider client; the only upstream
dispatch is the egress's, through the existing DirectMetaGateway.

Lifecycle ownership: from the first durable write until the run is terminal, ONE handler
(`_lifecycle`) owns the run. Any exit from it (error, or cancellation at any await) goes through
`_abandon`, which settles the run from what was durably recorded. A run therefore never stays in
a live state, and a request is never left `admitted` or `dispatched` under a terminal run.
"""

import asyncio
import contextlib
import hashlib
import json
import secrets
import time
from dataclasses import asdict

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError

from alive.cognitive_models import ModelInvocation
from alive.models import now, uid
from alive.pi import states
from alive.pi.egress import RunContext, approved_request_sha256, gateway_for_run, render_prompt
from alive.pi.models import PiProviderRequest, PiRun
from alive.pi.process import shielded
from alive.pi.runner import PiResult, PiRunFailure, flags_identity, sha256_text
from alive.pi.runtime import current_runtime
from alive.providers import Generation, ProviderError

SETTLE_WAIT_SECONDS = 5.0  # how long to let an in-flight egress request settle after Pi is gone
# One Governor reservation pays for ONE provider request. This is a constant, not a setting: a
# configuration that allowed more would spend money the reservation never accounted for.
MAX_PROVIDER_REQUESTS = 1
MAX_RETAINED_EVENTS = 200  # Pi events persisted per run; the rest are counted, not stored
MAX_RETAINED_EVENT_BYTES = 256 * 1024


class _Abort(Exception):
    """An internal, typed reason to end a run as FAILED (never a cancellation)."""

    def __init__(self, category):
        super().__init__(category)
        self.category = category


class _Flight:
    """Everything the lifecycle owner needs to settle a run from any exit."""

    def __init__(self):
        self.run_id = uid()
        self.token = secrets.token_urlsafe(32)
        self.token_sha = hashlib.sha256(self.token.encode()).hexdigest()
        self.started = time.monotonic()
        self.ctx = None
        self.partial = PiResult()
        self.events = self.event_bytes = self.events_dropped = 0


class PiGateway:
    def __init__(self, settings, operation):
        self.settings = settings
        self.operation = operation

    async def structured(self, req):
        if req.operation != self.operation:
            raise ValueError(
                f"Operation mismatch: gateway serves {self.operation!r}, "
                f"request claims {req.operation!r}; refusing dispatch"
            )
        runtime = current_runtime()
        if runtime is None:
            raise ProviderError("pi_runtime_unavailable")
        if not req.correlation:
            raise ProviderError("pi_no_reservation")  # no Governor reservation, no run
        if self.settings.alive_pi_max_provider_requests != MAX_PROVIDER_REQUESTS:
            raise ProviderError("pi_config_invalid")  # refused before anything durable exists
        # The lifecycle runs as its own task so that a cancellation of the caller, delivered at
        # ANY await (including the ones inside the first database write), reaches a single owner
        # that reconciles the run. A repeated cancel cannot interrupt that reconciliation.
        task = asyncio.ensure_future(self._lifecycle(runtime, req, _Flight()))
        cancelled = False
        while not task.done():
            try:
                await asyncio.shield(task)
            except asyncio.CancelledError:
                if not cancelled:
                    task.cancel()
                cancelled = True
            except Exception:  # noqa: BLE001 - re-raised below from the finished task
                break
        if cancelled:  # the caller's cancellation always stands, even if the work finished first
            if not task.cancelled():
                task.exception()  # mark any error as retrieved
            raise asyncio.CancelledError()
        return task.result()

    async def _lifecycle(self, runtime, req, flight):
        k = runtime.kernel
        try:
            await self._prepare(k, req, flight)
            try:
                install = runtime.runner.install()
            except PiRunFailure as failure:
                raise _Abort(failure.category) from None
            await self._update(
                k,
                flight.run_id,
                state=states.ADMITTED,
                event="pi.run.admitted",
                pi_version=install.version,
                pi_bundle_sha256=install.bundle_sha256,
                flags_sha256=flags_identity(req.max_output),
            )
            await runtime.ensure_egress()
            flight.ctx = RunContext(
                flight.run_id,
                flight.token_sha,
                req,
                gateway_for_run(self.settings, req.operation, runtime.upstream_transport),
                MAX_PROVIDER_REQUESTS,
            )
            runtime.egress.register(flight.token, flight.ctx)
            await self._update(k, flight.run_id, state=states.STARTING, event="pi.run.starting")

            async def on_running():
                await self._update(k, flight.run_id, state=states.RUNNING, event="pi.run.started")

            async def on_event(event):
                await self._retain_event(k, flight, event)

            try:
                result = await runtime.runner.run(
                    result=flight.partial,
                    prompt=render_prompt(req),
                    base_url=runtime.egress.base_url,
                    token=flight.token,
                    max_tokens=req.max_output,
                    deadline=self.settings.alive_pi_run_deadline,
                    on_event=on_event,
                    on_running=on_running,
                    install=install,
                )
            except Exception as exc:  # noqa: BLE001 - a spawn failure is a typed, recorded failure
                result = _Failed(PiRunFailure("pi_spawn_failed", type(exc).__name__))
            runtime.egress.unregister(flight.token)
            generation, error = await shielded(self._settle(k, flight, result, cancelled=False))
            if error is not None:
                raise error
            return generation
        except BaseException as exc:
            runtime.egress.unregister(flight.token)
            await shielded(self._abandon(k, flight, exc))
            if isinstance(exc, _Abort):
                raise ProviderError(exc.category) from None
            raise

    # -- persistence ------------------------------------------------------------------------
    @staticmethod
    def _event(k, session, event_type, run_id, payload):
        k.add_event(
            session,
            event_type,
            {"run_id": run_id, **payload},
            source="pi",
            correlation=run_id,
        )

    async def _prepare(self, k, req, flight):
        """PREPARED: persist the approved identity. One run per reservation, ever."""
        try:
            async with k.lock, k.db.sessions.begin() as session:
                reservation = await session.get(ModelInvocation, req.correlation)
                if reservation is None or reservation.status != "reserved":
                    raise ProviderError("pi_no_reservation")
                destination = reservation.input_json.get("model_destination")
                if destination is not None or req.destination is not None:
                    if req.destination is None or asdict(req.destination) != destination:
                        raise ProviderError("destination_mismatch")
                session.add(
                    PiRun(
                        id=flight.run_id,
                        instance_id=k.instance_id,
                        operation=req.operation,
                        idempotency_key=f"{req.operation}:{req.correlation}",
                        reservation_ref=req.correlation,
                        approved_request_json={
                            "operation": req.operation,
                            "model": req.model,
                            "max_output": req.max_output,
                            "schema_sha256": sha256_text(repr(sorted(req.schema.items()))),
                            "payload_sha256": sha256_text(render_prompt(req)),
                        },
                        approved_request_sha256=approved_request_sha256(req),
                        requested_json={
                            "upstream_model": req.model,
                            "max_output": req.max_output,
                            "deadline_s": self.settings.alive_pi_run_deadline,
                        },
                        token_sha256=flight.token_sha,
                        max_provider_requests=MAX_PROVIDER_REQUESTS,
                    )
                )
                self._event(
                    k, session, "pi.run.prepared", flight.run_id, {"reservation": req.correlation}
                )
        except IntegrityError:
            # This reservation already has a run. It is never dispatched twice.
            raise ProviderError("ambiguous_settlement") from None

    async def _update(self, k, run_id, *, state, event, **fields):
        async with k.lock, k.db.sessions.begin() as session:
            run = await session.get(PiRun, run_id)
            run.state = states.advance(run.state, state, states.RUN_TRANSITIONS)
            for name, value in fields.items():
                setattr(run, name, value)
            run.updated_at = now()
            self._event(k, session, event, run_id, {})

    async def _retain_event(self, k, flight, event):
        """Persist Pi's (already redacted) events, with a hard cap so a flood cannot fill the DB."""
        size = len(json.dumps(event, default=str))
        if (
            flight.events >= MAX_RETAINED_EVENTS
            or flight.event_bytes + size > MAX_RETAINED_EVENT_BYTES
        ):
            flight.events_dropped += 1
            return
        flight.events += 1
        flight.event_bytes += size
        async with k.lock, k.db.sessions.begin() as session:
            self._event(k, session, "pi.rpc.event", flight.run_id, {"event": event})

    async def _abandon(self, k, flight, exc):
        """Settle a run that is leaving the lifecycle by error or cancellation. Idempotent."""
        cancelled = isinstance(exc, asyncio.CancelledError)
        if isinstance(exc, _Abort):
            category = exc.category
        elif cancelled or isinstance(exc, ProviderError):
            category = None
        else:
            category = "pi_internal_error"
        await self._settle(k, flight, flight.partial, cancelled=cancelled, abort_category=category)

    async def _settle(self, k, flight, result, *, cancelled, abort_category=None):
        """Settle the run in ONE transaction from what was durably recorded.

        Every request row is reconciled in the same transaction that makes the run terminal, and
        the egress's dispatch fence takes the same lock, so no request can be dispatched after the
        run is terminal and none can be left `admitted` or `dispatched` under it.
        Returns (generation, error); both None when the run was already terminal or never existed.
        """
        ctx = flight.ctx
        if ctx is not None and ctx.inflight:  # let an in-flight upstream call finish if it will
            with contextlib.suppress(TimeoutError):
                await asyncio.wait_for(ctx.idle.wait(), SETTLE_WAIT_SECONDS)
        async with k.lock, k.db.sessions.begin() as session:
            run = await session.get(PiRun, flight.run_id)
            if run is None or run.state in states.RUN_TERMINAL:
                return None, None
            requests = (
                await session.scalars(
                    select(PiProviderRequest)
                    .where(PiProviderRequest.run_id == run.id)
                    .order_by(PiProviderRequest.seq)
                )
            ).all()
            for request in requests:
                if request.state == states.R_DISPATCHED:  # may have been sent: outcome unknown
                    request.state = states.R_AMBIGUOUS
                    request.error_category = request.error_category or "unsettled"
                    request.updated_at = now()
                elif request.state == states.R_ADMITTED:  # never sent
                    request.state = states.R_REJECTED
                    request.error_category = (
                        "cancelled_before_dispatch" if cancelled else ("run_concluded")
                    )
                    request.updated_at = now()
            settled = [r for r in requests if r.state == states.R_SETTLED]
            ambiguous = [r for r in requests if r.state == states.R_AMBIGUOUS]
            failed = [r for r in requests if r.state == states.R_FAILED]
            receipt = self._receipt(flight, result, requests, settled, failed, ambiguous)
            new_state, reason, generation, error = self._decide(
                result, flight, requests, settled, failed, ambiguous, cancelled, abort_category
            )
            try:
                run.state = states.advance(run.state, new_state, states.RUN_TRANSITIONS)
            except states.IllegalTransition:
                if new_state != states.UNKNOWN:
                    raise
                run.state = states.UNKNOWN  # the truth is recorded even where the table is strict
            run.terminal_reason, run.result_json = reason, receipt
            run.finished_at = run.updated_at = now()
            self._event(k, session, f"pi.run.{new_state.lower()}", run.id, {"reason": reason})
        return generation, error

    @staticmethod
    def _receipt(flight, result, requests, settled, failed, ambiguous):
        text = result.text if result is not None else None
        consistent = (
            text is not None
            and flight.ctx is not None
            and flight.ctx.last_text_sha256 == sha256_text(text)
        )
        return {
            "duration_s": round(time.monotonic() - flight.started, 3),
            "cleanup_confirmed": bool(result and result.cleanup_confirmed),
            "pi_settled": bool(result and result.settled),
            "pi_observed_provider": result.observed_provider if result else None,
            "pi_observed_model": result.observed_model if result else None,
            "pi_stop_reason": result.stop_reason if result else None,
            # Pi prices an unpriced custom model at zero: recorded for the receipt, never trusted.
            "pi_reported_usage_untrusted": result.pi_usage if result else None,
            "tool_events": result.tool_events if result else 0,
            "malformed_frames": result.malformed_frames if result else 0,
            "stderr_bytes": result.stderr_bytes if result else 0,
            "stderr_sha256": result.stderr_sha256 if result else None,
            "events_retained": flight.events,
            "events_dropped": flight.events_dropped,
            "text_sha256": sha256_text(text) if text is not None else None,
            "matches_egress_record": consistent,
            "requests": {
                "settled": len(settled),
                "failed": len(failed),
                "ambiguous": len(ambiguous),
                "total": len(requests),
            },
        }

    @staticmethod
    def _decide(result, flight, requests, settled, failed, ambiguous, cancelled, abort_category):
        """(state, reason, generation, error) for a run that is being settled."""

        def usage_of(request):
            return (request.usage_json or None) if request is not None else None

        if cancelled:
            if ambiguous:
                return states.UNKNOWN, "cancelled_after_possible_dispatch", None, None
            if settled:
                return states.CANCELLED, "cancelled_after_dispatch_settled", None, None
            if failed:
                return states.CANCELLED, "cancelled_after_dispatch_failed", None, None
            return states.CANCELLED, "cancelled_before_dispatch", None, None
        if ambiguous:
            error = ProviderError(ambiguous[0].error_category or "ambiguous_settlement")
            return states.UNKNOWN, "ambiguous_provider_request", None, error
        if failed:
            first = failed[0]
            error = ProviderError(
                first.error_category,
                first.http_status,
                usage=usage_of(first),
                response_received=first.http_status is not None,
            )
            return states.FAILED, f"provider_{first.error_category}", None, error
        failure = result.failure if result is not None else None
        problem = abort_category
        if problem is None and failure is not None:
            problem = failure.category
        text = result.text if result is not None else None
        consistent = (
            text is not None
            and flight.ctx is not None
            and flight.ctx.last_text_sha256 == sha256_text(text)
        )
        if problem is None:
            if len(settled) != 1 or len(requests) != 1:
                problem = "pi_unexpected_requests"
            elif not (result.settled and result.accepted):
                problem = "pi_not_settled"
            elif result.tool_events:
                problem = "pi_tool_activity"
            elif result.stop_reason != "stop":
                problem = "pi_model_error"
            elif not consistent:
                problem = "pi_output_mismatch"
            elif not result.cleanup_confirmed:
                problem = "pi_cleanup_unconfirmed"
        if problem is None:
            request = settled[0]
            return (
                states.SETTLED,
                "settled",
                Generation(text, request.usage_json or {}, request.latency_ms or 0),
                None,
            )
        spent = settled[0] if settled else None
        error = ProviderError(
            problem if problem != "pi_output_mismatch" else "invalid_response",
            usage=usage_of(spent),
            response_received=spent is not None,
        )
        return states.FAILED, problem, None, error


class _Failed:
    """A runner result for a failure that happened before Pi could report anything."""

    def __init__(self, failure):
        self.failure = failure
        self.text = None
        self.cleanup_confirmed = False
        self.settled = self.accepted = False
        self.observed_provider = self.observed_model = self.stop_reason = None
        self.pi_usage = self.stderr_sha256 = None
        self.tool_events = self.malformed_frames = self.stderr_bytes = 0
