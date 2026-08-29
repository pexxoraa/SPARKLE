# External worker

## Scope

`sparkle-worker` is a separately installable standard-library HTTP service for
one operation: `SPARKLE-WORKER/1` `python_unittest`. It is not an agent, model
tool, shell, build farm, package installer, or general remote-execution API.
The main application submits a job only after explicit operator approval.

The service implements exact request validation, timestamped HMAC-SHA256
authentication, bounded bodies/files/output/concurrency, digest verification,
replay/idempotency storage, fixed execution, signed responses, and safe health
status. It shares no memory, knowledge, trace, provider, or application store.

## Threat model and controls

| Threat | Control | Current evidence |
|---|---|---|
| Arbitrary commands/arguments | Wire schema has no such fields; executor command is immutable | Validator and command-structure tests pass |
| Modified/stale request | Constant-time HMAC, five-minute freshness window, canonical body | Tamper/staleness tests pass |
| Job-ID reuse | SQLite job ID + request digest claim; exact replay only | Replay/conflict tests pass |
| Traversal/symlink/secret source | Strict POSIX paths, sensitive-name/suffix rejection, decoded digest/key scan, exclusive materialization | Adversarial tests pass |
| Secret disclosure | Separate resolver, no-follow private file open, cleared child env, exact-key and pattern redaction, safe logs/status | Permission/symlink/redaction tests pass |
| Host filesystem access | Bubblewrap read-only runtime plus one writable ephemeral workspace | Command/preflight tests pass; live host preflight blocked |
| Network access | All namespaces unshared; preflight attempts an outbound connection and requires failure | Command/preflight tests pass; live host preflight blocked |
| Resource exhaustion | Body/file/output bounds, semaphore, wall timeout, process-group kill, POSIX CPU/memory/file/FD/process/core limits | Bound/capacity/timeout tests pass |
| Container misconfiguration | Unprivileged UID, read-only root, no capabilities, no-new-privileges, internal worker port, TLS gateway | Deployment-policy regression test passes; image build awaits CI |

Authenticated sandbox booleans describe the worker's executor. The main client
still records `isolation_verified: false`: a signed claim is not independent
proof. Changing that field requires a named deployment, captured preflight,
hostile canary suite, and operator-reviewed evidence.

## Executor modes

`bubblewrap` is the production default. Its readiness preflight creates a real
sandbox and checks that a host canary is absent, only the fixed environment
exists, and outbound network connection cannot succeed. A missing dependency,
timeout, denial, or nonzero result makes readiness false and jobs return 503
without running source.

`process` exists for deterministic local protocol and integration testing. It
requires `SPARKLE_WORKER_ALLOW_UNSAFE_PROCESS_EXECUTOR=true`; status and signed
results always report filesystem/network isolation false. It must not receive
hostile code.

## Deployment

The supported reference assets are in `worker_environment/`:

- `Dockerfile` installs only SPARKLE, Python, Bubblewrap, and CA certificates;
- `compose.yaml` adds a read-only worker, private state/tmp, file-mounted key,
  internal-only port, and a Caddy TLS gateway;
- `sparkle-worker.service` supplies a hardened unprivileged systemd profile;
- `README.md` contains exact provisioning and readiness commands.

The signing key must contain 32–4096 bytes. Generate and deliver it through the
deployment secret manager; do not put it in source, Compose environment,
command arguments, logs, memory, knowledge, traces, issues, or chat. Both the
client and worker need the same value.

## Verified local result

On 2026-08-29, the real signed client → service → process executor → signed
response path ran a submitted unittest that imported submitted application
code. Response authentication passed and the process executor correctly
reported no filesystem/network isolation. The real Bubblewrap preflight ran
and safely refused readiness because this build executor does not allow the
required namespace setup. Therefore protocol integration is tested, but live
hostile-code isolation and remote deployment remain blocked rather than passed.
