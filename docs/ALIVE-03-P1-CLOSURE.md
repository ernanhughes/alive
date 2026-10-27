# P1 closure — accepted with limitations

Owner review on 27 October 2026 closes P1 without further policy or scorer tuning.
The reviewed history through `2d6a4d4` is published on
[`codex/alive-03-p1-selective-cognition`](https://github.com/ernanhughes/alive/tree/codex/alive-03-p1-selective-cognition).
It preserves the frozen corpus, model/prompt versions, failed case, 240-call ledger,
uncertainty intervals, execution authorization and $0.5689762 estimated inference cost.

Never and Selective achieved 120/120; Always achieved 119/120. Selective's threshold chose
Never-like behavior. This is not evidence of learned or adaptive routing. The one regression
retained the correct median and citations but changed the recommendation to investigate;
the original score stands. The simple policy's ceiling performance limits discrimination.

P2 starts from the same history in a separate branch. Runtime criticism now defaults off
for new instances and default configuration submissions. Explicit `use_critic=true` remains
supported and tested. Existing saved configurations are preserved; the owner's local instance
is deliberately changed to false. The frozen P1 configuration schema remains unchanged for
reproducibility; current runtime defaults are defined separately.

Future evaluations separate factual belief accuracy from decision outcomes and resource costs.
The next contribution concerns learning from completed action-dependent transitions, rather
than adding roles or presenting browser embeddings as reinforcement learning. See the
[P2 protocol](ALIVE-03-P2.md) and [unchanged P1 evidence](../archives/ALIVE-03-P1-FULL/README.md).
