# Application Builder

The Application Builder is implemented as a specialized agent routed to a
coding-capable model and allowed safe file/context tools. Its instruction covers
requirements, UX, architecture, implementation, tests, packaging, and
deployment. It can invoke an approval-gated workspace scaffold with a project
name and UTF-8 file map.

Workspaces are confined beneath the configured applications data root. The
manager rejects absolute paths, traversal, symlinks, invalid project names,
unapproved overwrites, more than 100 files, files over 250 KB, and manifests
over 1 MB. Each write records its byte count and SHA-256 digest in
`data_environment/builds.sqlite3`.

```bash
sparkle scaffold app.json --approve
```

An approved verification manifest can statically compile Python without
execution, ask Node.js to check JavaScript syntax, and parse JSON. Every check
is confined to the project, bounded, and recorded in
`data_environment/verifications.sqlite3`.

```bash
sparkle verify-workspace verification.json --approve
```

An explicitly enabled dedicated worker can execute one fixed test operation:

```bash
SPARKLE_WORKSPACE_TESTS_ENABLED=true sparkle test-workspace robot_dashboard --approve
```

The runner accepts no command or argument input. It scans and bounds the whole
workspace, rejects symlinks, strips the child environment, applies POSIX
resource limits, kills the process group on wall timeout, redacts bounded
output, and records results in `data_environment/test_runs.sqlite3`. It refuses
to start unless the parent environment matches a narrow explicit allowlist.

This is not a container sandbox: filesystem and network isolation are false and
reported as such. Use only a disposable, secret-free worker. Arbitrary shell,
application, package-install, and build commands remain unavailable. A hardened
container worker, packager, and deployment adapter are still required before
autonomous application delivery can be marked complete.

## Signed external worker boundary

SPARKLE also implements the client boundary needed to move the same fixed test
operation out of the API process. It is disabled by default and is intentionally
not registered as an agent-visible tool. After a compatible worker has been
deployed and independently hardened, configure its HTTPS endpoint and
secret-managed signing key, then invoke it as an operator:

```bash
export SPARKLE_EXTERNAL_WORKER_ENABLED=true
export SPARKLE_EXTERNAL_WORKER_URL='https://worker.example/v1/jobs'
export SPARKLE_WORKER_SIGNING_KEY='set-through-a-secret-manager'
sparkle test-workspace-external robot_dashboard --approve
```

The request uses protocol `SPARKLE-WORKER/1`, a unique job ID, a fixed
`python_unittest` operation, requested limits, and a bounded base64-encoded
UTF-8 source bundle with per-file SHA-256 digests. Timestamped HMAC-SHA256
headers authenticate both directions. Responses must be fresh, correctly
signed, schema-exact, job-matched, type-bounded, and status-consistent.

Submitting a workspace transfers its accepted source files to the configured
endpoint. Hidden, symlinked, binary, oversized, secret/credential-like, and
signing-key-containing files are refused; this does not prove the absence of
all application secrets, so approval must follow a source review. Results live
in `data_environment/external_worker_runs.sqlite3`. Sandbox fields are retained
as worker **claims**, while `isolation_verified` remains false until a real
deployment has separate end-to-end isolation evidence. This repository does
not yet contain or claim a hardened container-worker deployment.
