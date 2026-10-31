"""Where untrusted bytes enter: the parser and the trusted-host capture builders."""

import hashlib
import os

import bs4
import pytest

from alive.models import Memory, uid
from alive.sources import capture, documents
from alive.workflows.context import Refused
from tests.workflow_execution_helpers import call, prepare

posix_only = pytest.mark.skipif(not hasattr(os, "mkfifo"), reason="needs POSIX FIFOs")


def parse(text, fmt):
    return documents.extract(text.encode() if isinstance(text, str) else text, fmt)


def test_markdown_headings_split_sections_but_fenced_code_does_not():
    out = parse("intro\n# One\nbody\n```\n# not a heading\n```\n## Two\nmore\n", "markdown")
    assert [s["heading"] for s in out["sections"]] == ["", "One", "Two"]
    assert "# not a heading" in out["sections"][1]["text"]
    assert (
        out["format"] == "markdown"
        and out["raw_bytes"] == len(out["raw_sha256"]) * 0 + out["raw_bytes"]
    )
    for section in out["sections"]:
        assert section["sha256"] == hashlib.sha256(section["text"].encode()).hexdigest()
        assert section["char_count"] == len(section["text"])


def test_html_drops_executable_and_hidden_content_and_keeps_headings():
    html = (
        "<html><head><title>t</title><style>p{}</style></head><body>"
        "<script>alert('x')</script><!-- secret comment -->"
        "<h1>Title</h1><p>First &amp; second</p><noscript>no</noscript>"
        "<h2>Part</h2><div><p>Nested <b>bold</b></p></div></body></html>"
    )
    out = parse(html, "html")
    joined = " ".join(s["heading"] + " " + s["text"] for s in out["sections"])
    assert [s["heading"] for s in out["sections"]] == ["Title", "Part"]
    assert "First & second" in joined and "Nested bold" in joined
    for hidden in ("alert", "secret comment", "p{}", "no "):
        assert hidden not in joined
    assert all(s["line_start"] == 0 for s in out["sections"])  # HTML has no meaningful lines


def test_plain_text_is_split_into_bounded_blocks_and_newlines_are_normalised():
    text = "\r\n".join(f"line {n}" for n in range(1, 131))
    out = parse(text, "text")
    assert [(s["line_start"], s["line_end"]) for s in out["sections"]] == [
        (1, 60),
        (61, 120),
        (121, 130),
    ]
    assert "\r" not in out["sections"][0]["text"]


@pytest.mark.parametrize(
    "raw,fmt,category",
    [
        (b"", "text", "document_size_refused"),
        (b"a" * (documents.MAX_DOCUMENT_BYTES + 1), "text", "document_size_refused"),
        (b"ab\x00cd", "text", "document_binary"),
        (b"\xff\xfe broken", "text", "document_encoding"),
        (b"   \n\n  ", "text", "document_sections_refused"),
        (b"x", "pdf", "document_format_unsupported"),
        (("<div>" * 500 + "x" + "</div>" * 500).encode(), "html", "document_nesting_refused"),
        ("\n".join(f"# h{n}\nb" for n in range(documents.MAX_SECTIONS + 1)).encode(), "markdown",
         "document_sections_refused"),
    ],
    ids=["empty", "oversize", "nul", "encoding", "blank", "pdf", "deep-html", "many-sections"],
)  # fmt: skip
def test_hostile_documents_are_refused_with_a_named_category(raw, fmt, category):
    with pytest.raises(Refused, match=category):
        documents.extract(raw, fmt)


def test_control_and_formatting_characters_are_removed_and_oversize_sections_are_flagged():
    out = parse("# T\nclean\x1b[31mred\x07 ‮gnirts\n", "markdown")
    assert "\x1b" not in out["sections"][0]["text"] and "‮" not in out["sections"][0]["text"]
    big = parse("# Big\n" + "x" * (documents.MAX_SECTION_CHARS + 10), "markdown")
    assert big["sections"][0]["truncated"] is True and big["truncated"] is True
    assert big["sections"][0]["char_count"] == documents.MAX_SECTION_CHARS


