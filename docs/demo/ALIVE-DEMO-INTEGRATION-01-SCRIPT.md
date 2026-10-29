# ALIVE demonstration — 90-second script

For a presenter at `http://localhost:8000` after `docker compose up --build -d`. Enter the local
token once (`alive-dev-token-replace-for-local-use-000` unless you set your own). Everything below
runs offline; no provider key is set and none can be used.

**Say the label out loud.** The page carries `DETERMINISTIC LOCAL FIXTURE — NOT LIVE META`. Do not
call the comparison "AI reasoning", "verified", or "ALIVE found the truth".

| Time | Do | Say |
|---|---|---|
| 0:00 | Open **Demonstration**. Point at the amber label. | "This is a fresh clone, running offline. The comparison here is a deterministic fixture, and the page says so. What's real is the memory, the bindings and the withdrawal." |
| 0:12 | Read the consent line, click **Start demonstration**. | "Clicking authorises exactly two local comparisons of these pinned sources. Nothing leaves the machine." |
| 0:20 | Steps 1–3 appear. Point at the source hash and the anchored sentence. | "ALIVE remembers a Python 3.11 page by its bytes, and I've anchored one sentence: it returns the current UTC time with no timezone." |
| 0:35 | Steps 4–6. Point at the consent card and the bound pair. | "Here is the exact payload: this memory, this later page, this hash. A result for any other pair would not be shown." |
| 0:45 | The **compare** step. Read the two quotes. | "The standing changed — it's now deprecated — but the described behaviour is still there. That's a change in applicability, not a contradiction." |
| 0:58 | The **abstention** step. | "A second page says nothing about that sentence, so ALIVE declines to infer anything. That refusal is part of the product." |
| 1:08 | **Before and after withdrawal** table. | "I withdrew the original. Before: one finding, two comparisons, retrievable. After: none of them come back from an ordinary read." |
| 1:18 | **Audit view**. | "The originals are retained for audit as retired rows — hidden, not erased. No source text is shown." |
| 1:24 | Run `docker compose restart app`, then **Check again**. | "New server process, same answer. The state is in the database, not in this page." |
| 1:30 | Stop. | |

## If asked

* *Is the comparison a model?* No. It is `local_fixture_claim`, a deterministic fixture bound to
  these two pinned pages. A live model run needs a separate owner authorisation and spend cap; none
  exists, and this build has no code path to one.
* *Is the Python deprecation text "true"?* The pages are pinned local mirrors; matching bytes
  identifies a document, it does not judge its claims.
* *Does ALIVE improve itself?* Not shown, not claimed.

## Fallback: RECORDED walkthrough

If Docker or Chrome fails on stage, play `docs/demo/evidence/recorded/RECORDED-*.png`, a storyboard captured from a
real local run, with **RECORDED WALKTHROUGH — NOT LIVE** burned into every frame. Say "this is a
recording". Regenerate with `pwsh scripts/demo-acceptance.ps1 -Record` (set `DEMO_VIDEO=1` after `npx playwright install ffmpeg` for a video).
