# Contributing

Create a feature branch and make small, reviewable changes. New work must be written here; do not import private project implementations or data. Keep model/browser authority explicit and deterministic behavior inspectable.

Run backend Ruff/tests, dashboard tests/build, and relevant live acceptance checks. Document skipped integrations separately from mocked and live results. Include migrations for schema changes; never mutate a previously released migration. Keep credentials, profiles, observations and local evidence out of Git.

Pull requests should explain the concrete trigger, resulting behavior, validation and limitations. The project uses Apache-2.0; retain dependency/asset license obligations. Do not push, publish or deploy changes on another contributor's behalf without authorization.
