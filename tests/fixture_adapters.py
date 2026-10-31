"""Adapters for resolution tests only. Reached through a test-built trusted allowlist entry."""

from alive.workflows.adapters import StageResult


async def marker_prepare(_ctx):
    return StageResult({"context": {"marker": "bound-alternative"}, "claims": [], "sources": []})
