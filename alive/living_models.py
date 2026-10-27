from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from alive.models import Base, J, now, uid


class LivingPolicy(Base):
    __tablename__ = "living_policies"
    instance_id: Mapped[str] = mapped_column(ForeignKey("alive_instances.id"), primary_key=True)
    data: Mapped[dict] = mapped_column(J, default=lambda: {"version": 0, "contexts": {}})
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)


class LivingJourney(Base):
    __tablename__ = "living_journeys"
    id: Mapped[str] = mapped_column(primary_key=True, default=uid)
    instance_id: Mapped[str] = mapped_column(ForeignKey("alive_instances.id"))
    provider: Mapped[str]
    status: Mapped[str] = mapped_column(default="ready")
    data: Mapped[dict] = mapped_column(J, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)


class LivingTransition(Base):
    __tablename__ = "living_transitions"
    id: Mapped[str] = mapped_column(primary_key=True, default=uid)
    instance_id: Mapped[str] = mapped_column(ForeignKey("alive_instances.id"))
    journey_id: Mapped[str] = mapped_column(ForeignKey("living_journeys.id"))
    episode: Mapped[int]
    context: Mapped[str]
    data: Mapped[dict] = mapped_column(J)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)
    __table_args__ = (UniqueConstraint("journey_id", "episode"),)
