"""Process-wide Pi runtime: the runner, the lazily started egress, and restart recovery.

Recovery rule (never negotiable): after a restart a request that was `dispatched` but not settled is
`ambiguous` and is NEVER replayed, and its run is `UNKNOWN`. Nothing is re-dispatched; the existing
Governor reservation (the `ModelInvocation`) keeps its conservative charge.
"""

from sqlalchemy import select

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
    """Settle every non-terminal Pi run left by a previous process. Never re-dispatches."""
    async with kernel.lock, kernel.db.sessions.begin() as session:
        runs = (
            await session.scalars(select(PiRun).where(PiRun.state.notin_(states.RUN_TERMINAL)))
        ).all()
        for run in runs:
            requests = (
                await session.scalars(
                    select(PiProviderRequest).where(PiProviderRequest.run_id == run.id)
                )
            ).all()
            possibly_sent = False
            for request in requests:
                if request.state == states.R_DISPATCHED:
                    request.state, request.error_category = states.R_AMBIGUOUS, "restart"
                    request.updated_at = now()
                    possibly_sent = True
                elif request.state == states.R_ADMITTED:
                    request.state, request.error_category = (
                        states.R_FAILED,
                        "restart_before_dispatch",
                    )
                    request.updated_at = now()
            if possibly_sent and run.state == states.RUNNING:
                new, reason = states.UNKNOWN, "restart_after_possible_dispatch"
            else:
                new, reason = states.CANCELLED, "restart"
            run.state = states.advance(run.state, new, states.RUN_TRANSITIONS)
            run.terminal_reason, run.finished_at, run.updated_at = reason, now(), now()
            kernel.add_event(
                session,
                f"pi.run.{new.lower()}",
                {"run_id": run.id, "reason": reason},
                source="pi",
                correlation=run.id,
            )
