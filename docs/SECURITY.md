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
- Artifact packaging requires explicit approval, accepts only stable regular
  non-symlink files, rejects hidden/sensitive/reserved and non-portable paths,
  enforces file/count/total limits, and writes immutable content-addressed ZIPs
  with canonical manifests. Existing artifacts are digest-checked and never
  silently replaced. Deployment records execute no action and always remain
  explicitly unverified.
- Workspace verification requires explicit approval; supports only
  non-executing Python compile, Node `--check`, and JSON parse; rejects
  traversal, symlinks, undeclared fields, wrong types, and oversized inputs.
  Node runs without a shell, receives no inherited provider secrets, times out
  after five seconds, and produces bounded recorded output.
- Workspace test execution is separately disabled by default and requires
  configuration opt-in plus per-run approval. It accepts no executable or
  arguments, runs a fixed isolated-mode Python unittest discovery command,
  rejects symlinks/oversized workspaces, strips the child environment, applies
  POSIX resource limits, and kills the process group on wall timeout.
- The test worker refuses to run unless every non-empty parent environment
  variable is on a narrow runtime/configuration allowlist. Output is bounded
  and credential-pattern redacted. Filesystem and
  network isolation remain explicitly false; this boundary is for disposable,
  dedicated workers and is not a hardened sandbox for hostile code.
- External worker submission is a separate disabled-by-default, operator-only
  boundary and is not registered for model tool use. It requires per-run
  approval, an HTTPS URL without embedded credentials/query/fragment, and a
  secret-resolved signing key of at least 32 bytes.
- Source transfer is bounded to UTF-8 regular files and rejects symlinks,
  hidden paths, credential/secret-like paths and suffixes, oversized input, and
  any file containing the configured signing-key value. Accepted files are
  base64 encoded with SHA-256 digests; source bundles are not persisted in the
  result database.
- Requests and responses are timestamped and HMAC-SHA256 authenticated.
  Responses must be fresh, job-matched, exact-schema, bounded, and internally
  consistent, with HTTP 200, JSON content type, and the protocol header.
  Redirects are rejected so signed source cannot be forwarded to another
  origin. Transport failures are wrapped without endpoint or exception detail.
  Output is bounded and credential-pattern redacted before persistence.
- Worker-reported filesystem, network, ephemeral, and resource-limit fields are
  untrusted declarations. SPARKLE records them as `sandbox_claims` and always
  reports `isolation_verified: false` in this release. The repository contains
  hardened deployment profiles but no named validated remote worker and
  performs no automatic submission retries.
- Permanent memory, knowledge-source, and automation deletion requires an
  explicit API approval flag.
- Automation actions are limited to validated SPARKLE agent requests with one
  to three attempts; arbitrary commands are not accepted.
- Proactive rules inspect only bounded structured metadata in eligible memory
  categories. They do not parse memory free text, expose memory values, or let
  condition records add unknown fields. Condition alert/category/key filters
  are allowlisted and cooldowns are restricted to 1-10,080 minutes.
- The supervised automation entrypoint uses an owner-only no-follow POSIX lock,
  one active local instance, expiring claim tokens, recovery records, and
  token-fenced completion. Its status stores only bounded lifecycle/error-type
  metadata. Recovery is at least once, so future external actions must supply
  their own idempotency keys.
- Shell and web tools are disabled by default and not registered in this release.
- The HTTP server binds to localhost by default and supplies defensive headers.
- Every API route supports optional bearer authentication resolved from
  environment secret references. Comparison is constant-time; failures and
  status never contain the supplied or configured value.
- When API authentication is required, the dashboard can exchange that bearer
  credential for a 256-bit opaque, process-local session. Only a SHA-256 digest
  of the session ID is held in bounded memory; sessions have absolute expiry,
  oldest-entry eviction, explicit revocation, and no database representation.
- Browser cookies are host-only, HttpOnly, `SameSite=Strict`, path `/`, and
  configurable `Secure`. Every cookie-authenticated mutation requires a separate
  256-bit CSRF token held only in page/server memory. The dashboard never uses
  localStorage or sessionStorage for credentials.
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
- Session-enabled non-loopback startup also fails unless secure cookies are
  configured. A trusted TLS reverse proxy remains mandatory because the built-
  in server does not terminate or validate TLS.
- Provider reasoning blocks are preserved only for provider continuity and are
  neither displayed nor traced.

Production deployment still needs multi-user role/owner authorization, TLS at the edge,
distributed/edge rate limiting, audit retention, backup encryption, dependency scanning,
containerized filesystem/network isolation for test/build execution, and a
threat-model review.
