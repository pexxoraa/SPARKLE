# Dashboard

Run `sparkle serve`, then open `http://127.0.0.1:8765`.

Implemented panels:

- Command console with normal or multi-agent execution.
- System state, active model, storage counts, voice state, and agents.
- Durable memory records.
- Read-only evidence-derived skill levels, targets, counts, and averages.
- Evidence-backed proactive alerts and automation execution history.
- Bounded dashboard notifications with delivery/read state and safe source
  labels.
- Application-build, static-verification, bounded test-run,
  external-worker, immutable artifact, unverified deployment-event,
  execution-trace, and secret-free API-audit lists.
- Persisted automation-service lifecycle state in system metrics.
- Multimodal contract status and limits in system metrics. The command console
  remains text-only; explicit content envelopes use the JSON API in this
  release.

The proactive list is read from `GET /api/proactive`. It shows only structured
evidence identifiers and classifications; memory free text and knowledge
source content are not returned to the panel. Memory and knowledge source IDs
are explicitly labeled. An empty list means no supported rule currently has
valid evidence, not that the system inferred an all-clear state.

The notification list is read from `GET /api/notifications`. Its title/body are
intentionally user-visible delivery content; notification content is not copied
into execution traces or automation run summaries. Read state is available
through the authenticated API.

The server sets no-store on JSON, denies framing, disables MIME sniffing, uses a
self-only Content Security Policy, limits JSON bodies to 1 MB, and does not log
headers or bodies. API bearer authentication, exact origin controls, and
bounded rate limiting are implemented. When API authentication is required, the
dashboard accepts the API token only in its password field, exchanges it for a
bounded process-local session, clears the field, and never writes either token
to local or session storage. The session cookie is host-only, HttpOnly, and
`SameSite=Strict`; state-changing requests also require an in-memory CSRF token.
Reload recovers CSRF state from the authenticated same-origin session endpoint,
and logout revokes the server-side session.

For non-loopback use, secure cookies and a trusted TLS-terminating reverse proxy
are mandatory. SPARKLE verifies the secure-cookie configuration but cannot
verify or provide edge TLS, proxy access policy, or deployment hardening.
