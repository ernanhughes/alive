"""The one place that decides whether a captured source may be used, and for what.

Capture, approval and use are three different facts:

* A capture identifies exact bytes. It is not an approval.
* An approval is an owner record bound to that capture's digest, a set of operations, a scope and
  an expiry. It can be withdrawn and nothing else about it can change.
* Use re-checks every one of those facts at the moment a stage runs, so a withdrawal, an expiry or
  a changed capture takes effect even for a grant minted earlier.

Nothing here parses untrusted bytes at workflow time and no function returns raw content except
`resolve`, which returns it already restricted to the approved scope.
"""

import hashlib
import json
import re
from dataclasses import dataclass
from datetime import timedelta

from sqlalchemy import select

from alive.capabilities.contracts import json_bytes
from alive.capabilities.manifest import ID as CAPABILITY_ID
from alive.models import Memory, now, uid
from alive.sources.models import (
    CLASSIFICATIONS,
    SOURCE_TYPES,
    SourceApproval,
    SourceCapture,
)
from alive.workflows.context import aware, require

OWNER_EVENT_SOURCE = "source-owner"
MAX_CAPTURE_BYTES = 524288
MIN_TTL_SECONDS = 60
MAX_TTL_SECONDS = 30 * 24 * 3600
RESOURCE_KEYS = {"source_ref", "approval_id", "content_sha256", "scope_sha256"}
# Where each source type keeps the list a scope can narrow, and the key that names an item.
ITEM_KEYS = {
    "repository": ("files", "path"),
    "document": ("sections", "index"),
    "browser": ("sections", "index"),
    "collection": ("items", "memory_id"),
}


def digest(value):
    return hashlib.sha256(json_bytes(value)).hexdigest()


def item_names(source_type, content):
    listing, key = ITEM_KEYS[source_type]
    return [str(item[key]) for item in content.get(listing, [])]


def inventory(source_type, content):
    """Safe, content-free metadata an owner can inspect before approving."""
    listing, key = ITEM_KEYS[source_type]
    if source_type == "repository":
        items = [
            {"item": f["path"], "bytes": f["bytes"], "sha256": f["sha256"]}
            for f in content["files"]
        ]
    elif source_type == "collection":
        items = [
            {"item": i["memory_id"], "sha256": i["content_sha256"], "type": i["memory_type"]}
            for i in content["items"]
        ]
    else:
        items = [
            {"item": str(s[key]), "heading": s.get("heading", "")[:80], "sha256": s["sha256"]}
            for s in content[listing]
        ]
    view = {"items": items, "omitted": content.get("omitted", [])}
    for field in ("format", "origin", "title", "parser", "truncated"):
        if field in content:
            view[field] = content[field]
    return view


def apply_scope(source_type, content, scope):
    """What an approval allows. Items outside the scope are absent, not hidden."""
    if scope.get("all") is True:
        return content
    listing, key = ITEM_KEYS[source_type]
    allowed = set(scope["items"])
    kept = {**content, listing: [i for i in content[listing] if str(i[key]) in allowed]}
    if "omitted" in kept:
        kept["omitted"] = [o for o in kept["omitted"] if o.get("path") in allowed]
    return kept


def capture_view(row):
    return {
        "id": row.id,
        "source_type": row.source_type,
        "label": row.label,
        "locator": row.locator,
        "classification": row.classification,
        "capture_method": row.capture_method,
        "content_sha256": row.content_sha256,
        "byte_count": row.byte_count,
        "item_count": row.item_count,
        "captured_at": aware(row.captured_at).isoformat(),
        "inventory": inventory(row.source_type, row.content),
    }


def approval_view(row):
    return {
        "id": row.id,
        "capture_id": row.capture_id,
        "content_sha256": row.content_sha256,
        "operations": list(row.operations),
        "scope": row.scope,
        "scope_sha256": row.scope_sha256,
        "expires_at": aware(row.expires_at).isoformat(),
        "approved_at": aware(row.approved_at).isoformat(),
        "approved_by": row.approved_by,
        "withdrawn_at": aware(row.withdrawn_at).isoformat() if row.withdrawn_at else None,
        "withdrawn_reason": row.withdrawn_reason,
        "resources": resources_for(row),
    }


def resources_for(approval):
    """The exact binding an owner grant carries for a stage that reads this source."""
    return {
        "source_ref": approval.capture_id,
        "approval_id": approval.id,
        "content_sha256": approval.content_sha256,
        "scope_sha256": approval.scope_sha256,
    }


