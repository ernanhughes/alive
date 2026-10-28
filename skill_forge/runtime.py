"""Explicit, bounded dispatch for an approved ALIVE skill.

The caller supplies host-owned handlers. A model cannot register handlers or
grant capabilities. The host must enforce browser/page permissions independently.
"""
from __future__ import annotations

from collections.abc import Callable
from typing import Any

from . import SAFE_OPERATIONS, SkillError, SkillRegistry

MAX_RESULTS = 12


def execute_requested_skill(
    registry: SkillRegistry,
    skill_id: str,
    handlers: dict[str, Callable[[dict[str, Any]], Any]],
    *,
    owner_requested: bool = False,
) -> list[dict[str, Any]]:
    if not owner_requested:
        raise SkillError("an explicit owner request is required")
    manifest = registry.enabled_manifest(skill_id)
    results: list[dict[str, Any]] = []
    for step in manifest["steps"]:
        op = step["operation"]
        if op not in SAFE_OPERATIONS or op not in manifest["capabilities"]:
            raise SkillError("operation not permitted")
        handler = handlers.get(op)
        if handler is None:
            raise SkillError(f"host capability unavailable: {op}")
        result = handler(dict(step["args"]))
        results.append({"operation": op, "result": result})
        if len(results) >= MAX_RESULTS:
            break
    return results
