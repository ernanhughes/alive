"""Gate B1: a source can be used only while every custody fact still holds."""

import hashlib
import json
from datetime import timedelta

import pytest
from sqlalchemy import select, update

from alive.models import Event, Instance, now, uid
from alive.sources import custody
from alive.sources.models import ImmutableSource, SourceApproval, SourceCapture
from alive.workflows.context import Refused
from tests.workflow_execution_helpers import call

OP = "repository.inspect"


def repo_content(files=None):
    files = files or {"README.md": "hello world\n", "src/app.py": "print(1)\n", "docs/a.md": "a\n"}
    return {
        "kind": "repository",
        "files": [
            {
                "path": p,
                "content": text,
                "sha256": hashlib.sha256(text.encode()).hexdigest(),
                "bytes": len(text.encode()),
            }
            for p, text in sorted(files.items())
        ],
        "omitted": [{"path": ".env", "reason": "ignored_by_host_policy"}],
    }


async def captured(kernel, content=None, **over):
    args = {
        "source_type": "repository",
        "label": "fixture",
        "locator": "fixture-repo",
        "classification": "owner_internal",
        "capture_method": "test",
        "content": content or repo_content(),
    } | over
    return await custody.create_capture(kernel, **args)


async def approved(
    kernel, capture, *, scope=None, ttl=3600, operations=(OP,), request="req-00000001"
):
    return await custody.approve(
        kernel,
        capture["id"],
        confirm_sha256=capture["content_sha256"],
        operations=list(operations),
        scope=scope or {"all": True},
        ttl_seconds=ttl,
        principal="owner-test",
        request_id=request,
    )


def refused(category):
    return pytest.raises(Refused, match=category)


async def refusal(awaitable):
    """The refusal category an awaitable raises, or None.

    Returned as data: a failed expectation is then an ordinary assertion in the test body. A
    `pytest.raises` that fails *inside* the client's portal raises a BaseException there, which
    crashes the portal and buries the real failure under a teardown error.
    """
    try:
        await awaitable
    except Refused as error:
        return str(error)
    return None


def test_a_capture_identifies_content_but_exposes_none_and_stores_no_host_path(client):
    capture = call(client, captured)
    assert len(capture["content_sha256"]) == 64 and capture["item_count"] == 3
    shown = json.dumps(capture)
    assert "hello world" not in shown and "print(1)" not in shown  # inventory, not content
    assert {i["item"] for i in capture["inventory"]["items"]} == {
        "README.md",
        "src/app.py",
        "docs/a.md",
    }
    assert capture["inventory"]["omitted"] == [{"path": ".env", "reason": "ignored_by_host_policy"}]


def test_nothing_is_usable_until_the_owner_approves_the_exact_digest(client):
    capture = call(client, captured)
    resources = {
        "source_ref": capture["id"],
        "approval_id": uid(),
        "content_sha256": capture["content_sha256"],
        "scope_sha256": "0" * 64,
    }
    with refused("source_approval_missing"):
        call(client, custody.resolve, resources, OP)

    async def wrong_digest(k):
        return await custody.approve(
            k,
            capture["id"],
            confirm_sha256="0" * 64,
            operations=[OP],
            scope={"all": True},
            ttl_seconds=3600,
            principal="owner-test",
            request_id="req-00000002",
        )

    with refused("source_digest_mismatch"):
        call(client, wrong_digest)
    assert call(client, custody.list_approvals) == []


def test_approval_resolves_to_exactly_the_approved_scope(client):
    async def go(k):
        capture = await captured(k)
        approval = await approved(k, capture, scope={"items": ["README.md"]})
        return approval, await custody.resolve(k, approval["resources"], OP)

    approval, source = call(client, go)
    content = source.content
    assert [f["path"] for f in content["files"]] == ["README.md"]  # others are absent, not hidden
    assert content["omitted"] == []  # an omission for an out-of-scope path is not disclosed either
    assert source.content_sha256 != source.scoped_sha256
    assert source.scope_sha256 == approval["scope_sha256"]
    source.content["files"].clear()  # a copy: mutating it cannot change the approved view
    assert len(source.content["files"]) == 1


