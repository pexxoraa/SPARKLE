# Dashboard

Run `sparkle serve`, then open `http://127.0.0.1:8765`.

Implemented panels:

- Command console with normal or multi-agent execution.
- System state, active model, storage counts, voice state, and agents.
- Durable memory records.
- Automation, application-build, static-verification, bounded test-run,
  external-worker, immutable artifact, unverified deployment-event,
  execution-trace, and secret-free API-audit lists.

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
