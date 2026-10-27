# ALIVE-12 - Three-minute demonstration

This is a **controlled native synthetic playback**, not live Meta inference. It demonstrates the
cross-page research-memory mechanism and its boundaries. Do not call the two sources corroborating
evidence.

| Time | Demonstration |
|---|---|
| 0:00-0:35 | Open controlled source A in Chrome. Establish the research goal and review the excerpt. |
| 0:35-1:00 | Save the validated note for research. Show the source URL, reviewed timestamp, SHA-256, goal and bounded excerpt. |
| 1:00-1:35 | Open controlled source B. Run **Find related research**. ALIVE returns source A as historical evidence, explicitly separate from the current page. |
| 1:35-2:10 | Select **Explain connection**. Show the `same_concept` candidate, both exact quotations, shared terms and the “candidate, not corroboration” label. |
| 2:10-2:35 | Rate the connection. Then restart the backend and show the memory still present; withdraw it and show retrieval abstains. |
| 2:35-2:50 | Show the false-similarity fixture: retrieval can return a lexical match, but the connection abstains when no shared evidence survives. |
| 2:50-3:00 | Claim: “ALIVE uses authorised, persistent research memory to connect evidence across different pages. This demonstrates the mechanism; broader usefulness is evaluated separately.” |

## Exact claims

- All sources are controlled, explicitly reviewed loopback excerpts.
- Historical text is not current-page evidence.
- Similarity is a retrieval hint, not proof.
- The evaluation includes a strong history-access control; no ranking advantage is demonstrated.
- The only inference call in the native journey is one local synthetic provider call. No paid Meta
  call was made.
- Withdrawal deletes the retrieval projection and survives restart.

## Reproduction

```powershell
uv run python -m scripts.native12
uv run python -m scripts.alive12_evaluation
```

Evidence: `archives/ALIVE-12/` (manifest, retrieval comparison, native evidence and screenshot).
