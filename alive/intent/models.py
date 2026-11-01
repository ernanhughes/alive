"""Immutable history of how each recommendation was produced. Replay never calls a model."""

from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, String, event
from sqlalchemy.orm import Mapped, mapped_column

from alive.models import Base, J, now, uid
from alive.workflows.models import ImmutableRecord


class IntentRecommendation(Base):
    __tablename__ = "intent_recommendations"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    instance_id: Mapped[str] = mapped_column(ForeignKey("alive_instances.id"), index=True)
    admission_id: Mapped[str] = mapped_column(ForeignKey("owner_admissions.id"), unique=True)
    record_sha256: Mapped[str] = mapped_column(String(64))
    record: Mapped[dict] = mapped_column(J)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)


@event.listens_for(IntentRecommendation, "before_update")
@event.listens_for(IntentRecommendation, "before_delete")
def immutable(*_):
    raise ImmutableRecord("intent recommendations are immutable")
