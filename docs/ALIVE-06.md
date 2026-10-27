# ALIVE-06 - Contextual Browser Intelligence

ALIVE-06 adds a deterministic relevance gate between an authorised browser observation and the
existing ALIVE-05 documentation companion. It answers a practical question before spending a
model call: **is this observation relevant to the owner's goal?**

## What it does

1. The owner saves a goal and authorises an exact documentation page.
2. The extension sends a reviewed excerpt with its exact hash.
3. Before any analysis or note reservation, ALIVE compares lowercase content words in the goal
   and excerpt.
4. If no content term overlaps, the persisted decision is `no_action`.
5. `no_action` creates no note, no provider reservation and no Meta call.
6. A direct call to the analysis endpoint for the same state is rejected with HTTP 409.
7. The side panel shows the matched terms, the relevance basis and why no action was taken.
8. If terms overlap, the existing decision policy runs: recall a useful exact-match note, or
   propose one bounded analysis.

The check is local and deterministic. It does not use an embedding, classifier, language model
or paid call. It is intentionally coarse: a false negative is possible, and the panel tells the
owner to revise the goal if the page should be analysed.

## Decision contract

| Field | Meaning |
|---|---|
| `action` | `recall`, `analyse` or `no_action` |
| `goal_relevance.policy` | `deterministic-goal-excerpt-overlap-v1` |
| `goal_relevance.relevant` | Whether at least one content term overlaps |
| `goal_relevance.matched_terms` | At most 20 sorted matched terms |
| `goal_relevance.basis` | Explicit statement that this is lexical overlap, not inference |
| `inference_calls` | Always zero for the decision itself |

A `no_action` decision is persisted with the snapshot and cannot be converted into an analysis
call through the API. The extension disables the analysis button, but the server is authoritative.

## Controlled demonstration

Use the two authorised documentation pages and a fresh test database:

1. Save the goal “Help me decide where to start learning Python”.
2. Authorise the Python tutorial, review the excerpt, and send it.
3. The panel should show a relevance match (for example, `python`) and recommend analysis.
4. Run the bounded analysis, read the note, and rate it useful.
5. Revisit the same goal and excerpt. The decision should be `recall`, with zero new calls.
6. Save an unrelated goal such as “Check coolant temperature”.
7. Authorise the same page and send the excerpt. The panel should show **No action warranted**,
   list no matched terms, create no note and make no Meta call.
8. Calling the analysis endpoint directly for that state should return HTTP 409.

The evidence in `archives/ALIVE-06-CONTEXTUAL-BROWSER/` uses a synthetic provider and an isolated
SQLite database. It is not native Chrome or Meta qualification.

## Verification

```powershell
uv run pytest -q
uv run pytest -q tests/test_web_experience.py
uv run ruff check alive migrations scripts tests
uv run ruff format --check alive migrations scripts tests
npm test --prefix dashboard
npm run build --prefix dashboard
```

## Limits

- Lexical overlap is not semantic relevance. A relevant excerpt with different vocabulary can be
  classified as `no_action`; the owner can revise the goal.
- Relevance does not verify factual truth. A model note remains an interpretation, and its quoted
  evidence is checked separately.
- The no-action path is tested through the API and a controlled test harness, not a new native
  side-panel Playwright journey.
- The two exact documentation pages and exact-match reuse do not establish general web
  intelligence or autonomous action.
- No paid inference is part of this milestone.
