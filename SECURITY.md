# Security

ALIVE-01 is a single-user local development runtime. Bind it to `127.0.0.1`; do not expose it through a public tunnel. HTTP data access and mutations require a bearer token. WebSockets require a first-frame token and an allowed origin. CORS is additional browser isolation, not authentication.

Never commit `.env`, `.alive`, tokens, database passwords, Chrome profiles, browsing data or generated logs. The extension/frontend must never contain provider credentials. Use a long random token. Rotate a leaked token in local configuration and clear dashboard/extension storage.

Browser network requests require exact allowed origins. Interaction requires page-declared operation permission and rejects sensitive fields. Playwright uses separate contexts, blocks service workers/downloads and closes popups. Treat webpage content as untrusted. Do not configure private-account, authentication, payment or destructive workflows for this milestone. Screenshots are demonstration-only.

Pi is launched without tools, extensions, MCP or context-file discovery. It receives only explicitly submitted objectives, with one concurrent run and a timeout. Proposed goals never grant action authority. Keep these restrictions when extending ALIVE.

Observation text excludes inputs, textareas, selects, editable/private/hidden regions. Visible text elsewhere may still contain sensitive information: authorize pages deliberately and review previews before sending. Backend history is locally persistent and is not encrypted by ALIVE. This milestone has no multi-user permissions, secret vault or automated data-retention service.

For vulnerability reports, contact the maintainer privately through their GitHub profile's available contact channel. Do not include tokens or private observations in public issues. No security reporting address is invented here.

ALIVE-02 keeps model roles outside the authority boundary. Native structured outputs are revalidated, citations are scoped to supplied evidence, and the deterministic Governor reserves budget before inference. Class A effects are internal; Class B controlled drafts require explicit permission/approval; consequential external actions remain unsupported. Stop cancels work and revokes managed sensors. Restart pauses autonomy and never replays an external effect. Unknown interrupted inference retains a pessimistic token charge. Runtime and benchmark ledgers enforce their own experiment ceilings, not a provider-account billing quota.

The history importer handles explicitly submitted, previewed entries only; qualification uses synthetic records. Revocation deletes imported memories/vectors and preview content, but does not promise removal of every historical derived model summary or diagnostic snapshot. Model weights, inference reports and benchmark traces remain under ignored `.alive`. No complete personal browser history or private account automation is imported.
