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
- Natural-language AI-system conversion requires explicit approval before the
  text is disclosed to the configured model provider. It uses the isolated
  no-history/no-user/no-context/no-tool profile, rejects tool calls, requires
  exact duplicate-free JSON plus complete Blueprint validation, and persists
  only bounded content-free evidence. Provider semantic fidelity is not
  inferred from schema success.
- AI-system implementation planning revalidates the Blueprint, emits only
  deterministic confined proposed paths, and requires separate approval before
  writing the plan manifest. The write uses the bounded workspace manager with
  overwrite protection. Evidence excludes plan content, purpose, workflow,
  criteria, and source. Plan materialization does not approve or execute source
  generation, testing, external-worker submission, or deployment.
- Source-candidate generation additionally requires reviewed-plan approval,
  separate provider-disclosure approval, and per-generation approval. Exact
  duplicate-free JSON is bounded by file count and bytes and restricted to
  plan-declared paths. Candidates live outside application and production
  trees. Provider metadata is stored separately without credentials or source.
  Human review, static verification, and final candidate approval are distinct
  transitions and cannot be inferred or skipped.
- Candidate static verification performs path/manifest/digest/configuration
  validation, Python AST and JavaScript syntax checks, local import/dependency
  consistency, formatting checks, and credential/security-pattern scans. It
  never imports candidate Python, runs candidate tests, installs dependencies,
  calls the external worker, promotes source, or claims runtime correctness.
- Runtime evaluation requires explicit approval and an already approved source
  candidate with the exact plan ID. The contract is strict and bounded to the
  fixed Python unittest operation; it accepts no executable, argument list,
  shell, dependency installer, or deployment action. Harness paths are confined
  to `tests/test_*.py` in an evaluator-owned workspace.
- Runtime bundles use the existing HTTPS/HMAC worker protocol. Approved timeout
  and output limits are signed with the bundle; authenticated responses are
  identity/schema/size/freshness checked and replay conflicts fail closed.
  Results persist output digests/lengths rather than output or source. Worker
  claims never set independent isolation evidence.
- Controlled source promotion requires a separate expiring approval after a
  successful runtime result. Approval and request are bound to authoritative
  candidate/plan/evaluation digests, actor, and origin. Promotion re-reads and
  hashes candidate content, rejects invalidation, supersession, tampering,
  stale or mismatched approval, traversal, replay conflict, and overwrite, and
  writes exact bytes only through a locked temporary tree and atomic rename
  into `promotion_environment/staging`. It records no source or secret and
  cannot build, package, publish, deploy, or modify production source.
- Controlled execution requires a separate expiring authorization after build.
  It binds every authoritative lineage identity plus the exact provider-neutral
  execution policy, timeout, and output bound,
  rejects invalidated or superseded artifacts, validates the immutable archive
  and every extracted entry, and rechecks the archive immediately before the
  worker handoff. Requests and responses are HMAC-authenticated and freshness
  checked; worker replay storage and controller request identity prevent silent
  duplicate or conflicting execution. The child receives a minimal environment
  and no SPARKLE credentials. Network policy is disabled by default.
- The hardened systemd worker explicitly leaves `ProtectKernelTunables=no`
  because its API-filesystem namespace setup blocks Bubblewrap's required
  private `/proc` mount on the supported Ubuntu host. The dedicated
  unprivileged identity, empty capability and ambient-capability sets,
  `NoNewPrivileges=yes`, strict read-only host filesystem, module/log
  protections, and per-job Bubblewrap boundary remain enforced. The exception
  is accepted only when the real service-scoped preflight passes all canaries.
- Process-mode execution is Level 2 functional evidence, not hostile-code
  isolation. Level 3 requires the real Bubblewrap preflight and harmless
  host filesystem read/write, workspace escape, environment-secret, prohibited
  network, host-process, and artifact-modification canaries to pass on the
  deployed worker. The artifact is mounted read-only. They fail closed in the
  build executor because namespace creation is denied; that result is not used
  to override evidence from, or substitute for, the dedicated Linux host.
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
  insufficient declarations. SPARKLE pins the expected worker identity and sets
  `isolation_verified` only when the signed response matches the fixed profile,
  every named canary is true, and filesystem/network claims agree. The current
  repository still reports false because no named validated worker exists. It contains
  hardened deployment profiles but no named validated remote worker and
  performs no automatic submission retries.
- Permanent memory, knowledge-source, and automation deletion requires an
  explicit API approval flag.
- Automation actions are limited to validated SPARKLE agent requests with one
  to three attempts or strict dashboard-notification actions; arbitrary
  commands are not accepted.
- Dashboard notifications validate channel, severity, title/body lengths,
  dedupe keys, retry bounds, and exact automation fields before persistence.
  The store is capped at 1,000 records. Notification content is intentionally
  user-visible in its API/UI but is excluded from execution traces and run
  summaries.
- Proactive rules inspect only bounded structured metadata in eligible memory
  categories. They do not parse memory free text, expose memory values, or let
  condition records add unknown fields. Condition alert/category/key filters
  are allowlisted and cooldowns are restricted to 1-10,080 minutes.
- Schedule conflicts require two valid explicit intervals, reject past,
  reversed, over-seven-day, and beyond-30-day evidence, and compare at most 200
  recent records. Evidence exposes only normalized overlap data plus the other
  record's ID/category/key; record values are never serialized.
- Research monitoring requires an explicit boolean opt-in and a validated
  1-64 character monitor key. Knowledge metadata is capped at 4 KiB and source
  comparisons are bounded. Content digests remain in the separate knowledge
  database; proactive output excludes content, title, URI, and digest and
  exposes only opaque source IDs and normalized timing.
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
- Explicit content envelopes allow at most 16 parts and 8 MB decoded content;
  model requests allow at most 256 messages and 16 MB decoded content. Text,
  image, audio, document, metadata, and HTTP body sizes have independent hard
  bounds. Binary input requires canonical base64 and a compatible MIME family.
- Content metadata accepts only bounded deterministic JSON with validated keys,
  finite numbers, and no credential-like field names. Content identifiers are
  derived from validated type, MIME type, and bytes, so callers cannot inject
  arbitrary trace identifiers.
- Multimodal traces contain only type, content-derived identifier, MIME type,
  size, and digest; raw strings, binary/base64 values, and general caller
  metadata are not serialized. Adapters fail closed before provider access
  when a request contains an unsupported modality.

Production deployment still needs multi-user role/owner authorization, TLS at the edge,
distributed/edge rate limiting, audit retention, backup encryption, dependency scanning,
containerized filesystem/network isolation for test/build execution, and a
threat-model review.

NVIDIA and MiniMax credentials are environment or secret-manager references,
never registry values. Model request evidence stores identities, policy reason,
timing, retry/fallback state, optional provider-reported usage, and safe error
classes only. Test-harness executions are explicitly marked and cannot satisfy
live-provider verification. Provider error bodies are reduced to bounded safe
messages; authentication failures never echo submitted keys.
