# Data flow and tracing

```mermaid
sequenceDiagram
    participant U as User interface
    participant O as Orchestrator
    participant C as Context stores
    participant M as Model adapter
    participant T as Tool registry
    participant R as Trace store
    U->>O: Request
    O->>C: Relevant context
    O->>M: Provider-neutral request
    M-->>O: Text or tool calls
    O->>T: Allowed tool call
    T-->>O: Result
    O->>R: Outcome metadata
    O-->>U: Verified response
```

Every run records trace ID, source, agent, model, provider, tools, data stores
accessed, transformations, destinations, status, safe result summary, error
type, timestamps, and duration. Traces exclude authorization headers, request
bodies, provider thinking blocks, and secret values.

Scheduled work follows the same orchestrator path after an automation record is
atomically claimed. Its trace source is `automation`; run status, attempts,
trace ID, and bounded result summary are stored separately in the automation
database. Daily and weekly records are rescheduled only after the run is
recorded.

Generated-agent installation follows approval → manifest validation → SQLite
persistence → in-process registry load. Application scaffolding follows
approval → name/path/size validation → confined file writes → SHA-256 build
record. Neither path stores a secret or executes an arbitrary command.

Artifact packaging follows approval → confined workspace selection → stable
no-follow regular-file reads → portable path and size checks → per-file/source
digests → deterministic ZIP and embedded manifest → immutable target integrity
check → package record. Deployment reporting is a separate approval-gated
append-only record; it never invokes a target and always remains unverified.

Workspace verification follows approval → project/path/type/size validation →
non-executing parser/compiler check → bounded result → persistent verification
record. The Node syntax checker receives a minimal environment with no provider
credentials and cannot select an arbitrary executable or argument list.

Workspace test execution follows explicit runtime opt-in → per-run approval →
strict parent-environment allowlist → complete workspace/symlink/size scan → trusted child
runner → fixed unittest discovery → POSIX resources and wall timeout → redacted,
bounded persistent result. No user/model field becomes a command or argument.
The worker reports that filesystem/network isolation is absent and refuses
non-allowlisted parent environments; production hostile-code execution still
requires a separately deployed hardened container worker.

External worker submission follows operator approval → enabled/configured
check → secret-key resolution → confined workspace scan → hidden/sensitive/
binary/symlink/size/key-value rejection → canonical bounded source payload →
timestamped HMAC HTTPS request → bounded response read → HMAC/freshness/job/
schema/status verification → output redaction → result record. The signing key,
endpoint, and submitted bundle are not persisted. Sandbox fields are stored as
claims; isolation remains unverified until separate deployment evidence exists.

At the separate worker, TLS termination → bounded body read → HMAC/freshness
validation → exact schema/path/digest validation → job-ID/request-digest claim
→ isolation readiness check → ephemeral materialization → fixed unittest
runner → bounded/redacted output → signed response → replay record. The worker
has no model, agent, general shell, dependency installer, application database,
or provider credential. Its health output contains configuration booleans and
safe failure types, never the endpoint, key, source, or state path.

Every `/api/` request first consumes a bounded in-memory per-client quota, then
passes exact-origin validation and, when enabled, bearer or browser-session
authentication before its body is read or any application state is accessed.
Token values come from the secrets resolver, are compared in constant time, and
are never placed in status, traces, or logs. The login route exchanges a valid
bearer credential for a host-only HttpOnly cookie; the raw session ID is sent
only in `Set-Cookie`, hashed in process memory, and never persisted. A separate
CSRF token is returned only to the authenticated same-origin page and is
required on every cookie-authenticated mutation. OPTIONS preflight is rate- and
origin-gated but does not require the browser to transmit a credential.

Before response headers are sent, one query-free audit record is written with
method, route path, status, coarse outcome, duration, and timestamp. The audit
boundary deliberately has no fields for client identity, origin, headers,
query values, bodies, or credentials. An audit write failure cannot interrupt
the response path. Unknown API paths are stored and logged only as
`/api/[unknown]`.
