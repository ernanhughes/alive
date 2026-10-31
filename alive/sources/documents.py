"""Bounded document parsing for owner-captured text, Markdown and HTML.

Untrusted bytes are parsed once, here, on the trusted host at capture time. The owner then approves
what was actually extracted, and no workflow stage ever parses untrusted input.

PDF is not supported: no reviewed PDF parser is a dependency of ALIVE. Adding one is a supply-chain
decision (a new locked dependency in the image), so it is refused explicitly rather than guessed at.
"""

import hashlib
import re
import unicodedata
from pathlib import Path

import bs4
from bs4 import BeautifulSoup, Comment, NavigableString, Tag

from alive.workflows.context import require

FORMATS = {
    ".txt": "text",
    ".md": "markdown",
    ".markdown": "markdown",
    ".html": "html",
    ".htm": "html",
}
MAX_DOCUMENT_BYTES = 262144
MAX_SECTIONS = 512
MAX_SECTION_CHARS = 32768
TEXT_BLOCK_LINES = 60
HEADINGS = {f"h{n}" for n in range(1, 7)}
SKIPPED = {"script", "style", "noscript", "template", "svg", "head"}
BLOCKS = {"p", "div", "li", "br", "tr", "section", "article", "pre", "blockquote", "ul", "ol"}
MARKDOWN_HEADING = re.compile(r"^ {0,3}(#{1,6})[ \t]+(.+?)[ \t]*#*[ \t]*$")
FENCE = re.compile(r"^ {0,3}(```|~~~)")


def parser_identity():
    """What produced a section list. A different parser build means re-capture and re-approval."""
    source = Path(__file__).read_bytes().replace(b"\r\n", b"\n")
    return {
        "id": "alive-document-sections/v1",
        "sha256": hashlib.sha256(source + b"\0bs4=" + bs4.__version__.encode()).hexdigest(),
    }


def clean(text):
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    return "".join(
        c for c in text if c in "\n\t" or unicodedata.category(c) not in {"Cc", "Cf", "Cs"}
    )


def make_section(index, heading, text, line_start, line_end):
    text = clean(text).strip("\n")
    truncated = len(text) > MAX_SECTION_CHARS
    text = text[:MAX_SECTION_CHARS]
    return {
        "index": index,
        "heading": clean(heading)[:200],
        "text": text,
        "truncated": truncated,
        "char_count": len(text),
        "line_start": line_start,  # 1-based; 0 where the format has no meaningful lines (HTML)
        "line_end": line_end,
        "sha256": hashlib.sha256(text.encode()).hexdigest(),
    }


def markdown_sections(text):
    sections, heading, body, start, fence = [], "", [], 1, None
    lines = text.split("\n")

    def flush(end):
        if heading or any(line.strip() for line in body):
            sections.append(make_section(len(sections), heading, "\n".join(body), start, end))

    for number, line in enumerate(lines, 1):
        marker = FENCE.match(line)
        if marker:
            fence = None if fence == marker.group(1) else (fence or marker.group(1))
        found = None if fence else MARKDOWN_HEADING.match(line)
        if found:
            flush(number - 1)
            heading, body, start = found.group(2), [], number
        else:
            body.append(line)
    flush(len(lines))
    return sections


def text_sections(text):
    lines = text.split("\n")
    sections = []
    for offset in range(0, len(lines), TEXT_BLOCK_LINES):
        block = lines[offset : offset + TEXT_BLOCK_LINES]
        if any(line.strip() for line in block):
            sections.append(
                make_section(len(sections), "", "\n".join(block), offset + 1, offset + len(block))
            )
    return sections


def html_sections(markup):
    soup = BeautifulSoup(markup, "html.parser")
    sections, state = [], {"heading": "", "parts": []}

    def flush():
        body = re.sub(r"[ \t]+", " ", "".join(state["parts"]))
        body = re.sub(r"\n\s*\n+", "\n", body).strip()
        if state["heading"] or body:
            sections.append(make_section(len(sections), state["heading"], body, 0, 0))
        state["heading"], state["parts"] = "", []

    def walk(node):
        for child in node.children:
            if isinstance(child, Comment):
                continue
            if isinstance(child, NavigableString):
                state["parts"].append(str(child))
            elif isinstance(child, Tag):
                if child.name in SKIPPED:
                    continue
                if child.name in HEADINGS:
                    flush()
                    state["heading"] = re.sub(r"\s+", " ", child.get_text(" ", strip=True))
                    continue
                walk(child)
                if child.name in BLOCKS:
                    state["parts"].append("\n")

    walk(soup)
    flush()
    return sections


def extract(raw, fmt):
    """Parse bounded bytes into sections. Every refusal is a named category."""
    require(fmt in set(FORMATS.values()), "document_format_unsupported")
    require(type(raw) is bytes and 0 < len(raw) <= MAX_DOCUMENT_BYTES, "document_size_refused")
    require(b"\x00" not in raw, "document_binary")
    try:
        text = raw.decode("utf-8")
    except UnicodeDecodeError:
        require(False, "document_encoding")
    text = clean(text)
    sections = {"markdown": markdown_sections, "text": text_sections, "html": html_sections}[fmt](
        text
    )
    require(1 <= len(sections) <= MAX_SECTIONS, "document_sections_refused")
    return {
        "kind": "document",
        "format": fmt,
        "raw_sha256": hashlib.sha256(raw).hexdigest(),
        "raw_bytes": len(raw),
        "parser": parser_identity(),
        "sections": sections,
        "truncated": any(s["truncated"] for s in sections),
    }
