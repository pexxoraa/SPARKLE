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
- Provider reasoning blocks are preserved only for provider continuity and are
  neither displayed nor traced.

Production deployment still needs authentication, authorization, TLS at the
edge, rate limiting, audit retention, backup encryption, dependency scanning,
process/network isolation for future test and build execution, and a
threat-model review.
