"""PiGateway: a ModelGateway that runs one model operation through a governed Pi child (PI-01B).

Path: Cognition -> ModelGateway -> PiGateway -> PiRunner -> Pi -> ALIVE egress -> existing
DirectMetaGateway -> provider. The caller's contract is unchanged: it hands in a StructuredRequest
under an existing Governor reservation and gets a `Generation` or a typed `ProviderError`.

This module never touches a provider credential or constructs a provider client; the only upstream
dispatch is the egress's, through the existing DirectMetaGateway.
"""

import asyncio
import contextlib
import hashlib
import secrets
import time

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
        k = runtime.kernel
        run_id, token = uid(), secrets.token_urlsafe(32)
        token_sha = hashlib.sha256(token.encode()).hexdigest()
        started = time.monotonic()

        # 1. PREPARED: persist the approved identity. One run per reservation, ever.
        try:
            async with k.lock, k.db.sessions.begin() as session:
                reservation = await session.get(ModelInvocation, req.correlation)
                if reservation is None or reservation.status != "reserved":
                    raise ProviderError("pi_no_reservation")
                session.add(
                    PiRun(
                        id=run_id,
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
                        token_sha256=token_sha,
                        max_provider_requests=self.settings.alive_pi_max_provider_requests,
                    )
                )
                self._event(k, session, "pi.run.prepared", run_id, {"reservation": req.correlation})
        except IntegrityError:
            # This reservation already has a run. It is never dispatched twice.
            raise ProviderError("ambiguous_settlement") from None

        ctx = None
        try:
            # 2. Verify the pinned Pi. A mismatch is refused before anything starts.
            try:
                install = runtime.runner.install()
            except PiRunFailure as failure:
                await self._finish(k, run_id, states.FAILED, failure.category, {})
                raise ProviderError(failure.category) from None
            await self._update(
                k,
                run_id,
                state=states.ADMITTED,
                event="pi.run.admitted",
                pi_version=install.version,
                pi_bundle_sha256=install.bundle_sha256,
                flags_sha256=flags_identity(req.max_output),
            )
            await runtime.ensure_egress()
            ctx = RunContext(
                run_id,
                token_sha,
                req,
                gateway_for_run(self.settings, req.operation, runtime.upstream_transport),
                self.settings.alive_pi_max_provider_requests,
            )
            runtime.egress.register(token, ctx)
            await self._update(k, run_id, state=states.STARTING, event="pi.run.starting")

            async def on_running():
                await self._update(k, run_id, state=states.RUNNING, event="pi.run.started")

            async def on_event(event):
                async with k.lock, k.db.sessions.begin() as session:
                    self._event(k, session, "pi.rpc.event", run_id, {"event": event})

            # 3. Run Pi. The runner kills the whole process tree before any cancel propagates.
            partial = PiResult()
            try:
                result = await runtime.runner.run(
                    result=partial,
                    prompt=render_prompt(req),
                    base_url=runtime.egress.base_url,
                    token=token,
                    max_tokens=req.max_output,
                    deadline=self.settings.alive_pi_run_deadline,
                    on_event=on_event,
                    on_running=on_running,
                    install=install,
                )
            except asyncio.CancelledError:
                runtime.egress.unregister(token)
                await shielded(self._conclude(k, run_id, ctx, partial, started, cancelled=True))
                raise
            except Exception as exc:  # noqa: BLE001 - a spawn failure is a typed, recorded failure
                result = _Failed(PiRunFailure("pi_spawn_failed", type(exc).__name__))
            runtime.egress.unregister(token)
            return await shielded(self._conclude(k, run_id, ctx, result, started, cancelled=False))
        finally:
            if ctx is not None:
                runtime.egress.unregister(token)

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

    async def _update(self, k, run_id, *, state, event, **fields):
        async with k.lock, k.db.sessions.begin() as session:
            run = await session.get(PiRun, run_id)
            run.state = states.advance(run.state, state, states.RUN_TRANSITIONS)
            for name, value in fields.items():
                setattr(run, name, value)
            run.updated_at = now()
            self._event(k, session, event, run_id, {})

    async def _finish(self, k, run_id, new_state, reason, receipt):
        async with k.lock, k.db.sessions.begin() as session:
            run = await session.get(PiRun, run_id)
            if run.state in states.RUN_TERMINAL:
                return
            run.state = states.advance(run.state, new_state, states.RUN_TRANSITIONS)
            run.terminal_reason, run.result_json = reason, receipt
            run.finished_at = run.updated_at = now()
            self._event(k, session, f"pi.run.{new_state.lower()}", run_id, {"reason": reason})

    async def _conclude(self, k, run_id, ctx, result, started, *, cancelled):
        """Settle the run from what was DURABLY recorded, and say no more than was demonstrated."""
        with contextlib.suppress(TimeoutError):
            await asyncio.wait_for(ctx.idle.wait(), SETTLE_WAIT_SECONDS)
        async with k.lock, k.db.sessions.begin() as session:
            requests = (
                await session.scalars(
                    select(PiProviderRequest)
                    .where(PiProviderRequest.run_id == run_id)
                    .order_by(PiProviderRequest.seq)
                )
            ).all()
            for request in requests:  # still dispatched after the wait: the outcome is unknown
                if request.state == states.R_DISPATCHED:
                    request.state = states.R_AMBIGUOUS
                    request.error_category = request.error_category or "unsettled"
                    request.updated_at = now()
            settled = [r for r in requests if r.state == states.R_SETTLED]
            ambiguous = [r for r in requests if r.state == states.R_AMBIGUOUS]
            failed = [r for r in requests if r.state == states.R_FAILED]
        failure = result.failure if result is not None else None
        text = result.text if result is not None else None
        consistent = text is not None and ctx.last_text_sha256 == sha256_text(text)
        receipt = {
            "duration_s": round(time.monotonic() - started, 3),
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
            "text_sha256": sha256_text(text) if text is not None else None,
            "matches_egress_record": consistent,
            "requests": {
                "settled": len(settled),
                "failed": len(failed),
                "ambiguous": len(ambiguous),
                "total": len(requests),
            },
        }

        def usage_of(request):
            return (request.usage_json or None) if request is not None else None

        if cancelled:
            state, reason = (
                (states.UNKNOWN, "cancelled_after_possible_dispatch")
                if ambiguous
                else (
                    states.CANCELLED,
                    "cancelled_after_dispatch_settled" if requests else "cancelled_before_dispatch",
                )
            )
            await self._finish(k, run_id, state, reason, receipt)
            return None
        error = None
        if ambiguous:
            await self._finish(k, run_id, states.UNKNOWN, "ambiguous_provider_request", receipt)
            error = ProviderError(ambiguous[0].error_category or "ambiguous_settlement")
        elif failed:
            first = failed[0]
            await self._finish(
                k, run_id, states.FAILED, f"provider_{first.error_category}", receipt
            )
            error = ProviderError(
                first.error_category,
                first.http_status,
                usage=usage_of(first),
                response_received=first.http_status is not None,
            )
        elif failure is not None:
            await self._finish(k, run_id, states.FAILED, failure.category, receipt)
            error = ProviderError(failure.category)
        else:
            problem = None
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
            if problem is not None:
                await self._finish(k, run_id, states.FAILED, problem, receipt)
                spent = settled[0] if settled else None
                error = ProviderError(
                    problem if problem != "pi_output_mismatch" else "invalid_response",
                    usage=usage_of(spent),
                    response_received=spent is not None,
                )
            else:
                await self._finish(k, run_id, states.SETTLED, "settled", receipt)
                request = settled[0]
                return Generation(text, request.usage_json or {}, request.latency_ms or 0)
        raise error


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
