from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, String, UniqueConstraint, event, inspect
from sqlalchemy.orm import Mapped, mapped_column

from alive.models import Base, J, now, uid
from alive.workflows.models import ImmutableRecord


class Admission(Base):
    __tablename__ = "owner_admissions"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    instance_id: Mapped[str] = mapped_column(ForeignKey("alive_instances.id"), index=True)
    principal: Mapped[str] = mapped_column(String(100))
    idempotency_key: Mapped[str] = mapped_column(String(100))
    request_sha256: Mapped[str] = mapped_column(String(64))
    review_sha256: Mapped[str] = mapped_column(String(64))
    terms: Mapped[dict] = mapped_column(J)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)
    approval_ref: Mapped[str | None] = mapped_column(ForeignKey("events.id"))
    revocation_ref: Mapped[str | None] = mapped_column(ForeignKey("events.id"))
    authorization_ref: Mapped[str | None] = mapped_column(ForeignKey("events.id"))
    run_id: Mapped[str | None] = mapped_column(ForeignKey("workflow_runs.id"))
    __table_args__ = (
        UniqueConstraint(
            "instance_id", "principal", "idempotency_key", name="uq_owner_admission_retry"
        ),
    )


@event.listens_for(Admission, "before_update")
def immutable_terms(_mapper, _connection, row):
    state = inspect(row)
    for name in (
        "id",
        "instance_id",
        "principal",
        "idempotency_key",
        "request_sha256",
        "review_sha256",
        "terms",
        "created_at",
    ):
        if state.attrs[name].history.has_changes():
            raise ImmutableRecord("owner admission terms are immutable")
    for name in ("approval_ref", "revocation_ref", "authorization_ref", "run_id"):
        history = state.attrs[name].history
        if history.has_changes() and history.deleted and history.deleted[0] is not None:
            raise ImmutableRecord("owner admission receipts are one-way")


@event.listens_for(Admission, "before_delete")
def never_delete(*_):
    raise ImmutableRecord("owner admission history is retained")
