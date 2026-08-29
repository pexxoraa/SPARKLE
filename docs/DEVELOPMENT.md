# Development

1. Add domain code beneath `src/sparkle/`.
2. Keep provider behavior beneath `providers/`.
3. Add or change configuration without embedding credentials.
4. Add deterministic tests for success, failure, and security boundaries.
5. Run `make check` before committing.
6. Update `BUILD_STATE.md` and `ACCEPTANCE.md` using actual evidence.

To add a provider, implement `ModelAdapter.complete()`, optionally `stream()`,
and `health()`, register the adapter class, add a model record, and test the
mapping with a fake HTTP opener. Do not add provider types to agents.

## Generated-workspace verification

`DevelopmentVerifier` supports only `python_compile`, `javascript_syntax`, and
`json_parse`. Python uses the built-in compiler without executing the module.
JavaScript uses an absolute Node.js binary with `--check`, a five-second timeout,
no shell, a minimal environment containing no SPARKLE/provider secrets, and
bounded output. JSON is parsed without application hooks.

Checks are confined to an existing generated project and reject traversal,
symlinks, wrong file types, missing files, undeclared fields, more than 50
checks, and files over 500 KB. Syntax failures are successful verifier
executions with a recorded `failed` result; verifier contract violations are
client errors.

Do not widen this verifier into a general command runner.

## Generated-workspace tests

`WorkspaceTestRunner` is a separate, disabled-by-default boundary. It runs only
the trusted isolated-mode `sandbox_runner.py`, which applies limits and performs
fixed `tests/test*.py` unittest discovery. It accepts a project name and
approval—not an executable,
arguments, environment, or package list.

Before execution it validates the workspace name/root, rejects every symlink,
requires `tests/test*.py`, and bounds files, individual size, and total bytes.
The child receives a fixed environment and POSIX CPU, address-space, output-
file, descriptor, process, and core limits. The parent applies a wall timeout
to the entire process group; output is path-normalized, credential-pattern
redacted, truncated, and persisted.

The runner refuses any non-empty parent variable outside a narrow explicit
runtime/configuration allowlist. Run it in a dedicated sanitized worker. It
does not isolate the filesystem or network, so it is not suitable for hostile
code or a production multi-tenant service.

## External worker protocol

`ExternalWorkerClient` is an operator-only client boundary, not a sandbox. Keep
`ExternalWorkspaceTestTool` out of `ToolRegistry`: a model must never create its
own approval for source transfer. The wire contract is fixed at
`SPARKLE-WORKER/1` and `python_unittest`; do not add executable, argument,
environment, dependency-install, or general command fields.

Requests and responses use canonical JSON and a timestamped HMAC-SHA256 over
`timestamp + "." + body`. Preserve exact response-field validation, clock-skew
checking, job matching, bounds, safe-error wrapping, and output redaction. Do
not enable redirects or treat authenticated sandbox declarations as isolation
evidence.

The reference server lives in `worker_service.py`, its fixed executor in
`worker_executor.py`, and deployment assets in `worker_environment/`. Do not
widen the request schema. The default executor must fail closed when its
Bubblewrap preflight cannot prove filesystem/environment/network boundaries.
The `process` executor requires an explicit unsafe opt-in and must never report
isolation. Replay records bind each job ID to one request digest; the same body
is idempotent, while a changed body or in-flight duplicate conflicts.

See `WORKER.md` for the threat model and executed evidence. `isolation_verified`
remains false on the application side until a named deployment has separate,
host-specific validation evidence.
