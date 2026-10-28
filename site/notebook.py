"""Deterministic ALIVE Notebook conversion and provenance checker.

No model writes any chapter text. A chapter body is an exact slice of a canonical document
under ``docs/``; the front matter records the source path, the last commit that touched it and
the content hashes. ``check`` fails when a source drifts, a chapter differs from a fresh
conversion, or a recorded
relationship quote is not in both the source and the capturable part of the chapter.

    python site/notebook.py convert   # rewrite site/content/chapters/*.md
    python site/notebook.py check     # provenance + relationship quotes
    python site/notebook.py check --public site/public   # also verify built HTML
"""

import argparse
import hashlib
import json
import re
import subprocess
import sys
import tomllib
from html.parser import HTMLParser
from pathlib import Path

SITE = Path(__file__).resolve().parent
ROOT = SITE.parent
SPEC = SITE / "notebook" / "chapters.json"
RELATIONS = SITE / "notebook" / "relations.json"
CONTENT = SITE / "content" / "chapters"
PREAMBLE = "__preamble__"
GENERATOR = "site/notebook.py convert"

# Wording that a chapter must never gain relative to its source.
STRONGER = re.compile(
    r"\b(improves?|outperforms?|proves?|proven|superior|validated|guarantees?)\b"
    r"|advantage (?:is )?demonstrated",
    re.I,
)
QUALIFIER = re.compile(
    r"not (?:demonstrated|run|claimed|established)|unestablished|candidate|does not establish"
    r"|limitation|scripted|synthetic|controlled|frozen",
    re.I,
)


def load_spec():
    return json.loads(SPEC.read_text(encoding="utf-8"))


def normalise(data):
    """LF line endings so hashes agree across checkouts."""
    return data.replace(b"\r\n", b"\n")


def sha256(data):
    return hashlib.sha256(data).hexdigest()


def git(*args):
    return subprocess.run(["git", "-C", str(ROOT), *args], capture_output=True, check=True).stdout


def source_bytes(doc):
    return normalise((ROOT / doc).read_bytes())


def source_commit(doc):
    if git("rev-parse", "--is-shallow-repository").decode().strip() != "false":
        raise ValueError("provenance requires full Git history; fetch with --unshallow")
    commit = git("log", "-n1", "--format=%H", "--", doc).decode().strip()
    if not re.fullmatch(r"[0-9a-f]{40}", commit):
        raise ValueError(f"no source history for {doc}")
    return commit


def split_doc(text):
    """Return the H1 title and an ordered ``{part: text}`` of the preamble and ``##`` sections."""
    lines = text.split("\n")
    if not lines or not lines[0].startswith("# "):
        raise ValueError("source document must start with a single H1")
    parts, name, buffer = {}, PREAMBLE, []
    for line in lines[1:]:
        if line.startswith("## "):
            parts[name] = "\n".join(buffer).strip("\n")
            name, buffer = line[3:].strip(), [line]
        else:
            buffer.append(line)
    parts[name] = "\n".join(buffer).strip("\n")
    return lines[0][2:].strip(), parts


def render_body(doc, part_names):
    title, parts = split_doc(source_bytes(doc).decode("utf-8"))
    missing = [name for name in part_names if name not in parts]
    if missing:
        raise ValueError(f"{doc} has no part {missing}")
    return title, "\n\n".join(parts[name] for name in part_names) + "\n"


def toml_value(value):
    return json.dumps(value, ensure_ascii=False)


def chapter_metadata(chapter, commit):
    doc = chapter["doc"]
    title, body = render_body(doc, chapter["parts"])
    return {
        "title": title,
        "slug": chapter["id"],
        "chapter_id": chapter["id"],
        "alive_stage": chapter["alive_stage"],
        "source_doc": doc,
        "source_parts": chapter["parts"],
        "source_commit": commit,
        "source_sha256": sha256(source_bytes(doc)),
        "body_sha256": sha256(body.encode("utf-8")),
        "generated_by": GENERATOR,
    }


def chapter_file(chapter, commit):
    meta = chapter_metadata(chapter, commit)
    _, body = render_body(chapter["doc"], chapter["parts"])
    header = "\n".join(f"{key} = {toml_value(value)}" for key, value in meta.items())
    return f"+++\n{header}\n+++\n{body}"


def convert():
    spec = load_spec()
    CONTENT.mkdir(parents=True, exist_ok=True)
    wanted = set()
    for chapter in spec["chapters"]:
        path = CONTENT / f"{chapter['id']}.md"
        wanted.add(path.name)
        path.write_text(
            chapter_file(chapter, source_commit(chapter["doc"])), encoding="utf-8", newline="\n"
        )
    for stale in CONTENT.glob("*.md"):
        if stale.name not in wanted:
            stale.unlink()
    return sorted(wanted)


def read_chapter(path):
    text = normalise(path.read_bytes()).decode("utf-8")
    if not text.startswith("+++\n"):
        raise ValueError("missing TOML front matter")
    header, _, body = text[4:].partition("\n+++\n")
    return tomllib.loads(header), body


