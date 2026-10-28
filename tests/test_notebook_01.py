"""ALIVE-NOTEBOOK-01: provenance of the Hugo notebook and cross-page research over its chapters.

Everything here is deterministic and local: chapters are exact slices of docs/, memories are
saved from reviewed snapshots (no model-written note), and no provider is reachable.
A relationship in site/notebook/relations.json is a human reading of verified quotes; ALIVE's
deterministic layer does not judge supersession or validity (see the UNIMPLEMENTED test).
"""

import importlib.util
import json
import shutil
from pathlib import Path

import pytest

from alive.web_experience import NOTEBOOK_CHAPTERS, PAGES
from tests.test_research_memory import goal, grant, post, snapshot

SITE = Path(__file__).resolve().parents[1] / "site"
spec = importlib.util.spec_from_file_location("notebook", SITE / "notebook.py")
nb = importlib.util.module_from_spec(spec)
spec.loader.exec_module(nb)

GOAL = "Trace how ALIVE's research claims changed between milestones"
RELATIONS = {r["id"]: r for r in json.loads(nb.RELATIONS.read_text(encoding="utf-8"))["relations"]}


def url(chapter, host="127.0.0.1"):
    return f"http://{host}:1313/chapters/{chapter}/"


class Journey:
    """A researcher reading chapters in order, saving some as research memories."""

    def __init__(self, client, instruction=GOAL):
        self.client = client
        self.goal = goal(client, instruction)
        self.shots, self.memories = {}, {}

    def read(self, chapter):
        text = nb.captured_text(chapter)
        grant_row = grant(self.client, self.goal["id"], url(chapter))
        self.shots[chapter] = snapshot(self.client, grant_row, url(chapter), text)
        return self.shots[chapter]["snapshot"]["id"]

    def save(self, chapter):
        saved = post(self.client, "/research/memories", {"snapshot_id": self.read(chapter)})
        self.memories[chapter] = saved
        return saved

    def retrieve(self, chapter):
        shot = self.shots.get(chapter) or None
        snapshot_id = shot["snapshot"]["id"] if shot else self.read(chapter)
        return post(self.client, "/research/retrieve", {"snapshot_id": snapshot_id})

    def connect(self, current, historical):
        snapshot_id = self.shots[current]["snapshot"]["id"]
        memory_id = self.memories[historical]["id"]
        return post(
            self.client,
            "/research/connections",
            {"snapshot_id": snapshot_id, "memory_id": memory_id},
        )["data"]


@pytest.fixture
def no_provider(monkeypatch):
    async def forbidden(*args, **kwargs):
        raise AssertionError("a notebook test reached a model provider")

    monkeypatch.setattr("alive.web_experience.MetaProvider.structured", forbidden)


# --- provenance -------------------------------------------------------------------------


def test_committed_chapters_pass_the_provenance_check():
    assert nb.check() == []


def tampered_copy(tmp_path, monkeypatch, chapter_id, edit):
    content = tmp_path / "chapters"
    shutil.copytree(nb.CONTENT, content)
    path = content / f"{chapter_id}.md"
    path.write_text(edit(path.read_text(encoding="utf-8")), encoding="utf-8", newline="\n")
    monkeypatch.setattr(nb, "CONTENT", content)
    return nb.check()


def test_rewriting_a_result_more_strongly_than_its_source_is_rejected(tmp_path, monkeypatch):
    weak = "Retrieval advantage: **NOT DEMONSTRATED**."
    problems = tampered_copy(
        tmp_path,
        monkeypatch,
        "alive-12-status",
        lambda text: text.replace(weak, "ALIVE improves research retrieval."),
    )
    joined = "\n".join(problems)
    assert "line stronger than source: ALIVE improves research retrieval." in joined
    assert "qualifier removed" in joined
    assert "chapter body was edited after conversion" in joined


