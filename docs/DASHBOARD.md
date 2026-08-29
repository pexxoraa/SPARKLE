# Dashboard

Run `sparkle serve`, then open `http://127.0.0.1:8765`.

Implemented panels:

- Command console with normal or multi-agent execution.
- System state, active model, storage counts, voice state, and agents.
- Durable memory records.
- Automation, application-build, static-verification, execution-trace, and
  secret-free API-audit lists.

The server sets no-store on JSON, denies framing, disables MIME sniffing, uses a
self-only Content Security Policy, limits JSON bodies to 1 MB, and does not log
headers or bodies. API bearer authentication, exact origin controls, and
bounded rate limiting are implemented. The dashboard deliberately has no API-token input or storage; use
it on the default loopback, unauthenticated configuration. A secured remote UI
still requires a trusted authenticated frontend/session layer.