@pytest.mark.parametrize(
    "case,category",
    [
        ("other_operation", "source_operation_not_approved"),
        ("withdrawn", "source_withdrawn"),
        ("expired", "source_approval_expired"),
        ("wrong_digest", "source_digest_mismatch"),
        ("wrong_scope", "source_scope_mismatch"),
        ("wrong_capture", "source_approval_missing"),
        ("extra_key", "source_resources_required"),
    ],
)
def test_every_custody_fact_is_rechecked_at_the_moment_of_use(client, monkeypatch, case, category):
    async def go(k):
        capture = await captured(k)
        approval = await approved(k, capture)
        resources = dict(approval["resources"])
        operation = OP
        if case == "other_operation":
            operation = "document.extract"
        elif case == "withdrawn":
            await custody.withdraw(
                k, approval["id"], reason="owner changed their mind", principal="o"
            )
        elif case == "expired":
            monkeypatch.setattr(custody, "now", lambda: now() + timedelta(hours=2))
        elif case == "wrong_digest":
            resources["content_sha256"] = "1" * 64
        elif case == "wrong_scope":
            resources["scope_sha256"] = "2" * 64
        elif case == "wrong_capture":
            other = await captured(k, repo_content({"x.txt": "x"}), label="other")
            resources["source_ref"] = other["id"]
        elif case == "extra_key":
            resources["note"] = "x"
        return await refusal(custody.resolve(k, resources, operation))

    assert call(client, go) == category


def test_a_grant_minted_before_withdrawal_is_refused_afterwards(client):
    async def go(k):
        capture = await captured(k)
        approval = await approved(k, capture)
        grant_resources = dict(approval["resources"])  # what an earlier owner grant would carry
        assert await custody.resolve(k, grant_resources, OP)
        await custody.withdraw(k, approval["id"], reason="withdrawn", principal="owner-test")
        outcome = await refusal(custody.resolve(k, grant_resources, OP))
        # Withdrawal is idempotent and final; a fresh approval is a new record.
        again = await custody.withdraw(k, approval["id"], reason="second call", principal="x")
        assert again["withdrawn_reason"] == "withdrawn"
        newer = await approved(k, capture, request="req-00000009")
        assert newer["id"] != approval["id"]
        assert await custody.resolve(k, newer["resources"], OP)
        return outcome

    assert call(client, go) == "source_withdrawn"


def test_content_changed_underneath_the_application_is_detected(client):
    async def go(k):
        capture = await captured(k)
        approval = await approved(k, capture)
        tampered = repo_content({"README.md": "substituted\n"})
        async with k.db.sessions.begin() as session:  # Core UPDATE bypasses the ORM guard
            await session.execute(
                update(SourceCapture)
                .where(SourceCapture.id == capture["id"])
                .values(content=tampered)
            )
        return (
            await refusal(custody.resolve(k, approval["resources"], OP)),
            await refusal(approved(k, capture, request="req-00000003")),
        )

    # Both the use of an existing approval and a new approval notice the substitution.
    assert call(client, go) == ("source_content_changed", "source_content_changed")


def test_approval_is_idempotent_by_request_and_a_reused_id_with_other_terms_conflicts(client):
    async def go(k):
        capture = await captured(k)
        first = await approved(k, capture, request="req-aaaaaaaa")
        again = await approved(k, capture, request="req-aaaaaaaa")
        assert first["id"] == again["id"] and len(await custody.list_approvals(k)) == 1
        return await refusal(
            approved(k, capture, scope={"items": ["README.md"]}, request="req-aaaaaaaa")
        )

    assert call(client, go) == "source_request_id_conflict"


@pytest.mark.parametrize(
    "terms",
    [
        {"operations": []},
        {"operations": ["not a capability"]},
        {"operations": ["a.b", "a.b"]},
        {"scope": {"items": ["missing.txt"]}},
        {"scope": {"items": []}},
        {"scope": {"all": False}},
        {"scope": {"all": True, "items": ["README.md"]}},
        {"ttl": 5},
        {"ttl": 10**9},
    ],
)
def test_approval_terms_are_bounded_and_validated(client, terms):
    async def go(k):
        capture = await captured(k)
        return await refusal(approved(k, capture, **terms)), await custody.list_approvals(k)

    outcome, approvals = call(client, go)
    assert outcome is not None and approvals == []  # refused, and nothing was approved