def test_source_or_hash_drift_is_rejected(tmp_path, monkeypatch):
    problems = tampered_copy(
        tmp_path,
        monkeypatch,
        "alive-13-status",
        lambda text: text.replace('source_sha256 = "', 'source_sha256 = "0'),
    )
    assert any("hash drift" in problem for problem in problems)
    assert any("recorded hash does not match" in problem for problem in problems)


def test_an_invented_quote_is_rejected(tmp_path, monkeypatch):
    data = json.loads(nb.RELATIONS.read_text(encoding="utf-8"))
    data["relations"][1]["newer"]["quotes"] = ["ALIVE improves research retrieval."]
    forged = tmp_path / "relations.json"
    forged.write_text(json.dumps(data), encoding="utf-8")
    monkeypatch.setattr(nb, "RELATIONS", forged)
    problems = nb.check()
    assert any("newer quote is not in docs/ALIVE-13.md" in problem for problem in problems)


def test_relations_cover_a_supersession_a_scoped_change_and_an_abstention():
    kinds = {r["kind"]: r for r in RELATIONS.values() if r["authenticity"] == "real"}
    assert {"supersession", "scoped_change", "abstention"} <= set(kinds)
    assert kinds["scoped_change"]["must_not_say"] == ["ALIVE improves research retrieval"]


def test_chapter_front_matter_has_stable_id_source_commit_and_hashes():
    for chapter in nb.load_spec()["chapters"]:
        meta, _ = nb.read_chapter(nb.CONTENT / f"{chapter['id']}.md")
        assert meta["chapter_id"] == meta["slug"] == chapter["id"]
        assert meta["source_doc"] == chapter["doc"]
        assert len(meta["source_commit"]) == 40
        assert len(meta["source_sha256"]) == len(meta["body_sha256"]) == 64


# --- authorisation ----------------------------------------------------------------------


def test_allowlist_is_exactly_the_notebook_chapters_on_loopback_port_1313():
    chapters = [c["id"] for c in nb.load_spec()["chapters"]]
    assert sorted(NOTEBOOK_CHAPTERS) == sorted(chapters)
    notebook = {page for page in PAGES if ":1313/" in page}
    assert notebook == {
        url(chapter, host) for chapter in chapters for host in ("127.0.0.1", "localhost")
    }
    assert not any("*" in page for page in PAGES)


def test_unlisted_notebook_urls_cannot_be_granted(client):
    g = goal(client, GOAL)
    body = {"goal_id": g["id"], "tab_key": "notebook-tab-1", "approved": True}
    granted = client.post(
        "/api/v1/browser-experience/grants", json=body | {"url": url("alive-12-status")}
    )
    assert granted.status_code == 200, granted.text
    for bad in (
        "http://127.0.0.1:1313/chapters/alive-12-status",
        "http://127.0.0.1:1313/chapters/not-a-chapter/",
        "http://127.0.0.1:1314/chapters/alive-12-status/",
        "http://127.0.0.1:1313/",
    ):
        response = client.post(
            "/api/v1/browser-experience/grants",
            json=body | {"url": bad},
        )
        assert response.status_code >= 400, bad


# --- cross-page retrieval ---------------------------------------------------------------


def test_cross_page_retrieval_returns_the_earlier_chapter_with_exact_source_text(
    client, no_provider
):
    """R1: reading ALIVE-13 recalls the ALIVE-12 chapter saved earlier, among distractors."""
    journey = Journey(client)
    target = journey.save("alive-12-status")
    journey.save("alive-11-corrections")
    journey.save("alive-14-status")
    result = journey.retrieve("alive-13-what-was-wrong")
    assert result["abstained"] is False
    first = result["results"][0]
    assert first["memory_id"] == target["id"]
    assert first["source_url"] == url("alive-12-status")
    assert first["source_url"] != url("alive-13-what-was-wrong")
    text = nb.captured_text("alive-12-status")
    assert first["sha256"] == target["data"]["sha256"]
    assert first["excerpt"] in text

    connection = journey.connect("alive-13-what-was-wrong", "alive-12-status")
    assert connection["inference_calls"] == 0
    assert connection["model"] == "deterministic-lexical-connection-v1"
    assert connection["relation_type"] == "topic_overlap_candidate"
    assert connection["status"] == "candidate"
    assert "same_concept" in connection["shared_terms"]
    assert connection["current_quote"] in nb.captured_text("alive-13-what-was-wrong")
    assert connection["historical_quote"] in text
    assert connection["quote_validation"] == {"current_exact": True, "historical_exact": True}
    assert "does not establish" in connection["explanation"]
    # The candidate says the pages overlap lexically. Whether R1 is a supersession is a human
    # reading (relations.json); ALIVE makes no such judgement.
    assert "supersed" not in connection["explanation"].lower()


