"""Local owner review/approval. No workflow starts from this command."""

import argparse
import asyncio
import json
import sys
from importlib import resources

from alive.admission import service
from alive.capabilities.registry import load_registry
from alive.config import Settings
from alive.sources.cli import open_kernel, principal
from alive.workflows.context import Refused
from alive.workflows.store import register_definition


async def run(args):
    settings = Settings()
    kernel = await open_kernel(settings)
    kernel.capabilities = load_registry(
        settings.alive_capability_directory or None,
        disabled=settings.alive_disabled_capabilities,
        limits=settings.alive_capability_limits,
    )
    try:
        if args.command == "install":
            raw = (resources.files("alive.admission") / "repository-inspection.json").read_text()
            result, _ = await register_definition(kernel, raw, status="active", source="admin")
        elif args.command == "inspect":
            result = await service.get(kernel, args.admission_id)
        elif args.command == "approve":
            result = await service.approve(
                kernel, args.admission_id, confirm_sha256=args.confirm_sha256, principal=principal()
            )
        else:
            result = await service.revoke(kernel, args.admission_id, principal=principal())
        print(json.dumps(result, indent=2, default=str))
    finally:
        await kernel.db.engine.dispose()


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    commands.add_parser("install", help="register only the shipped closed admission profile")
    for name in ("inspect", "approve", "revoke"):
        command = commands.add_parser(name)
        command.add_argument("admission_id")
        if name == "approve":
            command.add_argument("--confirm-sha256", required=True)
    try:
        asyncio.run(run(parser.parse_args(argv)))
    except (Refused, OSError) as error:
        print(
            f"refused: {error if isinstance(error, Refused) else type(error).__name__}",
            file=sys.stderr,
        )
        return 1
    return 0
