"""Monotonic state machines for a Pi run and for each provider request it makes (ALIVE-PI-01B).

A Pi run is ALIVE's record of one governed execution through Pi. A provider request is one
request that Pi's model call asked the ALIVE-owned egress to forward. The two machines are kept
separate because they settle differently: a run can be cancelled while a provider request is
already in flight, and that request's outcome is then genuinely unknown.

`dispatched` is persisted BEFORE the upstream call is made. A request that is still `dispatched`
after a crash is therefore ambiguous and is never replayed.
"""

PREPARED = "PREPARED"  # identity and approved request persisted; nothing admitted yet
ADMITTED = "ADMITTED"  # the existing Governor reservation is held; the run may start
STARTING = "STARTING"  # Pi process is being spawned
RUNNING = "RUNNING"  # Pi is up and the prompt was sent
SETTLED = "SETTLED"  # Pi settled and its output matched the egress's own record
FAILED = "FAILED"  # a known failure; no dispatch is in doubt
CANCELLED = "CANCELLED"  # cancelled with no provider request in flight
UNKNOWN = "UNKNOWN"  # process died or ALIVE restarted after a possible dispatch

RUN_TERMINAL = frozenset({SETTLED, FAILED, CANCELLED, UNKNOWN})
RUN_TRANSITIONS = {
    PREPARED: {ADMITTED, FAILED, CANCELLED},
    ADMITTED: {STARTING, FAILED, CANCELLED},
    STARTING: {RUNNING, FAILED, CANCELLED},
    RUNNING: {SETTLED, FAILED, CANCELLED, UNKNOWN},
}

R_ADMITTED = "admitted"  # a request slot was reserved; not yet sent upstream
R_DISPATCHED = "dispatched"  # persisted before the upstream call; outcome not yet known
R_SETTLED = "settled"  # upstream replied and the reply was recorded
R_FAILED = "failed"  # upstream refused or the reply was invalid; typed category recorded
R_AMBIGUOUS = "ambiguous"  # may have reached upstream; the outcome is not known
R_REJECTED = "rejected"  # refused by ALIVE before any dispatch (limit, state, mismatch)

REQUEST_TERMINAL = frozenset({R_SETTLED, R_FAILED, R_AMBIGUOUS, R_REJECTED})
REQUEST_TRANSITIONS = {
    # A slot that is reconciled before its dispatch marker was written was never sent: rejected.
    R_ADMITTED: {R_DISPATCHED, R_FAILED, R_REJECTED},
    R_DISPATCHED: {R_SETTLED, R_FAILED, R_AMBIGUOUS},
}


class IllegalTransition(ValueError):
    pass


def advance(current, new, table):
    """Return `new` if `current -> new` is allowed; otherwise refuse. Terminal states are final."""
    if new not in table.get(current, ()):
        raise IllegalTransition(f"{current} -> {new} is not allowed")
    return new
