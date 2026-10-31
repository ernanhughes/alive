"""Trusted-host capture builders. Each returns content for `custody.create_capture`; none approves.

These run in the owner's process on the owner's machine. They are never reachable from a workflow
stage, a model or an HTTP route.
"""

import hashlib
import os
import re
import unicodedata
from pathlib import Path

from sqlalchemy import select

from alive.capabilities.repository import (
    CAPTURE_MAX_BYTES,
    CAPTURE_MAX_FILES,
    SECRET_PARTS,
    _read,
    capture_repository,
    relative_path,
)
from alive.memory import GENERAL_MEMORY_TYPES
from alive.models import Event, Memory
from alive.sources import documents
from alive.workflows.context import Refused, require

BROWSER_EVENTS = ("browser.page_opened", "browser.dom_changed")
BROWSER_SECTION_CHARS = 2000
MAX_BROWSER_CHARS = 200000
MAX_COLLECTION_ITEMS = 256


def enumerate_repository(root, limit=CAPTURE_MAX_FILES):
    """Every non-directory entry under root; links are not followed. Refuses, never truncates."""
    root = Path(root)
    require(not root.is_symlink() and not root.is_junction(), "repository_root_link_refused")
    root = root.resolve(strict=True)
    require(root.is_dir(), "repository_root_required")
    found, refused = [], []

    def walk(directory, prefix):
        with os.scandir(directory) as entries:
            for entry in sorted(entries, key=lambda e: e.name):
                relative = prefix + entry.name
                if entry.is_dir(follow_symlinks=False) and not entry.is_junction():
                    if entry.name.casefold() not in SECRET_PARTS:
                        walk(entry.path, relative + "/")
                    continue
                try:
                    found.append(relative_path(relative))
                except Refused:
                    refused.append({"path": relative[:256], "reason": "repository_path_refused"})
                require(len(found) <= limit, "repository_too_many_files")

    walk(root, "")
    return found, refused


def repository_content(root, paths=None, *, limit=CAPTURE_MAX_FILES):
    """Capture an explicit path list, or every file when `paths` is None."""
    enumerated_refusals = []
    if paths is None:
        paths, enumerated_refusals = enumerate_repository(root, limit)
    require(len(paths) >= 1, "repository_nothing_to_capture")
    snapshot = capture_repository(
        "custody-capture",
        root,
        list(paths),
        max_files=max(1, min(len(paths), CAPTURE_MAX_FILES)),
        max_source_bytes=CAPTURE_MAX_BYTES,
    )
    omitted = [{"path": p, "reason": r} for p, r in snapshot.omitted] + enumerated_refusals
    return {
        "kind": "repository",
        "files": [
            {"path": f.path, "content": f.content, "sha256": f.sha256, "bytes": f.bytes}
            for f in snapshot.files
        ],
        "omitted": sorted(omitted, key=lambda o: (o["path"], o["reason"])),
    }


def document_content(file):
    """Parse one owner-chosen file with the same hardened reader repository capture uses."""
    path = Path(file)
    suffix = path.suffix.casefold()
    require(suffix != ".pdf", "document_format_unsupported_pdf_parser_not_installed")
    require(suffix in documents.FORMATS, "document_format_unsupported")
    require(not path.is_symlink() and not path.is_junction(), "document_link_refused")
    try:
        parent = path.resolve(strict=True).parent
        raw = _read(parent, path.name, documents.MAX_DOCUMENT_BYTES)
    except Refused as error:
        # The same categories on every platform, and in the document's own vocabulary.
        too_big = str(error) == "repository_file_size_limit"
        raise Refused("document_size_refused" if too_big else "document_unreadable") from None
    except OSError:
        # Never surface an operating-system message: it can name host paths.
        raise Refused("document_unreadable") from None
    return documents.extract(raw, documents.FORMATS[suffix])


def browser_sections(text):
    blocks, current, size = [], [], 0
    for line in text.split("\n"):
        if size + len(line) + 1 > BROWSER_SECTION_CHARS and current:
            blocks.append("\n".join(current))
            current, size = [], 0
        current.append(line[:BROWSER_SECTION_CHARS])
        size += len(line) + 1
    if current:
        blocks.append("\n".join(current))
    sections = []
    for block in blocks:
        if block.strip():
            sections.append(documents.make_section(len(sections), "", block, 0, 0))
    return sections


async def browser_content(kernel, event_id):
    """Prepare an already-captured observation. Nothing is fetched; nothing is navigated."""
    async with kernel.db.sessions() as session:
        event = await session.scalar(
            select(Event).where(Event.id == event_id, Event.instance_id == kernel.instance_id)
        )
    require(event is not None and event.event_type in BROWSER_EVENTS, "observation_not_found")
    payload = event.payload
    text = payload.get("text")
    require(type(text) is str and 0 < len(text) <= MAX_BROWSER_CHARS, "observation_text_refused")
    claimed = payload.get("text_sha256")
    actual = hashlib.sha256(text.encode()).hexdigest()
    require(claimed is None or claimed == actual, "observation_text_changed")
    sections = browser_sections(documents.clean(text))
    require(1 <= len(sections) <= documents.MAX_SECTIONS, "document_sections_refused")
    url = str(payload.get("url", ""))[:256]
    return {
        "kind": "browser",
        "observation_event_id": event.id,
        "observation_id": str(payload.get("observation_id", ""))[:36],
        "origin": str(payload.get("permission_origin", ""))[:128],
        "url": url,
        "title": documents.clean(str(payload.get("title", "")))[:200],
        "observed_at": str(payload.get("observed_at", ""))[:40],
        "raw_sha256": actual,
        "raw_chars": len(text),
        "sections": sections,
        "truncated": any(s["truncated"] for s in sections),
    }


def sha256_text(value):
    return hashlib.sha256(value.encode()).hexdigest()


async def collection_content(kernel, *, memory_types=GENERAL_MEMORY_TYPES, limit=64, query=""):
    """Freeze a set of existing memories by id and content hash. No content is copied."""
    require(1 <= limit <= MAX_COLLECTION_ITEMS, "collection_limit_refused")
    require(type(query) is str and len(query) <= 256, "collection_query_refused")
    async with kernel.db.sessions() as session:
        rows = await session.scalars(
            select(Memory)
            .where(Memory.instance_id == kernel.instance_id, Memory.memory_type.in_(memory_types))
            .order_by(Memory.created_at.desc(), Memory.id)
            .limit(limit * 4 if query else limit)
        )
        rows = rows.all()
    terms = [t for t in re.split(r"\W+", query.casefold()) if t]
    if terms:
        rows = [r for r in rows if any(t in r.content.casefold() for t in terms)]
    rows = rows[:limit]
    require(rows, "collection_empty")
    return {
        "kind": "collection",
        "items": [
            {
                "memory_id": r.id,
                "content_sha256": sha256_text(r.content),
                "memory_type": r.memory_type,
            }
            for r in rows
        ],
    }, [{"memory_id": r.id, "preview": unicodedata.normalize("NFKC", r.content[:80])} for r in rows]
