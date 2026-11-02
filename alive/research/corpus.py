"""Deterministic search/read over an owner-approved captured corpus.

Only captured source bytes are read. This module never fetches, executes or writes documents.
"""

from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass

TOKEN = re.compile(r"[A-Za-z0-9_]{2,}")


@dataclass(frozen=True)
class Document:
    document_id: str
    path: str
    content: str
    line_offsets: tuple[tuple[int, int], ...]


def _tokens(text: str) -> list[str]:
    return [term.lower() for term in TOKEN.findall(text)]


def _line_offsets(text: str) -> tuple[tuple[int, int], ...]:
    offsets = []
    position = 0
    for line in text.splitlines(keepends=True):
        end = position + len(line)
        offsets.append((position, end))
        position = end
    if not offsets:
        offsets = [(0, 0)]
    return tuple(offsets)


def documents(source_content: dict) -> list[Document]:
    found = []
    for item in source_content.get("files", []):
        path = str(item["path"])
        content = str(item["content"])
        found.append(Document(path, path, content, _line_offsets(content)))
    return found


def _snippet(document: Document, terms: list[str]) -> tuple[str, int, int]:
    lines = document.content.splitlines()
    if not lines:
        return "", 1, 1
    best = (0, 0)
    best_score = -1
    for index, line in enumerate(lines):
        lower = line.lower()
        score = sum(lower.count(term) for term in terms)
        if score > best_score:
            best = (index, index)
            best_score = score
    start = max(0, best[0] - 1)
    end = min(len(lines), best[1] + 2)
    return "\n".join(lines[start:end])[:2500], start + 1, end


def search(source_content: dict, query: str, *, limit: int = 5) -> list[dict]:
    terms = _tokens(query)
    if not terms:
        return []
    results = []
    for document in documents(source_content):
        lower = document.content.lower()
        counts = {term: lower.count(term) for term in terms}
        score = sum(counts.values())
        if score <= 0:
            continue
        snippet, start, end = _snippet(document, terms)
        results.append(
            {
                "document_id": document.document_id,
                "path": document.path,
                "snippet": snippet,
                "line_start": start,
                "line_end": end,
                "score": score,
            }
        )
    results.sort(key=lambda item: (-item["score"], item["document_id"]))
    return results[: max(1, min(limit, 5))]


def _sections(document: Document) -> list[tuple[str, int, int]]:
    lines = document.content.splitlines()
    sections: list[tuple[str, int, int]] = []
    heading = document.path
    start = 1
    for index, line in enumerate(lines, start=1):
        if re.match(r"^\s{0,3}#{1,6}\s+", line):
            if index > start:
                sections.append((heading, start, index - 1))
            heading = line.strip()[:200]
            start = index
    if lines:
        sections.append((heading, start, len(lines)))
    return sections or [(document.path, 1, 1)]


def read(source_content: dict, document_id: str, section: int | None = None) -> dict:
    for document in documents(source_content):
        if document.document_id != document_id:
            continue
        sections = _sections(document)
        if section is not None:
            if section < 0 or section >= len(sections):
                raise ValueError("section_out_of_range")
            heading, start, end = sections[section]
            lines = document.content.splitlines()
            text = "\n".join(lines[start - 1 : end])
            return {
                "document_id": document.document_id,
                "path": document.path,
                "section": section,
                "heading": heading,
                "line_start": start,
                "line_end": end,
                "text": text[:12000],
                "sha256": hashlib.sha256(text.encode()).hexdigest(),
                "sections": len(sections),
            }
        return {
            "document_id": document.document_id,
            "path": document.path,
            "section": None,
            "heading": sections[0][0],
            "line_start": 1,
            "line_end": max(1, len(document.content.splitlines())),
            "text": document.content[:12000],
            "sha256": hashlib.sha256(document.content.encode()).hexdigest(),
            "sections": len(sections),
        }
    raise ValueError("document_not_found")


def catalog(source_content: dict) -> list[dict]:
    return [
        {
            "document_id": document.document_id,
            "path": document.path,
            "bytes": len(document.content.encode()),
            "headings": [heading for heading, _, _ in _sections(document)][:12],
        }
        for document in documents(source_content)
    ]


__all__ = ["catalog", "documents", "read", "search"]