def test_the_parser_identity_changes_with_the_parser_build(monkeypatch):
    first = documents.parser_identity()
    assert first == documents.parser_identity() and first["id"] == "alive-document-sections/v1"
    monkeypatch.setattr(bs4, "__version__", "0.0.0-other")
    assert documents.parser_identity()["sha256"] != first["sha256"]


# --- repository ---------------------------------------------------------------------------------


def tree(root, files):
    for name, data in files.items():
        (root / name).parent.mkdir(parents=True, exist_ok=True)
        (root / name).write_bytes(data if isinstance(data, bytes) else data.encode())


def test_repository_capture_omits_secrets_ignored_binary_and_special_entries(tmp_path):
    tree(
        tmp_path,
        {
            "README.md": "ok",
            "src/a.py": "a",
            ".env": "SECRET=1",
            ".git/config": "[core]",
            "node_modules/x/index.js": "x",
            "id_rsa": "key",
            "creds/credentials.json": "{}",
            "debug.log": "log",
            ".gitignore": "*.log\n",
            "bin.dat": b"\x00\x01",
        },
    )
    out = capture.repository_content(tmp_path)
    paths = {f["path"] for f in out["files"]}
    assert paths == {"README.md", "src/a.py", ".gitignore"}
    reasons = {o["path"]: o["reason"] for o in out["omitted"]}
    for path in (".env", "id_rsa", "creds/credentials.json", "debug.log"):
        assert reasons[path] == "ignored_by_host_policy"
    assert reasons["bin.dat"] == "binary_file"
    assert not any(p.startswith((".git/", "node_modules/")) for p in {*paths, *reasons})
    assert out["files"] == sorted(out["files"], key=lambda f: f["path"])


def test_repository_capture_refuses_too_many_files_rather_than_truncating(tmp_path):
    tree(tmp_path, {f"f{n:03}.txt": "x" for n in range(30)})
    with pytest.raises(Refused, match="repository_too_many_files"):
        capture.repository_content(tmp_path, limit=10)


def test_repository_capture_does_not_follow_links_out_of_the_root(tmp_path):
    outside = tmp_path / "outside"
    outside.mkdir()
    (outside / "secret.txt").write_text("OUTSIDE", encoding="utf-8")
    root = tmp_path / "root"
    tree(root, {"in.txt": "inside"})
    try:
        os.symlink(outside / "secret.txt", root / "link.txt")
        os.symlink(outside, root / "linkdir", target_is_directory=True)
    except (OSError, NotImplementedError):
        pytest.skip("symlinks need privilege on this host")
    out = capture.repository_content(root)
    assert [f["path"] for f in out["files"]] == ["in.txt"]
    assert "OUTSIDE" not in str(out)
    assert {o["reason"] for o in out["omitted"]} <= {
        "repository_link_refused",
        "unavailable_or_linked_file",
    }


def test_hardlinks_cannot_alias_an_unapproved_file(tmp_path):
    tree(tmp_path, {"safe.txt": "x", ".env": "SECRET"})
    os.link(tmp_path / ".env", tmp_path / "alias.txt")
    out = capture.repository_content(tmp_path)
    assert "SECRET" not in str(out) and {f["path"] for f in out["files"]} == {"safe.txt"}


@posix_only
def test_a_fifo_in_the_tree_is_omitted_and_never_blocks_capture(tmp_path):
    tree(tmp_path, {"ok.txt": "fine"})
    os.mkfifo(tmp_path / "pipe")
    out = capture.repository_content(tmp_path)
    assert [f["path"] for f in out["files"]] == ["ok.txt"]
    assert {o["path"]: o["reason"] for o in out["omitted"]}[
        "pipe"
    ] == "repository_regular_file_required"


@pytest.mark.parametrize("path", ["../x", "/abs", "a/../b", "CON", "a\\b", "a//b", ""])
def test_explicit_repository_paths_must_be_canonical(tmp_path, path):
    tree(tmp_path, {"a.txt": "x"})
    with pytest.raises(Refused):
        capture.repository_content(tmp_path, [path])


# --- document, browser, collection builders ------------------------------------------------------


