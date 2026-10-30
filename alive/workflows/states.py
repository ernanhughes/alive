"""Monotonic state machines for workflow runs and stage runs (ALIVE-PI-02A).

Defined now so PI-02B's executor and every reader share one vocabulary. UNKNOWN is terminal and is
never resumed automatically: it means an effect may have happened and its outcome is not known
(for a Pi stage: ambiguous provider dispatch). Only a human decision or a fresh run can follow it.
"""

PENDING = "PENDING"
RUNNING = "RUNNING"
WAITING_APPROVAL = "WAITING_APPROVAL"
COMPLETED = "COMPLETED"
FAILED = "FAILED"
SKIPPED = "SKIPPED"  # stages only: an explicitly optional, side-effect-free stage was skipped
CANCELLED = "CANCELLED"  # cancelled with no effect in flight
UNKNOWN = "UNKNOWN"  # an effect may have happened; outcome not known

RUN_STATES = (PENDING, RUNNING, WAITING_APPROVAL, COMPLETED, FAILED, CANCELLED, UNKNOWN)
RUN_TERMINAL = frozenset({COMPLETED, FAILED, CANCELLED, UNKNOWN})
RUN_TRANSITIONS = {
    PENDING: {RUNNING, FAILED, CANCELLED},
    RUNNING: {WAITING_APPROVAL, COMPLETED, FAILED, CANCELLED, UNKNOWN},
    WAITING_APPROVAL: {RUNNING, FAILED, CANCELLED},
}

STAGE_STATES = (PENDING, RUNNING, WAITING_APPROVAL, COMPLETED, FAILED, SKIPPED, CANCELLED, UNKNOWN)
STAGE_TERMINAL = frozenset({COMPLETED, FAILED, SKIPPED, CANCELLED, UNKNOWN})
STAGE_TRANSITIONS = {
    PENDING: {RUNNING, SKIPPED, FAILED, CANCELLED},
    RUNNING: {WAITING_APPROVAL, COMPLETED, FAILED, CANCELLED, UNKNOWN},
    WAITING_APPROVAL: {RUNNING, FAILED, CANCELLED},
}

DEFINITION_STATUSES = ("draft", "active", "superseded", "archived")
DEFINITION_TRANSITIONS = {
    "draft": {"active", "archived"},
    "active": {"superseded", "archived"},
    "superseded": {"archived"},
}
VALIDATION_STATUSES = ("not_run", "passed", "failed")
UNCERTAINTY = ("none", "ambiguous_dispatch", "unknown_outcome")


class IllegalTransition(ValueError):
    pass


def advance(current, new, table):
    """Return `new` if `current -> new` is allowed. Terminal states have no outgoing edges."""
    if new not in table.get(current, ()):
        raise IllegalTransition(f"{current} -> {new} is not allowed")
    return new
