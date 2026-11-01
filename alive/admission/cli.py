"""Local owner review/approval. No workflow starts from this command."""

import argparse
import asyncio
import json
import sys

from alive.admission import live, service
from alive.admission.profiles import PROFILES, definition_text
from alive.capabilities.registry import load_registry
from alive.config import Settings
from alive.sources.cli import open_kernel, principal
from alive.workflows.context import Refused
from alive.workflows.store import register_definition


async def run(args):
    settings = Settings()
    kernel = await open_kernel(settings)

    async def model_provider_ready():
        # This process reads no provider credential. Approval records consent only; the server
        # re-runs the same feasibility with its real readiness probe before any start.
        return True

    kernel.model_provider_ready = model_provider_ready
    kernel.capabilities = load_registry(
        settings.alive_capability_directory or None,
        disabled=settings.alive_disabled_capabilities,
        limits=settings.alive_capability_limits,
    )
    try:
        if args.command == "install":
            profiles = [args.profile] if args.profile else list(PROFILES)
            result = {}
            for name in profiles:
                registered, _ = await register_definition(
                    kernel, definition_text(PROFILES[name]), status="active", source="admin"
                )
                result[name] = registered
        elif args.command == "trust":
            result = await live.approve(
                kernel, args.admission_id, confirm_sha256=args.confirm_sha256, principal=principal()
            )
        elif args.command == "untrust":
            await live.revoke(kernel, args.admission_id, principal=principal())
            result = {"state": "revoked"}
        elif args.command == "inspect-trust":
            async with kernel.db.sessions() as session:
                result = await live.consent(session, kernel, args.admission_id, active=False)
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
    install = commands.add_parser("install", help="register only the shipped closed profiles")
    install.add_argument("--profile", choices=list(PROFILES))
    for name in ("inspect", "approve", "revoke", "trust", "untrust", "inspect-trust"):
        command = commands.add_parser(name)
        command.add_argument("admission_id")
        if name in ("approve", "trust"):
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