async def create_capture(
    kernel, *, source_type, label, locator, classification, capture_method, content
):
    require(source_type in SOURCE_TYPES, "source_type_refused")
    require(
        classification in CLASSIFICATIONS
        and (source_type != "browser" or classification == "untrusted_browser"),
        "source_classification_refused",
    )
    require(type(label) is str and 1 <= len(label) <= 120, "source_label_refused")
    require(type(locator) is str and len(locator) <= 256, "source_locator_refused")
    require(type(content) is dict and content.get("kind") == source_type, "source_content_shape")
    blob = json_bytes(content)
    require(len(blob) <= MAX_CAPTURE_BYTES, "source_capture_size")
    sha = hashlib.sha256(blob).hexdigest()
    names = item_names(source_type, content)
    require(len(set(names)) == len(names), "source_duplicate_item")
    capture_id = uid()
    async with kernel.lock, kernel.db.sessions.begin() as session:
        event = kernel.add_event(
            session,
            "source.captured",
            {
                "capture_id": capture_id,
                "source_type": source_type,
                "label": label,
                "content_sha256": sha,
                "byte_count": len(blob),
                "item_count": len(names),
                "classification": classification,
            },
            source=OWNER_EVENT_SOURCE,
            correlation=capture_id,
        )
        row = SourceCapture(
            id=capture_id,
            instance_id=kernel.instance_id,
            source_type=source_type,
            label=label,
            locator=locator,
            classification=classification,
            capture_method=capture_method,
            content=json.loads(blob),
            content_sha256=sha,
            byte_count=len(blob),
            item_count=len(names),
            captured_at=now(),
            capture_event_id=str(event.event_id),
        )
        session.add(row)
        await session.flush()
        return capture_view(row)


async def get_capture(kernel, capture_id):
    async with kernel.db.sessions() as session:
        row = await session.get(SourceCapture, capture_id)
        require(row is not None and row.instance_id == kernel.instance_id, "source_not_found")
        return capture_view(row)


async def list_captures(kernel):
    async with kernel.db.sessions() as session:
        rows = await session.scalars(
            select(SourceCapture)
            .where(SourceCapture.instance_id == kernel.instance_id)
            .order_by(SourceCapture.captured_at.desc(), SourceCapture.id)
            .limit(200)
        )
        return [capture_view(r) | {"inventory": None} for r in rows.all()]


def checked_scope(source_type, content, scope):
    require(type(scope) is dict, "source_scope_refused")
    if scope == {"all": True}:
        return scope
    names = item_names(source_type, content)
    items = scope.get("items") if set(scope) == {"items"} else None
    require(
        type(items) is list
        and 1 <= len(items) <= 256
        and all(type(i) is str for i in items)
        and len(set(items)) == len(items)
        and set(items) <= set(names),
        "source_scope_refused",
    )
    return {"items": sorted(items)}


async def approve(
    kernel, capture_id, *, confirm_sha256, operations, scope, ttl_seconds, principal, request_id
):
    """The owner's explicit decision. The caller must restate the exact digest it inspected."""
    require(
        type(operations) in (list, tuple)
        and 1 <= len(operations) <= 8
        and all(type(o) is str and re.fullmatch(CAPABILITY_ID, o) for o in operations)
        and len(set(operations)) == len(operations),
        "source_operations_refused",
    )
    require(
        type(ttl_seconds) is int and MIN_TTL_SECONDS <= ttl_seconds <= MAX_TTL_SECONDS,
        "source_expiry_refused",
    )
    require(type(principal) is str and 1 <= len(principal) <= 100, "source_principal_refused")
    require(type(request_id) is str and 8 <= len(request_id) <= 100, "source_request_id_refused")
    async with kernel.lock, kernel.db.sessions.begin() as session:
        capture = await session.get(SourceCapture, capture_id)
        require(
            capture is not None and capture.instance_id == kernel.instance_id, "source_not_found"
        )
        require(confirm_sha256 == capture.content_sha256, "source_digest_mismatch")
        require(digest(capture.content) == capture.content_sha256, "source_content_changed")
        scope = checked_scope(capture.source_type, capture.content, scope)
        ordered = sorted(operations)
        key = hashlib.sha256(request_id.encode()).hexdigest()
        existing = await session.scalar(
            select(SourceApproval).where(
                SourceApproval.instance_id == kernel.instance_id,
                SourceApproval.idempotency_key == key,
            )
        )
        if existing is not None:
            # A retried request returns the same approval; a reused id with different terms is a
            # conflict, never a second approval.
            require(
                existing.capture_id == capture_id
                and existing.content_sha256 == capture.content_sha256
                and list(existing.operations) == ordered
                and existing.scope_sha256 == digest(scope),
                "source_request_id_conflict",
            )
            return approval_view(existing)
        approved_at = now()
        expires_at = approved_at + timedelta(seconds=ttl_seconds)
        approval_id = uid()
        event = kernel.add_event(
            session,
            "source.approved",
            {
                "approval_id": approval_id,
                "capture_id": capture_id,
                "content_sha256": capture.content_sha256,
                "operations": ordered,
                "scope_sha256": digest(scope),
                "expires_at": expires_at.isoformat(),
                "approved_by": principal,
            },
            source=OWNER_EVENT_SOURCE,
            correlation=capture_id,
        )
        row = SourceApproval(
            id=approval_id,
            capture_id=capture_id,
            instance_id=kernel.instance_id,
            content_sha256=capture.content_sha256,
            operations=ordered,
            scope=scope,
            scope_sha256=digest(scope),
            expires_at=expires_at,
            approved_at=approved_at,
            approved_by=principal,
            approval_event_id=str(event.event_id),
            idempotency_key=key,
        )
        session.add(row)
        await session.flush()
        return approval_view(row)


