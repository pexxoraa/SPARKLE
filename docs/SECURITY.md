# Security

- Secrets are resolved only from process environment references.
- `.env`, runtime databases, caches, coverage, and builds are ignored by Git.
- Secret status returns booleans, never values.
- Error messages omit authorization data.
- Trace serialization recursively redacts keys containing key/token/secret/auth.
- File reads are resolved and confined to the repository root.
- Calculator expressions use a restricted AST; calls and names are rejected.
- Tool definitions and executions are allowlisted per agent.
- Tool-call rounds and tool-result sizes are bounded.
- Shell and web tools are disabled by default and not registered in this release.
- The HTTP server binds to localhost by default and supplies defensive headers.
- Provider reasoning blocks are preserved only for provider continuity and are
  neither displayed nor traced.

Production deployment still needs authentication, authorization, TLS at the
edge, rate limiting, audit retention, backup encryption, dependency scanning,
and a threat-model review.
