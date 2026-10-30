"""Process-wide Pi runtime: the runner, the lazily started egress, and restart recovery.

Recovery rule (never negotiable): after a restart a request that was `dispatched` but not settled is
`ambiguous` and is NEVER replayed, and its run is `UNKNOWN`. Nothing is re-dispatched; the existing
Governor reservation (the `ModelInvocation`) keeps its conservative charge.
"""

from sqlalchemy import or_, select

from alive.models import now
from alive.pi import states
from alive.pi.egress import PiEgress
from alive.pi.models import PiProviderRequest, PiRun
from alive.pi.runner import PiRunner

_current = None


def current_runtime():
    return _current


def set_runtime(runtime):
    global _current
    _current = runtime


class PiRuntime:
    def __init__(self, kernel, settings, *, runner=None, upstream_transport=None):
        self.kernel, self.settings = kernel, settings
        self.runner = runner or PiRunner(settings)
        # Test seam only: an httpx transport for the UPSTREAM provider call. None in production.
        self.upstream_transport = upstream_transport
        self.egress = PiEgress(kernel, upstream_transport)

    async def initialize(self):
        await recover(self.kernel)

    async def ensure_egress(self):
        """Start the loopback egress on first use. No listener exists unless Pi is actually used."""
        if self.egress.port is None:
            await self.egress.start()

    async def close(self):
        await self.egress.stop()


async def recover(kernel):
    """Settle every Pi run (and request) a previous process left unfinished. Never re-dispatches.

    A request that was `dispatched` OR is already `ambiguous` may have reached the provider, so its
    run is UNKNOWN, never CANCELLED. A request still `admitted` never reached the provider and is
    rejected. Pending requests are repaired even under a run that is already terminal.
    """
    async with kernel.lock, kernel.db.sessions.begin() as session:
        pending = select(PiProviderRequest.run_id).where(
            PiProviderRequest.state.in_((states.R_ADMITTED, states.R_DISPATCHED))
        )
        runs = (
            await session.scalars(
                select(PiRun).where(
                    or_(PiRun.state.notin_(states.RUN_TERMINAL), PiRun.id.in_(pending))
                )
            )
        ).all()
        for run in runs:
            requests = (
                await session.scalars(
                    select(PiProviderRequest).where(PiProviderRequest.run_id == run.id)
                )
            ).all()
            repaired = False
            for request in requests:
                if request.state == states.R_DISPATCHED:
                    request.state, request.error_category = states.R_AMBIGUOUS, "restart"
                    request.updated_at, repaired = now(), True
                elif request.state == states.R_ADMITTED:
                    request.state, request.error_category = (
                        states.R_REJECTED,
                        "restart_before_dispatch",
                    )
                    request.updated_at, repaired = now(), True
            possibly_sent = any(r.state == states.R_AMBIGUOUS for r in requests)
            if run.state in states.RUN_TERMINAL:
                if repaired:  # the run's own terminal state stands; only the rows were stale
                    kernel.add_event(
                        session,
                        "pi.run.repaired",
                        {"run_id": run.id, "state": run.state},
                        source="pi",
                        correlation=run.id,
                    )
                continue
            if possibly_sent:
                new, reason = states.UNKNOWN, "restart_after_possible_dispatch"
            elif any(r.state in (states.R_SETTLED, states.R_FAILED) for r in requests):
                new, reason = states.CANCELLED, "restart_after_dispatch_resolved"
            else:
                new, reason = states.CANCELLED, "restart"
            try:
                run.state = states.advance(run.state, new, states.RUN_TRANSITIONS)
            except states.IllegalTransition:
                if new != states.UNKNOWN:
                    raise
                run.state = states.UNKNOWN  # record the truth even from an inconsistent state
            run.terminal_reason, run.finished_at, run.updated_at = reason, now(), now()
            kernel.add_event(
                session,
                f"pi.run.{new.lower()}",
                {"run_id": run.id, "reason": reason},
                source="pi",
                correlation=run.id,
            )
