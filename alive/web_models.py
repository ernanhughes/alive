"""Local, provenance-separated browser experience; no raw browsing archive is public."""

from datetime import datetime

from sqlalchemy import DateTime, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column

from alive.models import Base, J, now, uid


class WebExperience(Base):
    __tablename__ = "web_experiences"
    id: Mapped[str] = mapped_column(primary_key=True, default=uid)
    instance_id: Mapped[str] = mapped_column(ForeignKey("alive_instances.id"), index=True)
    kind: Mapped[str] = mapped_column(index=True)
    parent_id: Mapped[str | None] = mapped_column(ForeignKey("web_experiences.id"))
    status: Mapped[str] = mapped_column(default="recorded")
    data: Mapped[dict] = mapped_column(J, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)
