"""Immutable history, separate from execution and Intelligence learning records."""

from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, String, UniqueConstraint, event
from sqlalchemy.orm import Mapped, mapped_column

from alive.models import Base, J, now, uid
from alive.workflows.models import ImmutableRecord


class Recommendation(Base):
    __tablename__ = "bespoke_recommendations"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    instance_id: Mapped[str] = mapped_column(ForeignKey("alive_instances.id"), index=True)
    principal: Mapped[str] = mapped_column(String(100))
    goal_id: Mapped[str] = mapped_column(ForeignKey("goals.id"))
    investigation_id: Mapped[str] = mapped_column(ForeignKey("investigations.id"))
    source_ref: Mapped[str] = mapped_column(ForeignKey("events.id"))
    idempotency_key: Mapped[str] = mapped_column(String(100))
    request_sha256: Mapped[str] = mapped_column(String(64))
    selection_sha256: Mapped[str] = mapped_column(String(64))
    selection: Mapped[dict] = mapped_column(J)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)
    __table_args__ = (
        UniqueConstraint("instance_id", "principal", "idempotency_key", name="uq_bespoke_retry"),
    )


@event.listens_for(Recommendation, "before_update")
@event.listens_for(Recommendation, "before_delete")
def immutable(*_):
    raise ImmutableRecord("Bespoke recommendations are immutable")
