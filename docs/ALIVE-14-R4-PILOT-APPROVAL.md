# ALIVE-14-R4 - Pilot approval request

Status: **NOT AN APPROVAL**. No paid Meta inference is authorised.

The real `prepare --mode real` phase was executed locally. It created the
campaign and exact payload reservations but dispatched no provider call.

## Campaign identity

- Run: `alive14-r4-real-85fe891cee31`
- Protocol: `alive14r3-paired-v3` (frozen, unchanged)
- Protocol SHA-256: `85fe891cee31bf93d178c4cba2102642b8f4b5e666a0ee426186d5735eb5a71b`
- Answer-key SHA-256: `255e706dd569634d1710a50831f65a6dd6eb7dabc5ee56e1cd763b382554b43d`
- Campaign digest: `6851fbadf3b7a3367f93f623e1ae45063b0de6b09b6ce2efba965603c8884b7e`
- Provider/model: `meta` / `muse-spark-1.3`
- Tasks: 9
- Inference calls: 18 (A and B; C uses no inference)
- No automatic retries.

The digest excludes random database IDs and covers the protocol/answer-key
hashes, provider/model, instruction/schema hashes, and every task's goal,
question, current/historical URL, SHA-256 and exact excerpt.

## Staged caps

| Stage | Calls | Reserved tokens | Worst-case USD |
|---|---:|---:|---:|
| Stage 1 | 2 | 10,345 | **$0.043967** |
| Full campaign | 18 | 92,148 | **$0.391635** |

The full-campaign ceiling remains **$0.45**. The effective cap is the minimum of
the protocol ceiling, the owner-approved cap and `ALIVE_R4_RUNTIME_USD_CAP`.
Stage 2 approval uses the cumulative call cap of 18 and the full reservation.

## Exact material that would be transmitted

For each task, condition A sends:

- goal and neutral research question;
- current source URL, SHA-256 and exact excerpt;
- provider `meta`, pinned model `muse-spark-1.3`;
- the common `PAIRED_INSTRUCTIONS` and `PairedAnswerOutput` schema.

Condition B sends the same content plus exactly one selected historical source:
its URL, SHA-256 and exact excerpt. No other memory, browser history, tool,
credential or private record is included.

The exact payload and request hashes are in
`archives/ALIVE-14-R4/evidence/real-run-preview-manifest.json`. The registered
campaign manifest is in `real-campaign.json`. The request summary is in
`pilot-approval-request.json`.

## Owner approval procedure

1. Run:

   ```powershell
   uv run python -m scripts.alive14r4_experiment serve-approval --mode real --port 8765
   ```

   Keep it running. It prints the campaign digest and owner token.

2. In the native side panel, connect to `http://127.0.0.1:8765` with that token.
3. Open **Experiment approval**, refresh, select the campaign, and inspect:
   digest, provider/model, task count, exact manifest, stage caps, no-retry
   policy and reservation.
4. For a real campaign, check the owner-attestation box.
5. Approve **stage 1 (2 calls)**.
6. Stop `serve-approval`.
7. Run:

   ```powershell
   uv run python -m scripts.alive14r4_experiment approve --mode real
   uv run python -m scripts.alive14r4_experiment execute --mode real --limit 2
   ```

8. Inspect only the technical result of the two calls (status, schema validity,
   provider/model, usage, dispatch state). Do not read the answer content if you
   intend to remain blind for later ratings.
9. If stage 1 succeeds, restart `serve-approval`, approve **stage 2 (remaining
   16 calls)**, stop it, then:

   ```powershell
   uv run python -m scripts.alive14r4_experiment approve --mode real
   uv run python -m scripts.alive14r4_experiment execute --mode real --limit 16
   ```

10. Complete ratings through the native panel, then run `rate`, `reveal`,
    `analyse` and `archive` as separate commands.

The CLI `approve` step only reads the server-side owner approval; editing a local
file to say `human_approval=true` is rejected.

## Abort conditions

- Protocol or answer-key hash mismatch.
- Campaign digest mismatch or missing/revoked/superseded approval.
- Provider/model change or `ALIVE_META_API_KEY` absent.
- Any grant explicitly revoked, withdrawn historical memory, changed source
  hash or expired grant.
- Effective cap below the stage reservation.
- Campaign-fatal provider error (401/403, quota, rate limit, invalid schema,
  5xx/timeout/network, ambiguous settlement).
- Any attempt to replay an interrupted or ambiguous call.

No real calls are authorised until the owner completes the authenticated
approval and independently reviews the scope, budget and transcripts.
