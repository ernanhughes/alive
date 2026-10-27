# Hackathon provenance

Implementation began on 26 October 2026 in `C:\Projects\alive`.

- Starting branch: `main`.
- Starting HEAD: `7db2621fa4806e9b1930e1239c7131c3bc7998cf`.
- Starting tree: clean; `.gitignore`, Apache-2.0 `LICENSE`, and a seven-byte `README.md`.
- Work branch: `codex/alive-01`.
- The pasted brief described an empty repository; actual inspection found the initial commit above. That actual state is authoritative.

All ALIVE implementation in this milestone was written here. No earlier project implementation was imported, copied or vendored. No subagents were used. Pi was invoked as an integration under test, with tools disabled. Local commits are permitted by the brief; no push, merge, deployment or publication was performed.

Initial environment inspection found shell Python 3.13.15, uv 0.7.2, Node 25.8.2, npm 11.21.1, PostgreSQL client 18.1, stable Chrome 155.0.8059.85 and Pi 1.4.0. uv selected its managed Python 3.13.3 for the project virtual environment. The PostgreSQL 16/17/18 Windows services were stopped; a local PostgreSQL listener was nevertheless reachable on 5432. The owner supplied ALIVE connection configuration during implementation; its password is not recorded here.

Dependencies were resolved using package registries and locked. Implementation references included official [SQLAlchemy async documentation](https://docs.sqlalchemy.org/en/20/orm/extensions/asyncio.html), [Playwright browser API](https://playwright.dev/python/docs/api/class-browser), [Pi RPC specification](https://github.com/badlogic/pi-mono/blob/main/packages/coding-agent/docs/rpc.md), [Chrome side panel API](https://developer.chrome.com/docs/extensions/reference/api/sidePanel), and [Playwright extension testing guidance](https://playwright.dev/docs/chrome-extensions). The installed Pi help was checked for version-specific security flags and RPC support.

The project's original Apache-2.0 license is retained. Direct dependencies remain externally installed, not vendored. FastAPI/Pydantic/SQLAlchemy/Alembic/React/Vite/Playwright/Beautiful Soup/HTTPX and related dependencies carry their own permissive licenses; pyzmq/libzmq, PostgreSQL and pgvector retain their upstream obligations. Lucide icons use ISC. The dashboard requests DM Sans and Space Grotesk via Google Fonts (SIL Open Font License); no font files or third-party bitmap assets are copied into this repository. Redistributing packaged binaries/assets requires retaining their license notices.

An untracked `models.txt` appeared during implementation after the initial inspection. It was read as a local model catalog and left unmodified and outside the implementation commits.

## ALIVE-02

Work continued on 26 October 2026 from `codex/alive-01` at `3a73a72139b00b447394812c403b1a742094a641`, with only the existing unrelated untracked `models.txt`. Read-only `git ls-remote` independently confirmed that exact commit was pushed on `origin/codex/alive-01`; `origin/main` remained `7db2621fa4806e9b1930e1239c7131c3bc7998cf`. A new `codex/alive-02-cognitive-society` branch preserves that history. No subagents, copied prior-project implementation, push, merge or deployment were used for ALIVE-02.

The ALIVE-01 backend/frontend suites, production build, browser E2E, extension smoke and real-Pi First Contact were rerun before structural changes. The extension smoke initially exposed a first-500-events test-harness assumption on the larger persistent database; it was corrected to scan with sequence cursors and then passed. Migration head advanced from 0002 to 0003 with explicit new tables, preserving original identity, events, memories and goals.

The owner supplied Meta credentials through ignored local configuration and explicitly authorized continued live model calls, including the bounded benchmark. No credential value is reproduced in source, reports or commits. Official API references verified during implementation: [Meta structured output](https://dev.meta.ai/docs/structured-output), [Chat Completions](https://dev.meta.ai/docs/protocols/chat-completions), [reasoning](https://dev.meta.ai/docs/reasoning), and [token-counting distinctions](https://dev.meta.ai/docs/token-counting). Authenticated discovery confirmed `muse-spark-1.3`; actual inference and reported usage were recorded locally.

Actual local embedding inference uses Apache-2.0 [sentence-transformers/all-MiniLM-L6-v2](https://huggingface.co/sentence-transformers/all-MiniLM-L6-v2), pinned revision `1110a243fdf4706b3f48f1d95db1a4f5529b4d41`, 384 dimensions, ONNX Runtime, attention-mask mean pooling and normalization. Public model assets were downloaded to ignored `.alive/models/minilm`; no weights or private histories were vendored. ONNX Runtime/tokenizers/Hugging Face Hub/NumPy dependencies are locked and retain their upstream licenses.

The first live three-case benchmark was an engineering check on `benchmarks/cases.json`, not a defensible unseen test. Before final role-specification-v2 qualification, separate `benchmarks/heldout.json` cases were frozen. The final report records dataset hash, split, prompts, outputs, model and expenditure. Neither three-case run supports statistical superiority, a proven benefit from the Critic, learned behavior or general-world verification. See ALIVE-02-ACCEPTANCE for actual results and remaining limitations.
