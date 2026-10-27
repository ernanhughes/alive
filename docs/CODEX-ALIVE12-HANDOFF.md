# ALIVE-12 handoff - Personal Research Intelligence

## Repository

| Item | Value |
|---|---|
| Baseline `origin/main` | `d58c30748a5ec9273a0be86dc769d8c1b7dc6b23` |
| Branch | `codex/alive-12-research-intelligence` |
| Product code commit | `cf7022cb168b4cbd65bbc0b98faafbb25b498c85` |
| Archive/handoff commit | `_Pending._` |
| PR | `_Pending creation._` |
| Worktree | `C:\Projects\alive-worktrees\alive-11` |
| Paid inference | **None** |

The primary checkout and its 25 local changes were untouched. ALIVE-01 through ALIVE-11-R1 archives
were not modified.

## Architecture reused

- `WebExperience` for authoritative goal, snapshot, note, feedback and research records.
- Existing `Memory`/`MemoryVector` and `MemoryService` for the retrieval projection.
- Existing `MemoryService` hybrid/text retrieval and embedding provenance.
- Existing Governor, grants, exact recall and companion extension.
- No new database, vector store, embedding model or learner.

## Implemented loop

1. A validated note is explicitly saved from the panel.
2. `ResearchMemory.save` creates a bounded, provenance-linked research row and a deterministic
   `Memory` projection. Duplicate saves are idempotent.
3. A second reviewed source triggers goal-scoped retrieval. Results exclude the current URL,
   current SHA, other goals and withdrawn memories.
4. The panel shows historical source, date, excerpt, owner usefulness and retrieval method.
5. **Explain connection** creates a deterministic lexical candidate with exact historical and
   current quotations. It never labels a candidate as factual corroboration.
6. Connection feedback is persisted. Withdrawal deletes the projection/vector and is permanent
   across restart.
7. A native synthetic journey saves source A, retrieves it from source B, creates a candidate,
   records feedback, restarts, withdraws and confirms zero active memory.

## Evaluation

`archives/ALIVE-12/evidence/retrieval-comparison.json`:

| Arm | Results | Relevant | Precision@3 | Targets | Recall@3 | False retrievals | Correct abstentions |
|---|---:|---:|---:|---:|---:|---:|---:|
| Current-page only | 0 | 0 | n/a | 0/4 | 0.0 | 0 | 2 |
| Exact-match only | 0 | 0 | n/a | 0/4 | 0.0 | 0 | 2 |
| Cross-page retrieval | 5 | 4 | 0.80 | 4/4 | 1.0 | 1 | 1 |
| Retrieval + connection | 5 | 4 | 0.80 | 4/4 | 1.0 | 1 | 1 |
| History-access control | 5 | 4 | 0.80 | 4/4 | 1.0 | 1 | 1 |

Four connection candidates had valid current and historical quotations; zero unsupported/false
connections were recorded. The false-similarity source was retrieved lexically but the connection
abstained. No ranking or retrieval advantage is claimed because the strong history-access control
performed identically on this small corpus.

## Native synthetic

- Chrome `155.0.8059.85`, genuine docked side-panel target.
- Two controlled loopback pages.
- One local synthetic provider call to create the historical note.
- Restart retained active memory; withdrawal removed it; wrong-origin grant 403.
- Screenshot: `archives/ALIVE-12/evidence/research-memory.png`.

## Tests

| Check | Result |
|---|---|
| Backend suite | 151 passed |
| Research-memory focused | 5 passed |
| Extension tests | 9 passed |
| Frontend | 7 passed |
| Build | Passed |
| Ruff check/format | Passed |
| Native synthetic | Passed; docked panel |
| Paid calls | 0 |

## Limitations

- Small controlled corpus with one memory per goal; history-access control equals ranked retrieval.
- Labels are source-adequacy labels, not owner ratings or independent task outcomes.
- Retrieval evaluation used the text fallback; hybrid embeddings were not available in the test
  environment.
- Connections are lexical candidates; contradiction/support semantics are not resolved.
- No broad browser history, external search service, Hacker News/Hugging Face ingestion or Docker
  integration.
- No Meta relationship analysis or paid inference.
- False-similarity lexical retrieval remains a measured false positive; it was not tuned away.

## Review focus

1. Confirm explicit save and owner-scoped retention.
2. Confirm goal/URL/SHA filtering and no current-page re-use.
3. Confirm withdrawal deletes projection/vector and cannot resurrect.
4. Confirm connection candidates require both exact quotations and never claim factual support.
5. Confirm feedback revisions affect retrieval usefulness without topic suppression.
6. Check the evaluation does not claim ranking or utility advantage.

Publication is review-only: no merge or auto-merge.