def squash(text):
    return re.sub(r"\s+", " ", text).strip()


def plain(markdown):
    """Approximate the visible text of inline Markdown (backticks, emphasis, links, bullets)."""
    text = re.sub(r"\[([^\]]+)\]\([^)]*\)", r"\1", markdown)
    text = re.sub(r"(?m)^(#+ |- |\d+\. )", "", text)
    return squash(text.replace("`", "").replace("**", ""))


def diff_lines(expected, actual):
    want = [line for line in expected.split("\n") if line.strip()]
    have = [line for line in actual.split("\n") if line.strip()]
    return [line for line in have if line not in want], [line for line in want if line not in have]


def check_chapter(chapter, problems):
    name = chapter["id"]
    path = CONTENT / f"{name}.md"
    if not path.exists():
        problems.append(f"{name}: chapter file is missing; run convert")
        return None
    try:
        meta, body = read_chapter(path)
    except ValueError as error:
        problems.append(f"{name}: {error}")
        return None
    doc = chapter["doc"]
    if not (ROOT / doc).exists():
        problems.append(f"{name}: source {doc} is missing")
        return None
    if meta.get("source_doc") != doc or meta.get("chapter_id") != name:
        problems.append(f"{name}: front matter id/source does not match chapters.json")
    try:
        expected_meta = chapter_metadata(chapter, source_commit(doc))
    except (ValueError, subprocess.CalledProcessError) as error:
        problems.append(f"{name}: cannot verify canonical metadata: {error}")
        return body
    for key in sorted(set(meta) - set(expected_meta)):
        problems.append(f"{name}: unauthorized front matter key: {key}")
    for key, value in expected_meta.items():
        if type(meta.get(key)) is not type(value) or meta.get(key) != value:
            problems.append(f"{name}: front matter {key} differs from canonical generation")
    current = sha256(source_bytes(doc))
    if meta.get("source_sha256") != current:
        problems.append(f"{name}: source {doc} changed since conversion (hash drift)")
    commit = meta.get("source_commit", "")
    if not isinstance(commit, str) or not re.fullmatch(r"[0-9a-f]{40}", commit):
        problems.append(f"{name}: invalid source_commit")
        return body
    try:
        pinned = sha256(normalise(git("show", f"{commit}:{doc}")))
    except subprocess.CalledProcessError:
        problems.append(f"{name}: source commit {commit[:12]} does not contain {doc}")
    else:
        if pinned != meta.get("source_sha256"):
            problems.append(f"{name}: recorded hash does not match {doc} at {commit[:12]}")
    if sha256(body.encode("utf-8")) != meta.get("body_sha256"):
        problems.append(f"{name}: chapter body was edited after conversion")
    try:
        _, expected = render_body(doc, chapter["parts"])
    except ValueError as error:
        problems.append(f"{name}: {error}")
        return body
    if body != expected:
        added, removed = diff_lines(expected, body)
        for line in added:
            kind = "stronger than source" if STRONGER.search(line) else "not in source"
            problems.append(f"{name}: line {kind}: {line.strip()[:100]}")
        for line in removed:
            kind = "qualifier removed" if QUALIFIER.search(line) else "source line removed"
            problems.append(f"{name}: {kind}: {line.strip()[:100]}")
        if not added and not removed:
            problems.append(f"{name}: body differs from a fresh conversion (ordering/whitespace)")
    for target in re.findall(r"\]\(([^)]*)\)", body):
        if not re.match(r"(https?://|#)", target):
            problems.append(f"{name}: relative link would not resolve on the site: {target}")
    return body


def captured_text(chapter_id):
    """Block-structured text of a chapter as the companion's visible-text capture sees it."""
    spec = load_spec()
    chapter = next(c for c in spec["chapters"] if c["id"] == chapter_id)
    title, body = render_body(chapter["doc"], chapter["parts"])
    lines = [title]
    for block in re.split(r"\n\s*\n", body.strip()):
        item = None
        for line in block.split("\n"):
            if item is None or line.startswith(("- ", "#", "|")):
                if item is not None:
                    lines.append(item)
                item = line
            else:
                item += " " + line.strip()
        lines.append(item)
    return "\n".join(plain(line) for line in lines if line.strip())


def visible_text(meta_title, body):
    return plain(f"{meta_title}\n{body}")


