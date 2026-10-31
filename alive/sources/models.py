"""Durable source custody records.

A capture is immutable: it identifies bytes, it does not authorize their use. An approval is a
separate owner record bound to the capture's exact digest, an operation set, a scope and an expiry.
The only field of an approval that ever changes is its one-way withdrawal.
"""

from datetime import datetime

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    ForeignKey,
    Integer,
    String,
    UniqueConstraint,
    event,
    inspect,
)
from sqlalchemy.orm import Mapped, mapped_column

from alive.models import Base, J, now, uid

SOURCE_TYPES = ("repository", "document", "browser", "collection")
CLASSIFICATIONS = ("owner_internal", "untrusted_browser")


class ImmutableSource(RuntimeError):
    """A custody record that is part of a historical identity cannot be rewritten."""


class SourceCapture(Base):
    __tablename__ = "source_captures"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    instance_id: Mapped[str] = mapped_column(ForeignKey("alive_instances.id"), index=True)
    source_type: Mapped[str] = mapped_column(String(16))
    label: Mapped[str] = mapped_column(String(120))
    # Display only. A repository capture never stores the host path it was read from.
    locator: Mapped[str] = mapped_column(String(256), default="")
    classification: Mapped[str] = mapped_column(String(24))
    capture_method: Mapped[str] = mapped_column(String(48))
    content: Mapped[dict] = mapped_column(J)
    content_sha256: Mapped[str] = mapped_column(String(64))
    byte_count: Mapped[int] = mapped_column(Integer)
    item_count: Mapped[int] = mapped_column(Integer)
    captured_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)
    capture_event_id: Mapped[str] = mapped_column(ForeignKey("events.id"))
    __table_args__ = (
        CheckConstraint(
            "source_type IN ('repository','document','browser','collection')",
            name="ck_source_capture_type",
        ),
        CheckConstraint(
            "classification IN ('owner_internal','untrusted_browser')",
            name="ck_source_capture_classification",
        ),
        CheckConstraint("byte_count >= 0 AND item_count >= 0", name="ck_source_capture_counts"),
    )


class SourceApproval(Base):
    __tablename__ = "source_approvals"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    capture_id: Mapped[str] = mapped_column(ForeignKey("source_captures.id"), index=True)
    instance_id: Mapped[str] = mapped_column(ForeignKey("alive_instances.id"), index=True)
    # Copied from the capture at approval time and compared on every use.
    content_sha256: Mapped[str] = mapped_column(String(64))
    operations: Mapped[list] = mapped_column(J)
    scope: Mapped[dict] = mapped_column(J)
    scope_sha256: Mapped[str] = mapped_column(String(64))
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    approved_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)
    approved_by: Mapped[str] = mapped_column(String(100))
    approval_event_id: Mapped[str] = mapped_column(ForeignKey("events.id"))
    idempotency_key: Mapped[str] = mapped_column(String(64))
    withdrawn_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    withdrawn_by: Mapped[str | None] = mapped_column(String(100))
    withdrawn_reason: Mapped[str | None] = mapped_column(String(200))
    withdrawal_event_id: Mapped[str | None] = mapped_column(ForeignKey("events.id"))
    __table_args__ = (
        UniqueConstraint("instance_id", "idempotency_key", name="uq_source_approval_idempotency"),
    )


_APPROVAL_FROZEN = (
    "capture_id",
    "instance_id",
    "content_sha256",
    "operations",
    "scope",
    "scope_sha256",
    "expires_at",
    "approved_at",
    "approved_by",
    "approval_event_id",
    "idempotency_key",
)


@event.listens_for(SourceCapture, "before_update")
def _capture_is_immutable(_mapper, _connection, target):
    raise ImmutableSource("a source capture identifies exact bytes and is never rewritten")


@event.listens_for(SourceApproval, "before_update")
def _approval_changes_only_by_withdrawal(_mapper, _connection, target):
    state = inspect(target)
    for column in _APPROVAL_FROZEN:
        if state.attrs[column].history.has_changes():
            raise ImmutableSource(f"SourceApproval.{column} is part of the approval's identity")
    if state.attrs["withdrawn_at"].history.deleted:
        # A withdrawal cannot be undone; a new approval is a new record.
        previous = state.attrs["withdrawn_at"].history.deleted[0]
        if previous is not None:
            raise ImmutableSource("a withdrawal is final")


@event.listens_for(SourceCapture, "before_delete")
@event.listens_for(SourceApproval, "before_delete")
def _never_deleted(_mapper, _connection, target):
    raise ImmutableSource("custody records are historical evidence and are never deleted")
