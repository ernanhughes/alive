# ALIVE Notebook (ALIVE-NOTEBOOK-01, first milestone)

A small Hugo site that republishes selected sections of ALIVE's own engineering documents, so the
existing Chrome companion and research memory can be used to read across them.

It is a reading environment. It is not evidence that ALIVE improves research. ALIVE's own reports
say retrieval advantage is not demonstrated in general and that connections are candidates, not
verified facts, and this site keeps those statements intact.

## What is here

| Path | Purpose |
|---|---|
| `hugo.toml`, `layouts/`, `content/_index.md` | Minimal Hugo config and templates. No theme, no JavaScript. |
| `notebook/chapters.json` | The curated chapter list: id, source document, which parts to reproduce. |
| `notebook/relations.json` | Test ground truth: real historical relationships with verified quotes. Not published as a page. |
| `notebook.py` | Deterministic converter and provenance checker (Python standard library only). |
| `content/chapters/*.md` | Generated chapters. Do not edit by hand; rerun `convert`. |

`docs/` and `archives/` stay canonical and are never modified. No model writes any chapter text.

## Build and run

Requires [Hugo](https://gohugo.io/) (built and checked with v0.165.0) and Python 3.11+.

```bash
python site/notebook.py convert        # regenerate site/content/chapters from docs/
python site/notebook.py check          # provenance + relationship quotes
hugo --source site                     # build into site/public
hugo server --source site --bind 127.0.0.1 --port 1313 --disableLiveReload
```

Open `http://127.0.0.1:1313/chapters/alive-12-status/`. Use port 1313: the companion authorises
exact URLs, so any other port is refused.

## Provenance

Each chapter's front matter records `chapter_id` (stable, also the URL slug), `source_doc`,
`source_parts`, `source_commit` (the last commit that touched the source), `source_sha256`
(line endings normalised to LF) and `body_sha256`. `check` fails when:

- any front-matter field differs from canonical generation, including title, selected parts, stage,
  generator and commit, or any unauthorized key (such as `summary` or `draft`) is present;
- the source file changed since conversion, or does not match the recorded hash at the recorded
  commit (hash drift);
- the chapter body differs from a fresh conversion of the source. The report says whether an
  added line looks stronger than the source (for example "ALIVE improves research retrieval"
  where the source says "Retrieval advantage: NOT DEMONSTRATED") or a qualifier line was removed;
- a body link would not resolve on the site;
- a relationship quote is not in the canonical document, or is not inside the first 2000
  characters of the chapter (the companion saves at most a 2000-character excerpt);
- with `--public site/public`: an article H1 or document title differs from its canonical source
  title, a built page has page chrome inside `<main>`, or its article is
  longer than the saved excerpt.

Full Git history is required; missing or shallow history fails rather than skipping checks.
Hashes prove integrity relative to verified inputs, not the truth of an editorial interpretation.
The conversion manifest is a reviewed input. This checker cannot determine whether a changed
manifest omits a relevant qualification elsewhere in a source, or assess unfamiliar documents.
If a source document legitimately changes, rerun `convert` and review the chapter diff.

## Reading with the companion

The page layout keeps the article alone inside `<main>`. The site navigation, contents list and
provenance footer sit outside it, so the companion's visible-text capture (which roots at
`main,article,[role="main"]`) does not include them.

The companion authorises exact chapter URLs only: `alive/web_experience.py` (`PAGES`) and
`extension/config.js` (`AUTHORISED_PAGES`) list `http://127.0.0.1:1313/chapters/<id>/` and the
`localhost` equivalent. `extension/manifest.json` is unchanged; no wildcard or persistent host
permission was added. The grant is still created per page by the owner clicking the toolbar icon.
The allowlist does not pin the bytes of the served chapters; review the captured excerpt before
saving. A local process on port 1313 could serve different text at the same path.

Journey: read `alive-12-status`, review the excerpt, save it as research memory; read
`alive-13-what-was-wrong`; ask for related research. The retrieval and connection results are
produced by ALIVE's existing deterministic lexical code and make no model call.

## Relationships (ground truth for the tests)

`notebook/relations.json` holds three real relationships, each with exact quotes that `check`
verifies against `docs/`:

- **R1, supersession.** ALIVE-12 labelled lexical overlap `same_concept`; ALIVE-13 says those
  labels overstated what shared words establish.