def test_records_are_historical_evidence_not_editable_state(client):
    async def go(k):
        capture = await captured(k)
        approval = await approved(k, capture)
        async with k.db.sessions.begin() as session:
            row = await session.get(SourceCapture, capture["id"])
            row.label = "renamed"
            with pytest.raises(ImmutableSource):
                await session.flush()
            session.expire_all()
        async with k.db.sessions.begin() as session:
            row = await session.get(SourceApproval, approval["id"])
            row.scope = {"items": ["README.md"]}  # differs from the approved {"all": true}
            with pytest.raises(ImmutableSource):
                await session.flush()
            session.expire_all()
        await custody.withdraw(k, approval["id"], reason="done", principal="owner-test")
        async with k.db.sessions.begin() as session:
            row = await session.get(SourceApproval, approval["id"])
            row.withdrawn_at = None  # a withdrawal cannot be undone
            with pytest.raises(ImmutableSource):
                await session.flush()
            session.expire_all()
        async with k.db.sessions.begin() as session:
            await session.delete(await session.get(SourceCapture, capture["id"]))
            with pytest.raises(ImmutableSource):
                await session.flush()
            session.expire_all()

    call(client, go)


def test_custody_is_instance_scoped(client):
    async def go(k):
        capture = await captured(k)
        approval = await approved(k, capture)
        foreign = uid()
        async with k.db.sessions.begin() as session:
            session.add(Instance(id=foreign, name="another"))
            await session.flush()
            event = Event(
                id=uid(),
                instance_id=foreign,
                event_type="source.captured",
                source="source-owner",
                correlation_id=uid(),
                payload={},
                occurred_at=now(),
            )
            session.add(event)
            await session.flush()
            session.add(
                SourceCapture(
                    id=capture["id"][:-1] + ("0" if capture["id"][-1] != "0" else "1"),
                    instance_id=foreign,
                    source_type="repository",
                    label="foreign",
                    locator="",
                    classification="owner_internal",
                    capture_method="test",
                    content=repo_content(),
                    content_sha256=capture["content_sha256"],
                    byte_count=1,
                    item_count=1,
                    capture_event_id=event.id,
                )
            )
        ids = {c["id"] for c in await custody.list_captures(k)}
        assert capture["id"] in ids and all(i == capture["id"] or False for i in ids)
        unknown = await refusal(custody.get_capture(k, "ffffffff-ffff-ffff-ffff-ffffffffffff"))
        # Our approval pointed at the other instance's capture: it names a different capture.
        async with k.db.sessions.begin() as session:
            foreign_capture = (
                await session.scalars(select(SourceCapture).where(SourceCapture.label == "foreign"))
            ).one()
            foreign_event = (
                await session.scalars(select(Event).where(Event.instance_id == foreign))
            ).first()
            scope = {"all": True}
            foreign_approval = SourceApproval(
                id=uid(),
                capture_id=foreign_capture.id,
                instance_id=foreign,
                content_sha256=foreign_capture.content_sha256,
                operations=[OP],
                scope=scope,
                scope_sha256=custody.digest(scope),
                expires_at=now() + timedelta(hours=1),
                approved_at=now(),
                approved_by="foreign-owner",
                approval_event_id=foreign_event.id,
                idempotency_key="f" * 64,
            )
            session.add(foreign_approval)
        crossed = dict(approval["resources"]) | {"source_ref": foreign_capture.id}
        missing = await refusal(custody.resolve(k, crossed, OP))
        # A complete, internally consistent approval that belongs to ANOTHER instance is refused
        # on that ground alone.
        foreign_resources = {
            "source_ref": foreign_capture.id,
            "approval_id": foreign_approval.id,
            "content_sha256": foreign_capture.content_sha256,
            "scope_sha256": custody.digest(scope),
        }
        return (
            missing,
            unknown,
            await refusal(custody.resolve(k, foreign_resources, OP)),
        )

    assert call(client, go) == (
        "source_approval_missing",
        "source_not_found",
        "source_instance_mismatch",
    )


def test_custody_events_record_decisions_but_never_content(client):
    async def go(k):
        capture = await captured(k)
        approval = await approved(k, capture)
        await custody.withdraw(k, approval["id"], reason="because", principal="owner-test")
        async with k.db.sessions() as session:
            rows = (
                await session.scalars(select(Event).where(Event.source == "source-owner"))
            ).all()
        return [(r.event_type, json.dumps(r.payload)) for r in rows]

    events = call(client, go)
    assert [t for t, _ in events] == ["source.captured", "source.approved", "source.withdrawn"]
    for _, payload in events:
        assert "hello world" not in payload and "print(1)" not in payload