def check_relations(spec, bodies, problems):
    data = json.loads(RELATIONS.read_text(encoding="utf-8"))
    window = spec["capture_window"]
    chapters = {chapter["id"]: chapter for chapter in spec["chapters"]}
    kinds = {r["kind"] for r in data["relations"] if r["authenticity"] == "real"}
    for needed in ("supersession", "abstention"):
        if needed not in kinds:
            problems.append(f"relations: no real {needed} relationship recorded")
    for relation in data["relations"]:
        label = relation["id"]
        if relation["authenticity"] not in ("real", "synthetic"):
            problems.append(f"{label}: authenticity must be real or synthetic")
            continue
        if relation["authenticity"] == "synthetic":
            continue
        for side in ("older", "newer"):
            ref = relation[side]
            chapter = chapters.get(ref["chapter"])
            if not chapter or ref["chapter"] not in bodies:
                problems.append(f"{label}: {side} chapter {ref['chapter']} is unknown")
                continue
            source = squash(source_bytes(chapter["doc"]).decode("utf-8"))
            shown = visible_text(split_title(chapter), bodies[ref["chapter"]])
            for quote in ref["quotes"]:
                if squash(quote) not in source:
                    problems.append(
                        f"{label}: {side} quote is not in {chapter['doc']}: {quote[:60]}"
                    )
                if plain(quote) not in shown[:window]:
                    problems.append(
                        f"{label}: {side} quote is outside the first {window} captured characters"
                    )
        for term in relation.get("shared_terms", []):
            for side in ("older", "newer"):
                if not any(term in plain(q).lower() for q in relation[side]["quotes"]):
                    problems.append(f"{label}: shared term {term!r} is not in the {side} quotes")
    return data


def split_title(chapter):
    return split_doc(source_bytes(chapter["doc"]).decode("utf-8"))[0]


class Capturable(HTMLParser):
    """Collect the text a ``main``-rooted capture would see, noting excluded regions."""

    SKIP = {"script", "style", "noscript", "nav", "input", "textarea", "select"}

    def __init__(self):
        super().__init__()
        self.depth, self.skip, self.chunks = 0, 0, []
        self.main_count = 0
        self.foreign = []  # tags inside <main> that should be page chrome
        self.stack = []
        self.h1s, self.titles = [], []
        self.heading, self.page_title = None, None

    def handle_starttag(self, tag, attrs):
        if tag == "title":
            self.page_title = []
        if tag == "h1" and self.depth:
            self.heading = []
        if tag == "main" and not self.depth:
            self.main_count += 1
        if self.depth:
            if tag in ("header", "footer", "aside") or "toc" in dict(attrs).get("class", ""):
                self.foreign.append(tag)
            self.depth += 1 if tag not in ("br", "hr", "img", "meta", "link") else 0
        elif tag == "main":
            self.depth = 1
        if self.depth and tag in self.SKIP:
            self.skip += 1
            self.stack.append(tag)

    def handle_endtag(self, tag):
        if tag == "title" and self.page_title is not None:
            self.titles.append(squash("".join(self.page_title)))
            self.page_title = None
        if tag == "h1" and self.heading is not None:
            self.h1s.append(squash("".join(self.heading)))
            self.heading = None
        if self.stack and self.stack[-1] == tag:
            self.stack.pop()
            self.skip -= 1
        if self.depth and tag not in ("br", "hr", "img", "meta", "link"):
            self.depth -= 1

    def handle_data(self, data):
        if self.page_title is not None:
            self.page_title.append(data)
        if self.heading is not None:
            self.heading.append(data)
        if self.depth and not self.skip:
            self.chunks.append(data)


def check_public(public, spec, bodies, problems):
    window = spec["capture_window"]
    for chapter in spec["chapters"]:
        page = Path(public) / "chapters" / chapter["id"] / "index.html"
        if not page.exists():
            problems.append(f"{chapter['id']}: built page {page} is missing")
            continue
        parser = Capturable()
        parser.feed(page.read_text(encoding="utf-8"))
        title = squash(split_title(chapter))
        if parser.h1s != [title]:
            problems.append(f"{chapter['id']}: rendered H1 differs from authoritative source title")
        if parser.titles != [title + " · The ALIVE Notebook"]:
            problems.append(
                f"{chapter['id']}: rendered document title differs from canonical title"
            )
        if parser.main_count != 1:
            problems.append(
                f"{chapter['id']}: expected exactly one <main>, found {parser.main_count}"
            )
        if parser.foreign:
            problems.append(
                f"{chapter['id']}: page chrome inside <main>: {sorted(set(parser.foreign))}"
            )
        text = squash(" ".join(parser.chunks))
        if len(text) > window:
            problems.append(
                f"{chapter['id']}: article is {len(text)} chars; only {window} are saved"
            )


def check(public=None):
    spec = load_spec()
    problems, bodies = [], {}
    for chapter in spec["chapters"]:
        body = check_chapter(chapter, problems)
        if body is not None:
            bodies[chapter["id"]] = body
    check_relations(spec, bodies, problems)
    if public:
        check_public(public, spec, bodies, problems)
    return problems


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("command", choices=["convert", "check"])
    parser.add_argument("--public", help="built Hugo output directory to verify as well")
    args = parser.parse_args(argv)
    if args.command == "convert":
        for name in convert():
            print("wrote", name)
        return 0
    problems = check(args.public)
    for problem in problems:
        print("FAIL", problem)
    print("provenance OK" if not problems else f"{len(problems)} problem(s)")
    return 1 if problems else 0


if __name__ == "__main__":
    sys.exit(main())
