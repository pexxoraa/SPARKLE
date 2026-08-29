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
- Generated-agent installation and removal require explicit approval; manifests
  cannot replace built-in agents or reference unregistered tools.
- Application scaffolding requires explicit approval, confines every path to a
  dedicated application root, rejects traversal and symlinks, enforces file and
  manifest size limits, and protects existing files by default.
- Workspace verification requires explicit approval; supports only
  non-executing Python compile, Node `--check`, and JSON parse; rejects
  traversal, symlinks, undeclared fields, wrong types, and oversized inputs.
  Node runs without a shell, receives no inherited provider secrets, times out
  after five seconds, and produces bounded recorded output.
- Permanent memory, knowledge-source, and automation deletion requires an
  explicit API approval flag.
- Automation actions are limited to validated SPARKLE agent requests with one
  to three attempts; arbitrary commands are not accepted.
- Shell and web tools are disabled by default and not registered in this release.
- The HTTP server binds to localhost by default and supplies defensive headers.
- Every API route supports optional bearer authentication resolved from
  environment secret references. Comparison is constant-time; failures and
  status never contain the supplied or configured value.
- Same-origin API requests are allowed; cross-origin requests require an exact
  configured HTTP(S) origin. Wildcard origins are rejected. Preflight responses
  advertise only GET, POST, OPTIONS, Authorization, and Content-Type.
- A fixed-window limiter runs before origin and authentication checks. Its
  client buckets are thread-safe, expire by window, and are capped at 10,000;
  every API response includes limit/remaining headers and rejected requests
  receive HTTP 429 plus `Retry-After`.
- API outcomes are stored separately in `trace_environment/api_audit.sqlite3`.
  Records contain only method, query-free path, status, coarse outcome,
  duration, and timestamp. IPs, origins, headers, queries, bodies, and tokens
  are neither accepted by the store interface nor serialized by the handler.
  Unrecognized API paths are normalized to `/api/[unknown]` so path segments
  cannot become an accidental credential channel.
- Server startup fails if authentication is required but its token is absent,
  or if a non-loopback bind is requested without configured authentication.
- Provider reasoning blocks are preserved only for provider continuity and are
  neither displayed nor traced.

Production deployment still needs role/owner authorization, TLS at the edge,
distributed/edge rate limiting, audit retention, backup encryption, dependency scanning,
process/network isolation for future test and build execution, and a
threat-model review.