def test_scoped_change_pair_is_retrieved_within_top_three_but_not_ranked_first(client, no_provider):
    """R2: a measured limitation. The ALIVE-14 chapter outranks the ALIVE-12 predecessor."""
    journey = Journey(client)
    target = journey.save("alive-12-status")
    journey.save("alive-11-corrections")
    journey.save("alive-14-status")
    result = journey.retrieve("alive-13-status")
    ids = [row["memory_id"] for row in result["results"]]
    assert target["id"] in ids
    assert ids[0] != target["id"]


# --- abstention -------------------------------------------------------------------------


def test_retrieval_abstains_without_an_eligible_memory(client, no_provider):
    journey = Journey(client)
    journey.save("alive-12-status")
    # A chapter never retrieves itself, even when it is the only saved memory.
    assert journey.retrieve("alive-12-status")["abstained"] is True
    # Memory is goal-scoped: the same chapter under another goal sees nothing.
    other = Journey(client, "Design a Python tutorial")
    assert other.retrieve("alive-13-what-was-wrong")["abstained"] is True


def test_withdrawn_memory_is_not_retrieved(client, no_provider):
    journey = Journey(client)
    target = journey.save("alive-12-status")
    assert journey.retrieve("alive-13-what-was-wrong")["abstained"] is False
    post(client, f"/research/memories/{target['id']}/withdraw", {})
    assert journey.retrieve("alive-13-what-was-wrong")["abstained"] is True


def terminology_only_pair(client):
    journey = Journey(client)
    journey.save("alive-11-corrections")
    journey.read("alive-14-status")
    return journey.connect("alive-14-status", "alive-11-corrections")


def test_terminology_only_pair_is_shown_as_a_lexical_candidate_never_as_support(
    client, no_provider
):
    """R3: the real pair that shares 'paid' and 'calls' but establishes no relationship."""
    connection = terminology_only_pair(client)
    assert set(RELATIONS["R3-paid-terminology-only"]["shared_terms"]) <= set(
        connection["shared_terms"]
    )
    assert connection["relation_type"] in {"topic_overlap_candidate", "weak_lexical_overlap"}
    assert connection["status"] == "candidate"
    assert connection["quote_validation"] == {"current_exact": True, "historical_exact": True}
    assert (
        "does not establish agreement, support, contradiction or corroboration"
        in connection["explanation"]
    )


@pytest.mark.xfail(
    strict=True,
    reason="UNIMPLEMENTED: ALIVE's lexical connection cannot abstain on a terminology-only pair",
)
def test_terminology_only_pair_should_abstain(client, no_provider):
    assert terminology_only_pair(client)["relation_type"] == "insufficient_evidence"


@pytest.mark.skip(
    reason="UNIMPLEMENTED: judging that R1 is a supersession, or R2 a scoped change, needs a "
    "qualified validity judgement; none exists, none is claimed, and none was run here."
)
def test_validity_judgement_of_a_superseded_claim():
    raise AssertionError("not implemented")


