# Dashboard

Run `sparkle serve`, then open `http://127.0.0.1:8765`.

Implemented panels:

- Command console with normal or multi-agent execution.
- System state, active model, storage counts, voice state, and agents.
- Durable memory records.
- Execution trace list.

The server sets no-store on JSON, denies framing, disables MIME sniffing, uses a
self-only Content Security Policy, limits JSON bodies to 1 MB, and does not log
headers or bodies. Authentication is not yet implemented; bind to localhost in
this release.
