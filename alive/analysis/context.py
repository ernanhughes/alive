"""Bounded model context from a repository.inspect result. Truncation is refused, never hidden."""

import json

from alive.analysis.contracts import (
    CONTEXT_POLICY,
    INSTRUCTIONS,
    MAX_FILES,
    MAX_SOURCE_BYTES,
    RepositoryAnalysis,
)
from alive.workflows.context import digest, require

INPUT_KEYS = {"source_ref", "source_sha256", "scoped_sha256", "objective", "files", "omitted"}


def numbered(content):
    lines = content.split("\n")
    if lines and lines[-1] == "":
        lines.pop()  # a trailing newline does not start another line
    width = len(str(max(len(lines), 1)))
    return len(lines), "\n".join(f"{i:>{width}}| {line}" for i, line in enumerate(lines, 1))


def context_package(inputs):
    require(set(inputs) == INPUT_KEYS, "analysis_input_contract")
    files = inputs["files"]
    require(
        isinstance(files, list)
        and 1 <= len(files) <= MAX_FILES
        and all(
            isinstance(f, dict) and {"path", "content", "sha256", "bytes"} <= set(f) for f in files
        ),
        "analysis_requires_selected_files",
    )
    total = sum(f["bytes"] for f in files)
    require(total <= MAX_SOURCE_BYTES, "analysis_source_byte_ceiling")
    package_files = []
    for item in files:
        count, text = numbered(item["content"])
        package_files.append(
            {
                "path": item["path"],
                "sha256": item["sha256"],
                "bytes": item["bytes"],
                "line_count": count,
                "numbered_lines": text,
            }
        )
    return {
        "task": {
            "objective": inputs["objective"],
            "scope": "the supplied files only; this is not the whole repository",
        },
        "source": {
            "source_sha256": inputs["source_sha256"],
            "scoped_sha256": inputs["scoped_sha256"],
        },
        "files": package_files,
        "omitted": inputs["omitted"],
        "coverage": {
            "policy": CONTEXT_POLICY,
            "files_supplied": len(files),
            "bytes_supplied": total,
            "complete_for_selected_files": not inputs["omitted"],
        },
    }


def context_digest(inputs):
    return digest(context_package(inputs))


def request_bytes(inputs, output_tokens):
    """Cognition's conservative reservation for this call, in the Governor's own unit."""
    schema = RepositoryAnalysis.model_json_schema()
    body = {"instructions": INSTRUCTIONS, "data": context_package(inputs), "schema": schema}
    return len(json.dumps(body, ensure_ascii=False).encode()) + 1024 + output_tokens