async def withdraw(kernel, approval_id, *, reason, principal):
    require(type(reason) is str and 1 <= len(reason) <= 200, "source_reason_refused")
    require(type(principal) is str and 1 <= len(principal) <= 100, "source_principal_refused")
    async with kernel.lock, kernel.db.sessions.begin() as session:
        row = await session.get(SourceApproval, approval_id)
        require(
            row is not None and row.instance_id == kernel.instance_id, "source_approval_missing"
        )
        if row.withdrawn_at is not None:
            return approval_view(row)  # idempotent: the first withdrawal stands
        event = kernel.add_event(
            session,
            "source.withdrawn",
            {"approval_id": approval_id, "capture_id": row.capture_id, "reason": reason},
            source=OWNER_EVENT_SOURCE,
            correlation=row.capture_id,
        )
        row.withdrawn_at = now()
        row.withdrawn_by = principal
        row.withdrawn_reason = reason
        row.withdrawal_event_id = str(event.event_id)
        await session.flush()
        return approval_view(row)


async def list_approvals(kernel, capture_id=None):
    async with kernel.db.sessions() as session:
        query = select(SourceApproval).where(SourceApproval.instance_id == kernel.instance_id)
        if capture_id:
            query = query.where(SourceApproval.capture_id == capture_id)
        rows = await session.scalars(query.order_by(SourceApproval.approved_at.desc()).limit(200))
        return [approval_view(r) for r in rows.all()]


@dataclass(frozen=True)
class ApprovedSource:
    """Approved content, already narrowed to the approval's scope. Detached from the database."""

    source_ref: str
    approval_id: str
    source_type: str
    label: str
    classification: str
    content_sha256: str
    scope_sha256: str
    scoped_sha256: str
    captured_at: str
    expires_at: str
    blob: bytes

    @property
    def content(self):
        return json.loads(self.blob)  # a copy; callers cannot mutate the approved view


async def materialize_collection(session, kernel, scoped):
    """A collection holds ids and hashes only. Content is read live and must still match."""
    ids = [item["memory_id"] for item in scoped["items"]]
    rows = (
        await session.scalars(
            select(Memory).where(Memory.instance_id == kernel.instance_id, Memory.id.in_(ids))
        )
    ).all()
    live = {row.id: row for row in rows}
    items, omitted = [], []
    for item in scoped["items"]:
        row = live.get(item["memory_id"])
        if row is None:
            omitted.append({"memory_id": item["memory_id"], "reason": "unavailable"})
        elif hashlib.sha256(row.content.encode()).hexdigest() != item["content_sha256"]:
            omitted.append({"memory_id": item["memory_id"], "reason": "changed_since_approval"})
        else:
            items.append(
                item | {"content": row.content, "created_at": aware(row.created_at).isoformat()}
            )
    return {**scoped, "items": items, "omitted": omitted}


async def resolve(kernel, resources, operation):
    """Every fact must hold now. The order of checks is also the order of the refusal categories."""
    require(
        type(resources) is dict and set(resources) == RESOURCE_KEYS, "source_resources_required"
    )
    async with kernel.db.sessions() as session:
        approval = await session.get(SourceApproval, resources["approval_id"])
        capture = await session.get(SourceCapture, resources["source_ref"])
        require(
            approval is not None and capture is not None and approval.capture_id == capture.id,
            "source_approval_missing",
        )
        require(
            approval.instance_id == capture.instance_id == kernel.instance_id,
            "source_instance_mismatch",
        )
        require(approval.withdrawn_at is None, "source_withdrawn")
        require(aware(approval.expires_at) > now(), "source_approval_expired")
        require(operation in list(approval.operations), "source_operation_not_approved")
        require(
            approval.content_sha256 == capture.content_sha256 == resources["content_sha256"],
            "source_digest_mismatch",
        )
        require(
            approval.scope_sha256 == resources["scope_sha256"] == digest(approval.scope),
            "source_scope_mismatch",
        )
        require(digest(capture.content) == capture.content_sha256, "source_content_changed")
        scoped = apply_scope(capture.source_type, capture.content, approval.scope)
        scoped_sha256 = digest(scoped)  # the approved reference, before any live content joins it
        if capture.source_type == "collection":
            scoped = await materialize_collection(session, kernel, scoped)
        return ApprovedSource(
            source_ref=capture.id,
            approval_id=approval.id,
            source_type=capture.source_type,
            label=capture.label,
            classification=capture.classification,
            content_sha256=capture.content_sha256,
            scope_sha256=approval.scope_sha256,
            scoped_sha256=scoped_sha256,
            captured_at=aware(capture.captured_at).isoformat(),
            expires_at=aware(approval.expires_at).isoformat(),
            blob=json_bytes(scoped),
        )
