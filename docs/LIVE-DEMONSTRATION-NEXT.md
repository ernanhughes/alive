# Next product milestone — Visible continuing intelligence

P3 closes the planned learner diagnostic. Prioritize one live experience rather than another
learner optimization cycle. The evidence favors exposing useful history before increasing
model complexity; it does not establish that a predictive regularizer improves decisions.

Build a single, reviewable browser demonstration around the existing laboratory and Governor:

1. **Observe:** open an explicitly consented controlled page. Show the current observation and
   the recent events used to construct state. Distinguish source replacement from corroboration.
   Synthetic embeddings are not to be presented as actual browser semantic embeddings.
2. **Predict:** display a simple experience-based prediction for retrieving evidence versus
   monitoring, including its sample count, uncertainty, anticipated resource use and model version.
   Keep a frozen history-aware baseline beside it, with the same information.
3. **Choose:** make a shadow recommendation. Show what evidence and past outcomes support it.
   A recommendation has no tool permission. Actual actions pass the existing deterministic Governor.
4. **Act and observe:** execute a bounded permitted action, display the actual subsequent state,
   reward and usage, then record prediction error. Provider usage must be real when Meta is used;
   simulated rewards and virtual costs must remain explicitly labeled.
5. **Learn:** append the completed transition, perform a bounded validated controller update,
   and persist replay identity and before/after model hashes. Never train on a predicted outcome
   as if it were observed feedback. Do not introduce another model role.
6. **Revisit:** present a predetermined later situation with matched current features and relevant
   history. Display before/after recommendations and the unchanged baseline. If the decision
   does not change or deteriorates, show that result rather than selecting a favorable example.

Acceptance should verify actual page observations, pre-action forecasts, observed feedback,
persisted transitions across restart, a real model update, and an honestly reported later choice.
The live UI must let the owner stop the loop and inspect what was learned. Model updates cannot
expand permissions or reset budgets. Start in the controlled habitat and shadow mode before
considering any influence on unrestricted browsing.

P3's hand-designed history flag is not a deployed memory system. Extracting and validating the
corresponding state from a real browser event stream is the central implementation task here.
Success means a coherent and auditable observe → predict → choose → act → learn experience.
Any claim of improved decisions still requires a separate unchanged held-out comparison.