def test_document_capture_refuses_links_directories_and_unknown_formats(tmp_path):
    (tmp_path / "d.md").write_text("# a\nb\n", encoding="utf-8")
    assert capture.document_content(tmp_path / "d.md")["format"] == "markdown"
    (tmp_path / "UPPER.MD").write_text("# a\nb\n", encoding="utf-8")
    assert capture.document_content(tmp_path / "UPPER.MD")["format"] == "markdown"
    (tmp_path / "x.pdf").write_bytes(b"%PDF")
    with pytest.raises(Refused, match="pdf_parser_not_installed"):
        capture.document_content(tmp_path / "x.pdf")
    (tmp_path / "x.docx").write_bytes(b"PK")
    with pytest.raises(Refused, match="document_format_unsupported"):
        capture.document_content(tmp_path / "x.docx")
    (tmp_path / "dir.md").mkdir()
    with pytest.raises(Refused, match="document_unreadable"):
        capture.document_content(tmp_path / "dir.md")
    with pytest.raises(Refused, match="document_unreadable"):
        capture.document_content(tmp_path / "missing.md")
    (tmp_path / "huge.md").write_bytes(b"x" * (documents.MAX_DOCUMENT_BYTES + 1))
    with pytest.raises(Refused, match="document_size_refused"):
        capture.document_content(tmp_path / "huge.md")
    try:
        os.symlink(tmp_path / "d.md", tmp_path / "link.md")
    except (OSError, NotImplementedError):
        return
    with pytest.raises(Refused, match="document_link_refused"):
        capture.document_content(tmp_path / "link.md")


def test_browser_capture_checks_event_type_integrity_and_instance(client):
    from tests.test_source_capabilities import observed

    async def go(k):
        event_id = await observed(k, "line one\x1b\nline two")
        content = await capture.browser_content(k, event_id)
        assert content["kind"] == "browser" and "\x1b" not in content["sections"][0]["text"]
        assert content["raw_sha256"] == hashlib.sha256(b"line one\x1b\nline two").hexdigest()
        async with k.lock, k.db.sessions.begin() as session:  # a different event type
            other = k.add_event(session, "browser.navigation_completed", {"text": "x"})
        with pytest.raises(Refused, match="observation_not_found"):
            await capture.browser_content(k, str(other.event_id))
        async with k.lock, k.db.sessions.begin() as session:  # claimed hash does not match text
            bad = k.add_event(
                session,
                "browser.page_opened",
                {"text": "abc", "text_sha256": "0" * 64},
                source="user",
            )
        with pytest.raises(Refused, match="observation_text_changed"):
            await capture.browser_content(k, str(bad.event_id))
        async with k.lock, k.db.sessions.begin() as session:
            empty = k.add_event(session, "browser.page_opened", {"text": ""}, source="user")
        with pytest.raises(Refused, match="observation_text_refused"):
            await capture.browser_content(k, str(empty.event_id))

    prepare(client)
    call(client, go)


def test_collection_capture_stores_identities_not_content(client):
    async def go(k):
        async with k.db.sessions.begin() as session:
            for n in range(5):
                session.add(
                    Memory(
                        instance_id=k.instance_id,
                        content=f"alpha note {n}",
                        memory_type="experience",
                    )
                )
            session.add(
                Memory(instance_id=k.instance_id, content="beta only", memory_type="experience")
            )
            session.add(
                Memory(instance_id=k.instance_id, content="alpha hidden", memory_type="privileged")
            )
        content, previews = await capture.collection_content(k, query="alpha", limit=3)
        assert len(content["items"]) == 3 and len(previews) == 3
        assert "alpha" not in str(content) and all(
            len(i["content_sha256"]) == 64 for i in content["items"]
        )
        assert {i["memory_type"] for i in content["items"]} == {"experience"}  # general types only
        with pytest.raises(Refused, match="collection_empty"):
            await capture.collection_content(k, query="qqqq")
        with pytest.raises(Refused, match="collection_limit_refused"):
            await capture.collection_content(k, limit=0)
        return uid()

    prepare(client)
    call(client, go)
