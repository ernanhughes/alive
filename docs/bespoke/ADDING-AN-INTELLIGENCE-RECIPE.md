# Adding an Intelligence Recipe to ALIVE

1. Choose an existing installed, trusted capability set. Inspect the capability catalogue and
   its exact versions, manifest hashes, permission declarations and effective limits. Missing
   source/semantic operations require PI-03B/03C; a recipe cannot implement them.
2. Choose an existing registered versioned workflow. The reviewed JSON examples in `workflows/`
   show the actual existing contracts. Registration remains a trusted host action:

   ```python
   import json
   from pathlib import Path
   from alive.workflows.store import register_definition

   # Existing kernel in a trusted administrative or controlled-laboratory process only.
   raw = json.loads(Path("docs/bespoke/workflows/source-comparison.json").read_text())
   definition, created = await register_definition(kernel, raw, status="active", source="admin")
   ```

3. Write YAML using `alive/bespoke/recipes/controlled-comparison.yaml` as a real example. Pin the
   workflow's exact canonical hash and every stage's capability ID/version/manifest hash. Declare
   source types, explicit intents, evidence, permissions, budgets, output and validation accurately.
4. Validate with `parse_recipe` and the existing workflow registrar. They reject unknown YAML
   keys, executable constructs, contract mismatches and immutable version conflicts. Use a new
   version for changed published content; retain old historical identity.
5. Add the code-owned YAML to the package catalogue and restart the application. There is no
   public upload, plugin installation or hot-reload route. The workflow must be independently
   registered; loading recipe YAML does not register it.
6. Open Bespoke in the dashboard. Inspect dependency compatibility and bounded missing reasons.
   Installed never means contextually eligible or authorized.
7. Add independent expected suitability/refusal cases. Check exact compatibility, missing inputs,
   permissions, budgets, source approval, correct abstention and genuine procedural diversity.
8. Select an approved capture and explicit objective. Inspect the retained suitability factors,
   graph above details, exact identities, alternatives and uncertainty.
9. Production authorization is currently unavailable. In a disposable controlled laboratory,
   use the existing `fixture_authorization`, then `trusted_handoff`, followed by the **existing**
   `WorkflowRunner`. Never create a shortcut HTTP grant or execute route.
10. Follow the linked actual run to the Workflow Observatory. Inspect stage contracts, provenance,
    outcomes and artifacts; distinguish completion from independently verified success.

The fully reproducible laboratory example is `scripts/bespoke_check.py`. It performs all real
registration, capture, independent fixture approval, selection, handoff, execution and inspection
steps. It can serve the disposable recorded history for browser testing with `--workspace` and
`--serve`. Do not point it at a personal/production database.
