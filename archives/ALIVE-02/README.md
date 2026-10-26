# ALIVE-02 reviewed qualification archive

Owner acceptance review: **PASS_WITH_LIMITATIONS**. Reviewed implementation: [`f98a6a53b20316b7057f77e5b635fbc06ab23061`](https://github.com/ernanhughes/alive/commit/f98a6a53b20316b7057f77e5b635fbc06ab23061).

This archive was prepared following the owner's request to publish the reviewed feature branch and retain its specification, results, screenshot and redacted Meta usage logs. The review is based on reported local qualification, **not an independently rerun test suite**. No tests or model experiments were rerun for this archival step. The publication commit adds evidence and documentation without rewriting the reviewed implementation's history.

## Contents

| Path | Meaning |
| --- | --- |
| `specification/heldout-cases.json` | Frozen final three-case qualification corpus |
| `specification/engineering-cases.json` | Earlier engineering corpus; not an unseen test set |
| `specification/role-prompts.json` | Actual role specification v2 prompts and pinned model ID from the final report |
| `results/primary-meta.json` | Final live A/B/C + no-Critic report, inputs/outputs, criteria, dataset hash and metrics |
| `results/primary-meta-ledger.json` | Final experiment's persisted reservation/usage ledger |
| `results/engineering-meta*.json` | Earlier live engineering comparison and ledger |
| `results/controlled-*.json` | Alternative evidence-access experiments using controlled role fixtures, not live Meta |
| `results/meta-smoke.json` | Retained successful native structured-inference smoke evidence |
| `results/first-thought-summary.json` | Live autonomous demonstration summary with nested runtime/private-memory traces removed |
| `usage/meta-usage.jsonl` | Available Meta call usage records, one archive record per call; no double-counting nested benchmark copies |
| `usage/summary.json` | Coverage, redactions and explicit missing-usage disclosure |
| `acceptance.png` | Reviewed local observatory screenshot; the stopped/fixture controls shown are not evidence of a currently running Meta call |
| `qualification-report.md` | Historical qualification report captured before publication |
| `manifest.json` | SHA-256/byte count for each evidence payload and the reviewed source commit |

The manifest covers the evidence payload, not itself, this README or `.gitattributes`. Archive attributes preserve exact payload bytes across platforms. The original qualification report's “no push” statement describes its qualification-time state; subsequent publication is this separately authorized administrative step.

## Interpretation

The final benchmark used one Meta model, `muse-spark-1.3`, across all arms. It made **25 calls / 30,632 reported tokens**. Adaptive and no-Critic arms both met the evidence-and-citation criterion on 3/3 tasks; the no-Critic arm used fewer tokens. These three synthetic cases do not establish general superiority or a demonstrated benefit from the Critic. They motivate a larger frozen Always/Never/Selective Critic experiment for ALIVE-03.

The consolidated usage export includes all available runtime Meta invocation rows, both live benchmark ledgers and the retained successful smoke: **69 calls with reported usage / 98,927 reported tokens**. One earlier truncated bootstrap smoke has **unknown full usage**, explicitly represented with `usage: null`. Missing timestamps/provider request identifiers are not invented. Archive identifiers for benchmark/smoke records are not claimed to be provider-issued request IDs. These records do not establish complete provider-account billing or a dollar total.

Credentials, HTTP authorization headers, runtime input/output bodies, retrieved-memory content, personal browser history, browser profiles and raw service logs are excluded. Full benchmark inputs/outputs are retained because they contain only the frozen synthetic fixtures. The screenshot was visually inspected before inclusion. Local credential values were checked against every payload before staging.

## Verify payload integrity

From the repository root:

```powershell
uv run python -c "import hashlib,json,pathlib; p=pathlib.Path('archives/ALIVE-02'); m=json.loads((p/'manifest.json').read_text()); assert all(hashlib.sha256((p/n).read_bytes()).hexdigest()==v['sha256'] and (p/n).stat().st_size==v['bytes'] for n,v in m['files'].items()); print('Archive checksums verified')"
```

The source implementation and full reproduction commands remain in [the current acceptance report](../../docs/ALIVE-02-ACCEPTANCE.md). `models.txt` is unrelated local work and is not part of this archive.
