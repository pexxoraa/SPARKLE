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
| Host filesystem access | Bubblewrap read-only runtime and read-only artifact mount; only sandbox-private temporary state is writable | Command/preflight tests pass; live host preflight blocked |
| Network access | All namespaces unshared; preflight attempts external and host-local connections and requires both to fail | Command/preflight tests pass; live host preflight blocked |
| Wrong worker | Application configuration pins the expected public worker ID and rejects a valid signed result from another identity | Identity-mismatch tests pass |
| Resource exhaustion | Body/file/output bounds, semaphore, wall timeout, process-group kill, POSIX CPU/memory/file/FD/process/core limits | Bound/capacity/timeout tests pass |
| Container misconfiguration | Unprivileged UID, read-only root, no capabilities, no-new-privileges, internal worker port, TLS gateway | Deployment-policy regression and repeated CI image build/entrypoint jobs pass |

Authenticated sandbox booleans describe the worker's executor. The main client
still records `isolation_verified: false`: a signed claim is not independent
proof. Changing that field requires a named deployment, captured preflight,
hostile canary suite, and operator-reviewed evidence.

Controlled execution uses `SPARKLE-WORKER-CONTROLLED-EXECUTION/1` over the same
service, HMAC, replay store, fixed executor, and `/v1/jobs` route. Its strict
context binds execution/request, artifact, build, promotion, candidate, plan,
evaluation, authorization, and mode identities. The signed result adds worker
identity, start/end timestamps, output digest, canonical result digest,
output-limit state, and executable isolation evidence. The fixed signed policy
is 512 MiB address space, CPU equal to the wall timeout, 32 processes, 5 MB
workspace input, bounded output, and network disabled.

## Executor modes

`bubblewrap` is the production default. Its readiness preflight creates a real
sandbox and emits exact results for host read/write, other-workspace access,
secret environment, external/host-local network, host process, and read-only
artifact modification canaries. A missing dependency, ambiguous result,
timeout, denial, or nonzero result makes readiness false and jobs return 503
without running source.

`process` exists for deterministic local protocol and integration testing. It
requires `SPARKLE_WORKER_ALLOW_UNSAFE_PROCESS_EXECUTOR=true`; status and signed
results always report filesystem/network isolation false. It must not receive
hostile code.

## Free/local development platform

`sparkle-worker --diagnose` runs without worker credentials. It executes and
records bounded user/mount/network namespace probes, a `no_new_privs` probe,
and the actual Bubblewrap hostile-canary preflight. Results use `AVAILABLE`,
`UNAVAILABLE`, or `NOT_VERIFIED`; the command never converts capability
detection into Level 3 evidence.

`worker_environment/bootstrap-local-worker.sh` creates an overwrite-protected,
Git-ignored development bundle containing a file-injected HMAC key, a seven-day
self-signed `localhost` TLS certificate, private key, state directory, and
externalized worker configuration. This bundle starts the explicit process
test harness and is always **NON-ISOLATED**. Automated tests connect using the
trusted development certificate, reject the untrusted certificate and wrong
hostname, and confirm private key modes. No credential value is logged.

## Deployment

The supported reference assets are in `worker_environment/`:

- `Dockerfile` installs only SPARKLE, Python, Bubblewrap, and CA certificates;
- `compose.yaml` adds a read-only worker, private state/tmp, file-mounted key,
  internal-only port, and a Caddy TLS gateway;
- `sparkle-worker.service` supplies a hardened unprivileged systemd profile;
- `install-systemd-worker.sh` installs an offline wheel and service without
  creating credentials or starting the worker;
- `worker.conf.example` externalizes worker identity, paths, limits, and policy;
- `README.md` contains exact provisioning and readiness commands.

The signing key must contain 32–4096 bytes. Generate and deliver it through the
deployment secret manager; do not put it in source, Compose environment,
command arguments, logs, memory, knowledge, traces, issues, or chat. Both the
client and worker need the same value.

## Infrastructure acceptance

The manual `SPARKLE Level 3 Worker Acceptance` workflow reads the endpoint and
pinned worker ID from protected environment variables and the HMAC key from an
environment secret. `worker_environment/level3_acceptance.py` submits a harmless
fixed unittest and requires authenticated, profile-matched, all-true canary
evidence. It intentionally reports `level_3_complete: false`: the final gate
still requires a real approved controlled-build artifact through the controller.
The workflow is manual-only and is not evidence until a named worker run passes.

## Verified local result

On 2026-08-29, the real signed client → service → process executor → signed
response path ran a submitted unittest that imported submitted application
code. Response authentication passed and the process executor correctly
reported no filesystem/network isolation. The real Bubblewrap preflight ran
and safely refused readiness because this build executor does not allow the
required namespace setup. Therefore protocol integration is tested, but live
hostile-code isolation and remote deployment remain blocked rather than passed.
On the v0.30 build host Bubblewrap 0.9.0 exists, but the executable preflight
returns `IsolationPreflightFailed` because namespace setup is denied. Therefore
Level 3 is blocked and `isolation_verified` remains false; this is not reported
as a missing binary or as a pass.
