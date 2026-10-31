"""Developer tooling: list, validate, inspect and doctor capability manifests.

Nothing here imports or runs an implementation. Validation parses YAML, builds a throwaway
registry and reports what the startup catalogue would do with the declaration.
"""

import argparse
import json
import sys
from pathlib import Path

from alive.capabilities.api import detail, summary
from alive.capabilities.manifest import ManifestError, manifest_sha256, parse
from alive.capabilities.registry import CapabilityRegistry, load_registry


def _registry(args):
    return load_registry(args.directory)


def _print(value, as_json):
    if as_json:
        print(json.dumps(value, indent=2, sort_keys=True))
        return
    if isinstance(value, list):
        for item in value:
            print(
                f"{item['id']}@{item['version']:<8} {item['status']:<12} "
                f"{item['effect_class']:<7} impl={item['implementation_state']}"
            )
    else:
        for key, item in value.items():
            print(f"{key}: {item}")


def list_command(args):
    registry = _registry(args)
    _print([summary(registry, cap) for cap in registry.list()], args.json)
    return 0


def inspect_command(args):
    registry = _registry(args)
    name, _, version = args.capability.partition("@")
    try:
        cap = registry.get(name, version or None)
    except KeyError:
        print(f"unknown capability: {args.capability}", file=sys.stderr)
        return 1
    print(json.dumps(detail(registry, cap), indent=2, sort_keys=True))
    return 0


def validate_command(args):
    path = Path(args.path)
    if path.is_symlink() or not path.is_file():
        print("invalid: manifest must be a regular file", file=sys.stderr)
        return 1
    try:
        manifest = parse(path.read_bytes())
        if path.name != f"{manifest.id}@{manifest.version}.yaml":
            raise ManifestError(f"filename must be {manifest.id}@{manifest.version}.yaml")
        existing = [parse_manifest(cap) for cap in _registry(args).list()]
        # Re-validating an installed file is fine; a different manifest reusing its identity
        # is a duplicate and the registry constructor refuses it.
        existing = [
            m
            for m in existing
            if (m.id, m.version, manifest_sha256(m))
            != (manifest.id, manifest.version, manifest_sha256(manifest))
        ]
        registry = CapabilityRegistry([*existing, manifest])
    except (ManifestError, OSError) as error:
        print(f"invalid: {error}", file=sys.stderr)
        return 1
    cap = registry.get(manifest.id, manifest.version)
    report = {
        "id": manifest.id,
        "version": manifest.version,
        "manifest_sha256": manifest_sha256(manifest),
        "status": cap.status,
        "implementation_state": registry.implementation_state(cap),
        "usable_in_workflow": cap.executable,
        "reason": cap.reason,
        "note": "Usable means installed and valid. A run still needs an exact owner grant.",
    }
    _print(report, args.json)
    return 0 if cap.executable else 1


def parse_manifest(cap):
    return parse(json.dumps(cap.manifest))


def doctor_command(args):
    try:
        registry = _registry(args)
    except ManifestError as error:
        print(f"invalid catalogue: {error}", file=sys.stderr)
        return 1
    caps = registry.list()
    counts = {}
    for cap in caps:
        counts[cap.status] = counts.get(cap.status, 0) + 1
    problems = [
        f"{c.identity['id']}@{c.identity['version']}: {c.reason}"
        for c in caps
        if c.status == "incompatible"
    ]
    _print({"capabilities": len(caps), "by_status": counts, "problems": problems}, args.json)
    return 1 if problems else 0


def main(argv=None):
    parser = argparse.ArgumentParser(prog="python -m alive.capabilities")
    common = argparse.ArgumentParser(add_help=False)
    common.add_argument("--directory", help="extra manifest directory (never imported as code)")
    common.add_argument("--json", action="store_true")
    commands = parser.add_subparsers(dest="command", required=True)
    commands.add_parser("list", parents=[common]).set_defaults(run=list_command)
    inspect = commands.add_parser("inspect", parents=[common])
    inspect.add_argument("capability", help="id or id@version")
    inspect.set_defaults(run=inspect_command)
    validate = commands.add_parser("validate", parents=[common])
    validate.add_argument("path")
    validate.set_defaults(run=validate_command)
    commands.add_parser("doctor", parents=[common]).set_defaults(run=doctor_command)
    args = parser.parse_args(argv)
    return args.run(args)
