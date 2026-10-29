"""Durable records for Pi execution (ALIVE-PI-01B, migration 0007).

Only what trustworthy execution and recovery need. The raw Pi event stream is NOT stored here:
it goes to the existing append-only `events` table (`source="pi"`, `correlation_id=<run id>`).
"""

from datetime import datetime

from sqlalchemy import DateTime, Float, ForeignKey, Index, Integer, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from alive.models import Base, J, now, uid
from alive.pi import states


class PiRun(Base):
    __tablename__ = "pi_runs"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    instance_id: Mapped[str] = mapped_column(ForeignKey("alive_instances.id"), index=True)
    operation: Mapped[str] = mapped_column(String(64), index=True)
    # operation + ":" + the existing Governor reservation (ModelInvocation id). A second run
    # for the same reservation is refused: an invocation is never dispatched twice.
    idempotency_key: Mapped[str] = mapped_column(String(160), unique=True)
    reservation_ref: Mapped[str | None] = mapped_column(String(36))
    state: Mapped[str] = mapped_column(String(16), default=states.PREPARED, index=True)
    approved_request_json: Mapped[dict] = mapped_column(J)
    approved_request_sha256: Mapped[str] = mapped_column(String(64))
    requested_json: Mapped[dict] = mapped_column(J)  # upstream model, output limit, deadline
    pi_version: Mapped[str | None] = mapped_column(String(32))
    pi_bundle_sha256: Mapped[str | None] = mapped_column(String(64))
    flags_sha256: Mapped[str | None] = mapped_column(String(64))
    token_sha256: Mapped[str] = mapped_column(String(64))  # the run token itself is never stored
    max_provider_requests: Mapped[int] = mapped_column(Integer, default=1)
    inbound_requests: Mapped[int] = mapped_column(Integer, default=0)  # every request Pi made
    provider_requests: Mapped[int] = mapped_column(Integer, default=0)  # slots actually admitted
    terminal_reason: Mapped[str | None] = mapped_column(String(120))
    result_json: Mapped[dict] = mapped_column(J, default=dict)  # receipt facts, never raw text
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class PiProviderRequest(Base):
    __tablename__ = "pi_provider_requests"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    run_id: Mapped[str] = mapped_column(ForeignKey("pi_runs.id"), index=True)
    seq: Mapped[int] = mapped_column(Integer)  # 1-based, counts every inbound request
    state: Mapped[str] = mapped_column(String(16), default=states.R_ADMITTED)
    body_sha256_in: Mapped[str | None] = mapped_column(String(64))  # what Pi sent
    approved_request_sha256: Mapped[str | None] = mapped_column(String(64))  # what ALIVE sent on
    model_requested: Mapped[str | None] = mapped_column(String(120))
    model_observed: Mapped[str | None] = mapped_column(String(160))
    http_status: Mapped[int | None] = mapped_column(Integer)
    # NULL means unknown. It is never 0: an unknown usage must not read as "free".
    usage_json: Mapped[dict | None] = mapped_column(J, nullable=True)
    latency_ms: Mapped[float | None] = mapped_column(Float)
    upstream_ref: Mapped[str | None] = mapped_column(String(80))
    error_category: Mapped[str | None] = mapped_column(String(64))
    response_sha256: Mapped[str | None] = mapped_column(String(64))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)
    __table_args__ = (
        UniqueConstraint("run_id", "seq", name="uq_pi_provider_requests_run_seq"),
        Index("ix_pi_provider_requests_run_state", "run_id", "state"),
    )
