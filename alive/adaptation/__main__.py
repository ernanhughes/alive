"""Owner-local lesson inspection/qualification. Does not run inference or execute model code."""

import argparse
import asyncio
import json

from alive.adaptation import service
from alive.config import Settings
from alive.sources.cli import open_kernel, principal


async def main(args):
    settings = Settings()
    kernel = await open_kernel(settings)
    try:
        state = await service.listing(kernel)
        if args.command == "inspect":
            for lesson in state["lessons"]:
                lesson["proposed_export"] = service.export_text(lesson)
                lesson["export_sha256"] = service.digest(lesson["proposed_export"])
            print(json.dumps(state, indent=2))
        elif args.command == "feedback":
            from alive.adaptation.oracle import measure

            measurement = await measure(kernel, args.admission, args.task)
            result = await service.experience(
                kernel, args.admission, measurement, args.feedback_key
            )
            print(json.dumps({"experience_id": result, "measurement_ref": measurement}))
        else:
            result = await service.transition(
                kernel,
                args.lesson,
                state=args.state,
                expected_sha256=args.confirm_sha256,
                principal=principal(),
                export_sha256=args.export_sha256,
                counterevidence_ref=args.counterevidence,
            )
            print(json.dumps({"version_ref": result}))
    finally:
        await kernel.db.engine.dispose()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    commands.add_parser("inspect")
    feedback = commands.add_parser("feedback", help="Execute only frozen public fixture oracle")
    feedback.add_argument("admission")
    feedback.add_argument("--task", required=True)
    feedback.add_argument("--feedback-key", required=True)
    change = commands.add_parser("transition")
    change.add_argument("lesson")
    change.add_argument("state", choices=["qualified", "active", "revised", "rejected"])
    change.add_argument("--confirm-sha256", required=True)
    change.add_argument("--export-sha256")
    change.add_argument("--counterevidence")
    asyncio.run(main(parser.parse_args()))