- **R2, scoped change.** ALIVE-12: retrieval advantage NOT DEMONSTRATED. ALIVE-13: demonstrated
  only on its frozen lexical corpus; general superiority still NOT DEMONSTRATED. This is not a
  general reversal.
- **R3, abstention.** ALIVE-11 and ALIVE-14 both mention paid calls, about different milestones.
  No relationship is established.

These are a human reading of the quoted passages. ALIVE does not make these judgements. The key is
kept out of the published pages so it cannot enter a captured excerpt.

## Tests

```bash
uv run pytest tests/test_notebook_01.py
node --test tests/notebook-capture.test.cjs   # requires Hugo; missing Hugo fails
```

What they show, and do not show:

- Retrieval over the chapters returns the earlier chapter for R1 (rank 1 of 3 saved memories).
- For R2 the ALIVE-12 chapter is retrieved within the top three but not ranked first (the ALIVE-14 chapter outranks it). That is a
  measured limitation, asserted as such.
- For R3 the deterministic connection does not abstain. It shows a `topic_overlap_candidate`
  with the shared words `paid` and `calls`, labelled as not establishing agreement or support. The
  desired abstention is an `xfail(strict)` test marked UNIMPLEMENTED.
- A stronger validity judgement (is this claim superseded, or still valid?) does not exist.
  It appears only as a skipped test marked UNIMPLEMENTED. Nothing here claims it.
- Retrieval, abstention, withdrawal, restart and revocation were exercised in real
  Chrome 156 through the unpacked extension; see
  [the native result](../docs/validation/alive-notebook-01/native/result.json) and
  `scripts/native_notebook_01.py`.

## Native Chrome acceptance

```bash
uv run python -m scripts.native_notebook_01
```

The substituted-authorization harness starts Hugo on `127.0.0.1:1313`, an isolated SQLite ALIVE backend and the
actual unpacked extension, then drives a docked Chrome side panel through capture,
memory save, retrieval, the three relationships, withdrawal, backend restart and
revocation. It writes `docs/validation/alive-notebook-01/native/result.json` and
screenshots. This is integration evidence with a substituted test copy, not shipped
`activeTab` qualification. It overwrites all of `config.js`: backend defaults become the
isolated random port, `AUTHORISED_PAGES` becomes the five loopback chapter URLs and
`isLocalDemo` always returns false. It replaces the manifest's host permissions with the
isolated backend and `http://127.0.0.1:1313/*`, and sets backend
`ALIVE_NATIVE_TEST_PAGES` to those chapters. CDP opens the panel without qualifying a
real toolbar grant. The shipped extension files remain unchanged.

`uv run python -m scripts.native_notebook_01_shipped` separately loads a byte-identical
copy of the shipped extension, checks runtime configuration and permissions, and saves
its hashes. This load smoke does not claim capture acceptance. Shipped toolbar capture,
unlisted-URL rejection and revocation are **NOT QUALIFIED** until the manual procedure in
[the R1 report](../docs/ALIVE-NOTEBOOK-01-R1-REPORT.md) is completed. No model provider
is configured; no paid inference is used.

PR #40 has merged. All reported ranks used lexical fallback with embeddings disabled.
R1 remains a lexical connection candidate, R2 compares different evaluation conditions
and does not establish universal superiority, and R3 remains a known false similarity.

## Extending

1. Add an entry to `notebook/chapters.json` (`id`, `doc`, `alive_stage`, `parts`). Parts are the
   source `##` headings, or `__preamble__` for the text before the first one. Keep the chapter's
   article under 2000 characters of visible text.
2. Add the id to `NOTEBOOK_CHAPTERS` in `alive/web_experience.py` and to `NOTEBOOK_CHAPTERS` in
   `extension/config.js`. The tests fail if these lists and `chapters.json` disagree.
3. `python site/notebook.py convert`, then `python site/notebook.py check`.
4. To record a relationship, add it to `notebook/relations.json` with exact quotes. Do not
   paraphrase. Mark invented material `"authenticity": "synthetic"`; it is skipped by the
   quote check and must never be published as a chapter.

## Not done

Public publication, sections outside the five chapters, `research/`, `experiments/` and
`references/` collections, an extension host, and a model-backed validity judgement are
deferred. R3 remains a candidate for the next evidence-qualification milestone; ALIVE's
lexical connection does not abstain on the terminology-only pair.
