"""Owner tooling for source custody: prepare, inspect, approve, withdraw.

This is a local operator command, not a network route. It adds no write surface to the API. It
acts with the database access and filesystem rights of the person running it, which is the same
trust the rest of ALIVE already places in the local owner. It does not start the runtime and does
not mint a workflow grant; it records an exact, revocable decision about one captured source.

    python -m alive.sources prepare repository --root ./project --label project --all
    python -m alive.sources inspect <capture-id>
    python -m alive.sources approve <capture-id> --confirm-sha256 <digest> \\
        --operation repository.inspect --all --ttl-hours 24
    python -m alive.sources withdraw <approval-id> --reason "no longer needed"
"""

import argparse
import asyncio
import getpass
import json
import sys

from sqlalchemy import select

from alive.config import Settings
from alive.db import Database
from alive.kernel import Kernel
from alive.models import Instance, uid
from alive.sources import capture, custody
from alive.workflows.context import Refused


async def open_kernel(settings):
    """The minimum the custody service needs. Never initialize(): that takes the runtime lock."""
    db = Database(settings.database_url)
    kernel = Kernel(db, None, settings)
    async with db.sessions() as session:
        instance = await session.scalar(select(Instance))
    if instance is None:
        raise Refused("alive_not_started_against_this_database")
    kernel.instance_id = instance.id
    return kernel


def principal():
    return f"owner-cli:{getpass.getuser()}"[:100]


def show(value):
    print(json.dumps(value, indent=2, sort_keys=True, default=str))


async def prepare(kernel, args):
    if args.kind == "repository":
        paths = None if args.all else args.path
        if not args.all and not args.path:
            raise Refused("repository_choose_paths_or_all")
        content = await asyncio.to_thread(capture.repository_content, args.root, paths)
        classification, method, locator = "owner_internal", "owner_cli_repository", args.label
    elif args.kind == "document":
        content = await asyncio.to_thread(capture.document_content, args.file)
        classification, method, locator = "owner_internal", "owner_cli_document", args.label
    elif args.kind == "browser":
        content = await capture.browser_content(kernel, args.event_id)
        classification, method = "untrusted_browser", "owner_cli_observation"
        locator = content["origin"]
    else:
        content, previews = await capture.collection_content(
            kernel, limit=args.limit, query=args.query
        )
        classification, method, locator = "owner_internal", "owner_cli_collection", args.label
        print("Items selected (preview only; nothing below is stored):", file=sys.stderr)
        for item in previews:
            print(f"  {item['memory_id']}  {item['preview']!r}", file=sys.stderr)
    created = await custody.create_capture(
        kernel,
        source_type=args.kind,
        label=args.label,
        locator=locator,
        classification=classification,
        capture_method=method,
        content=content,
    )
    show(created)
    print(
        "\nThis is a CANDIDATE. It is not approved and no workflow can read it. Inspect the "
        "inventory, then approve the exact digest above.",
        file=sys.stderr,
    )


async def approve(kernel, args):
    if args.all == bool(args.item):
        raise Refused("source_scope_choose_all_or_items")
    result = await custody.approve(
        kernel,
        args.capture_id,
        confirm_sha256=args.confirm_sha256,
        operations=args.operation,
        scope={"all": True} if args.all else {"items": args.item},
        ttl_seconds=int(args.ttl_hours * 3600),
        principal=principal(),
        request_id=args.request_id or uid(),
    )
    show(result)


async def run(args):
    kernel = await open_kernel(Settings())
    try:
        if args.command == "prepare":
            await prepare(kernel, args)
        elif args.command == "list":
            show(await custody.list_captures(kernel))
        elif args.command == "inspect":
            show(await custody.get_capture(kernel, args.capture_id))
        elif args.command == "approve":
            await approve(kernel, args)
        elif args.command == "withdraw":
            show(
                await custody.withdraw(
                    kernel, args.approval_id, reason=args.reason, principal=principal()
                )
            )
        elif args.command == "approvals":
            show(await custody.list_approvals(kernel, args.capture))
    finally:
        await kernel.db.engine.dispose()


def parser():
    top = argparse.ArgumentParser(
        prog="python -m alive.sources", description=__doc__.split("\n")[0]
    )
    commands = top.add_subparsers(dest="command", required=True)
    prep = commands.add_parser("prepare", help="capture a candidate; this approves nothing")
    kinds = prep.add_subparsers(dest="kind", required=True)
    repo = kinds.add_parser("repository")
    repo.add_argument("--root", required=True)
    repo.add_argument("--label", required=True)
    repo.add_argument("--path", action="append", default=[])
    repo.add_argument("--all", action="store_true")
    doc = kinds.add_parser("document", help="text, Markdown or HTML (PDF is not supported)")
    doc.add_argument("--file", required=True)
    doc.add_argument("--label", required=True)
    page = kinds.add_parser("browser", help="an observation ALIVE already captured")
    page.add_argument("--event-id", required=True)
    page.add_argument("--label", required=True)
    coll = kinds.add_parser("collection", help="freeze a set of existing memories by id and hash")
    coll.add_argument("--label", required=True)
    coll.add_argument("--limit", type=int, default=64)
    coll.add_argument("--query", default="")
    commands.add_parser("list")
    inspect = commands.add_parser("inspect")
    inspect.add_argument("capture_id")
    grant = commands.add_parser("approve", help="the owner's decision; restate the digest")
    grant.add_argument("capture_id")
    grant.add_argument("--confirm-sha256", required=True)
    grant.add_argument("--operation", action="append", required=True)
    grant.add_argument("--all", action="store_true")
    grant.add_argument("--item", action="append", default=[])
    grant.add_argument("--ttl-hours", type=float, default=24)
    grant.add_argument("--request-id", help="reuse to retry safely; omitted = a new decision")
    out = commands.add_parser("withdraw")
    out.add_argument("approval_id")
    out.add_argument("--reason", required=True)
    approvals = commands.add_parser("approvals")
    approvals.add_argument("--capture")
    return top


def main(argv=None):
    args = parser().parse_args(argv)
    try:
        asyncio.run(run(args))
    except Refused as error:
        print(f"refused: {error}", file=sys.stderr)
        return 1
    except OSError as error:
        print(f"refused: {type(error).__name__}", file=sys.stderr)  # no paths in messages
        return 1
    return 0
