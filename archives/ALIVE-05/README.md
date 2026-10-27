# ALIVE-05 qualification — PASS_WITH_LIMITATIONS

The native Chrome documentation companion ran against the two explicitly authorised
public pages. The live Meta ledger contains **2 calls, 2,347 tokens and $0.00521675
estimated inference cost**. Both notes passed the exact-excerpt quotation check.
Costs are estimates from reported usage, not provider invoices.

An unrated Python note remained available without changing the analyse recommendation.
A qualification operator deliberately marked the inspected note useful. After closing
Chrome and restarting the backend, the same goal, URL and excerpt hash selected recall
of the original note, with **0 additional Meta calls**. The recorded no-feedback
comparison selects analyse on that same state. This demonstrates the implemented
feedback-driven reuse rule; it does not establish improved task accuracy or a learned
representation advantage. The feedback was automated engineering qualification,
not a user study or an independently measured environment reward.

Validation: **89 backend, 4 frontend and 6 dashboard browser tests**, plus native
feedback/restart-recall/MDN journeys and the local MV3 regression. Ruff and production
dashboard build pass. The pre-existing Windows ZeroMQ selector-thread warning remains.

The first native model invocation succeeded, but the initial runner failed to retrieve
its completed note through a CDP-evaluated runtime message. Its durable original note,
snapshot and decision were recovered without repeating inference. Later qualification
used actual panel completion state and the authenticated notes API. Unpacked MV3 worker
caching required a clean development test profile after source edits. No favourable
model output was selected from multiple attempts: the archive accounts for both paid
attempts, and both completed successfully.

`evidence.json` preserves every ALIVE-05 persisted row and all Meta usage, reservations,
latency, errors and output. Raw excerpts are replaced by their hashes and lengths;
instance IDs are hashed. Browser profiles, local tokens, API keys and unrelated browsing
are excluded. `native-recall.png` is an actual native-panel capture, with connection,
raw excerpt and runtime identity disclosures collapsed before capture. It is not a
generated mockup. `manifest.json` records payload and relevant implementation hashes.

The [protocol, installation and demo script](../../docs/ALIVE-05.md) define the scope.
The public demo is a labelled static replay of this evidence. The live backend remains
on localhost. Page content is observed text; notes are model interpretations; goals
are instructions; usefulness ratings affect reuse only. General websites, page writes,
account browsing, whole-page change detection and automatic truth verification remain
outside this qualification.

Sources: [Python tutorial](https://docs.python.org/3/tutorial/) (Python Software Foundation)
and [MDN JavaScript Guide](https://developer.mozilla.org/en-US/docs/Web/JavaScript/Guide)
(MDN contributors). Original excerpts remain local; the public archive includes bounded
model interpretations and short evidence quotes with provenance.
