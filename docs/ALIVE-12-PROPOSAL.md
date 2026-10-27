# ALIVE-12 proposal — Goal-scoped cross-page research memory

Status: **PROPOSAL ONLY**. Recommendation: defer implementation until ALIVE-11 is
reviewed. Do not let research memory delay native Chrome/Meta demonstration work.
No ALIVE-12 branch, collector, permission or model call has been created.

## Existing capability map

| Component | Present capability | Gap for cross-page companion memory |
| --- | --- | --- |
| `alive/memory.py` | Pinned local MiniLM ONNX, 384 dimensions; embedding-file provenance checks | Optional model availability must be checked on the accepted runtime |
| `MemoryService.index` | Projects `Memory` rows into versioned `MemoryVector` rows; PostgreSQL vector storage or bounded JSON-vector fallback | Companion `WebExperience` notes are separate records, not automatically an approved research index |
| `MemoryService.retrieve` | PostgreSQL full-text/SQLite substring, cosine vectors, reciprocal-rank hybrid fusion; hybrid can fall back to text | Explicit owner/goal/consent/retention filtering and companion provenance projection are needed |
| History import | Preview/approval and revocation deleting imported memories and vectors | This is not a silent Chrome history collector; reuse deletion semantics, not broad history ingestion |
| Browser companion | Reviewed snapshots, hashes, goals, exact recall, relevance, notes and feedback | Exact same-URL reuse does not provide cross-URL historical context |
| Docker/search | No repository Docker search integration found; Docker CLI installed, daemon unavailable during read-only inventory | No external service is assumed to belong to ALIVE or adopted implicitly |

## Smallest useful design

Add an explicit **Save to this goal's research memory** choice for an already
reviewed observation/note. Consent to live observation and consent to later
cross-page retrieval are distinct. Default remains off; no complete browsing
history collection and no new Chrome host permissions.

Maintain a provenance link to the source snapshot/note rather than copying an
unlabelled summary. A projection should retain owner/instance, goal ID, URL,
observed time, excerpt fingerprint, bounded authorised excerpt, interpretation
label, explicit usefulness rating, retention state and embedding revision.

Reuse the existing `Memory`/`MemoryVector` index for a consented projection, with
transactional source links and deduplication. Filter eligible source records by
owner, goal, live consent and retention before retrieval; recheck before returning
results. Start with up to three results and a recorded text/hybrid fallback.
Do not introduce another vector database or learner.

The current embedder truncates at 256 tokens. Do not assume it represents an entire
3,000-character excerpt: evaluate bounded segments with source ranges and parent
fingerprints, and measure whether truncation hides the relevant material.

When another authorised page is reviewed, retrieve saved material under the same
goal from different URLs. Show **Previously reviewed source** with date and link,
plus **Current page evidence** separately. Semantic similarity is a retrieval hint,
not support for a factual assertion about the new page. A remembered instruction
must never become a source fact, grant or executable action.

Do not forward historical text to Meta without previewing the exact historical
and current excerpts being sent under the owner's explicit permission. Retrieval
alone does not authorise another website visit, model call or tool action.

## Staleness, correction and removal

Record age and superseded content fingerprints. Label old material, allow the
owner to exclude it, and avoid claiming freshness from retrieval time. A possible
contradiction is a prompt to inspect dated evidence, not an automatically verified
correction or an inference that one source is true.

Provide per-item removal and whole-goal memory revocation. Delete/tombstone source
projections and associated vectors transactionally, and make all retrieval modes
respect removals immediately. Retain only minimal deletion audit metadata; do not
retain the supposedly deleted excerpt in an audit event. Specify local retention
and provider-side retention separately before implementation.

## One measurable scenario

Use an explicitly saved, dated Python learning-plan note. Later review the already
authorised MDN JavaScript Guide under a goal comparing a first study plan across
languages. Retrieve the earlier Python source as historical context, identify both
URLs, and avoid using Python documentation as factual evidence for JavaScript.

Before tuning, freeze a small set of cross-page pairs with positives and hard
negatives: same topic/different goal, obsolete source, revoked item, duplicate
excerpt and superficially similar but unsupported claim. Compare no memory,
goal-filtered lexical retrieval and the existing hybrid method on the same sources.

Measure relevant-source precision/recall at 3, wrong-goal/stale/removed retrievals,
correct URL/date attribution, unsupported support claims, owner connection-usefulness
ratings and actual additional calls/latency. For the safety exclusions, require
zero retrieved revoked/wrong-owner records. Report raw small-sample counts and
negative results rather than declaring superiority. Any paid analysis comparison
needs a separately approved budget and frozen protocol.

## Owner decision

After ALIVE-11 review, decide whether this bounded two-page, opt-in projection is
worth the remaining hackathon time. Broader Hacker News, Hugging Face, GitHub or
research-article observation requires separate page authorisation and a later
qualification. Full browser-history ingestion and personal-attribute inference
remain outside scope.