@pytest.mark.parametrize(
    ("key", "value"),
    [
        (
            "title",
            json.loads((SITE.parent / "tests/fixtures/notebook-r4.json").read_text())["attack"],
        ),
        ("source_parts", ["__preamble__"]),
        ("alive_stage", "ALIVE-99"),
        ("generated_by", "trusted-reviewer"),
        ("summary", "ALIVE improves research retrieval"),
        ("draft", True),
        ("slug", "unsupported-result"),
        ("chapter_id", "unsupported-result"),
        ("source_doc", "docs/ALIVE-13.md"),
        ("source_commit", "0" * 40),
        ("source_sha256", "0" * 64),
        ("body_sha256", "0" * 64),
    ],
)
def test_front_matter_attacks_are_rejected_with_valid_source_and_body_hashes(
    tmp_path, monkeypatch, key, value
):
    def edit(text):
        header, body = text[4:].split("\n+++\n", 1)
        meta = nb.tomllib.loads(header)
        meta[key] = value
        return (
            "+++\n"
            + "\n".join(f"{k} = {nb.toml_value(v)}" for k, v in meta.items())
            + "\n+++\n"
            + body
        )

    problems = tampered_copy(tmp_path, monkeypatch, "alive-12-status", edit)
    assert any(f"front matter {key}" in p or f"front matter key: {key}" in p for p in problems)


def test_rehashed_body_cannot_remove_critical_qualification(tmp_path, monkeypatch):
    def edit(text):
        header, body = text[4:].split("\n+++\n", 1)
        meta = nb.tomllib.loads(header)
        body = body.replace(
            "Retrieval advantage: **NOT DEMONSTRATED**.", "ALIVE improves research retrieval."
        )
        meta["body_sha256"] = nb.sha256(body.encode())
        return (
            "+++\n"
            + "\n".join(f"{k} = {nb.toml_value(v)}" for k, v in meta.items())
            + "\n+++\n"
            + body
        )

    problems = tampered_copy(tmp_path, monkeypatch, "alive-12-status", edit)
    assert any("qualifier removed" in p for p in problems)
    assert any("line stronger than source" in p for p in problems)
    assert not any("chapter body was edited after conversion" in p for p in problems)


def test_generation_is_deterministic_and_matches_committed_chapters(tmp_path, monkeypatch):
    committed = {p.name: nb.normalise(p.read_bytes()) for p in nb.CONTENT.glob("*.md")}
    monkeypatch.setattr(nb, "CONTENT", tmp_path / "chapters")
    nb.convert()
    first = {p.name: p.read_bytes() for p in nb.CONTENT.glob("*.md")}
    nb.convert()
    assert first == {p.name: p.read_bytes() for p in nb.CONTENT.glob("*.md")} == committed


def test_missing_history_is_a_failure_not_a_skip(monkeypatch):
    real_git = nb.git

    def git(*args):
        if args == ("rev-parse", "--is-shallow-repository"):
            return b"true\n"
        return real_git(*args)

    monkeypatch.setattr(nb, "git", git)
    problems = nb.check()
    assert len([p for p in problems if "requires full Git history" in p]) == 5


@pytest.mark.parametrize("tag", ["h1", "title"])
def test_rendered_title_attack_is_rejected(tmp_path, tag):
    chapter = nb.load_spec()["chapters"][1]
    title = nb.split_title(chapter)
    page = tmp_path / "chapters" / chapter["id"] / "index.html"
    page.parent.mkdir(parents=True)
    h1 = "ALIVE demonstrated retrieval superiority" if tag == "h1" else title
    doc_title = (
        "ALIVE demonstrated retrieval superiority"
        if tag == "title"
        else (title + " · The ALIVE Notebook")
    )
    page.write_text(
        f"<html><head><title>{doc_title}</title></head>"
        f"<body><main><h1>{h1}</h1></main></body></html>",
        encoding="utf-8",
    )
    problems = []
    nb.check_public(tmp_path, {"chapters": [chapter], "capture_window": 2000}, {}, problems)
    assert any("rendered" in p and "title" in p for p in problems)
