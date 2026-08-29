# Troubleshooting

## `status: limited`

The core is ready but neither `MINIMAX_API_KEY` nor `SPARKLE_LLM_API_KEY` is
present in the server process. Configure one in the hosting secret manager and
restart/redeploy the process.

## Live smoke authentication failure

Check that the key is active and belongs to the intended MiniMax plan. Do not
print it. Run `sparkle status` to verify presence only, then retry once.

## Rate or temporary errors

The adapter retries MiniMax codes 1000, 1001, 1002, 1024, and 1033 plus HTTP
408, 429, and common 5xx statuses with exponential backoff. Persistent errors
remain visible as failures and are traced by error type.

## Dashboard unavailable

Run `sparkle serve`, confirm the printed bind address, and check that the port is
free. Do not expose the alpha server directly to the public internet.

If API authentication is enabled, the dashboard displays its authentication
gate. Enter the configured API access token; the page exchanges it for an
HttpOnly session cookie and does not retain it in browser storage. Repeated 401
responses mean the token is wrong, the bounded session expired/was evicted, or
the server restarted. Authenticate again without printing the token.

## API startup refuses the bind

A non-loopback host requires `SPARKLE_API_AUTH_REQUIRED=true` and a configured
`SPARKLE_API_TOKEN` secret reference. Required authentication also fails closed
on loopback if the token is absent. Use `sparkle status` to inspect presence
only; never print the value.

If dashboard sessions are enabled, non-loopback startup also requires
`SPARKLE_SESSION_COOKIE_SECURE=true` and a trusted TLS-terminating reverse proxy.
For a bearer-only API, set `SPARKLE_SESSION_AUTH_ENABLED=false`. Do not disable
secure cookies to expose the dashboard over plain HTTP.

## API returns 403 origin_not_allowed

Use the same origin as the API, or add the exact trusted HTTP(S) origin to
`security.allowed_origins`. Wildcards, URL paths, credentials, queries, and
fragments are intentionally invalid.

## API returns 429 rate_limited

Honor the response's `Retry-After` value before retrying. For a trusted local
deployment, adjust `security.rate_limit_requests` and
`security.rate_limit_window_seconds` within the documented bounds, then restart
the server. Repeated unauthorized and origin-denied attempts also consume the
quota by design.

## PDF/DOCX ingestion unavailable

Install `python3 -m pip install -e '.[documents]'`.

## Workspace tests are disabled

This is the safe default. Set `SPARKLE_WORKSPACE_TESTS_ENABLED=true` only in a
dedicated disposable POSIX worker, then pass `--approve` for the individual run.

## Workspace tests require a secret-free worker

SPARKLE detected a non-empty parent variable outside the runner's narrow
allowlist and refused to execute generated code. Do not remove credentials from the live API process
just to bypass this control. Start a separate sanitized worker containing only
the data-root and workspace-test configuration variables. Filesystem and
network isolation are still absent, so use non-hostile code only.

## External workspace worker is unavailable

The external path is disabled unless `SPARKLE_EXTERNAL_WORKER_ENABLED=true`, a
valid credential-free HTTPS URL is configured, and the configured signing-key
reference resolves to at least 32 bytes. Every CLI/API submission also needs
explicit approval. Do not paste the key into configuration, logs, issues, or
chat. A signature, timestamp, job-ID, schema, size, or status mismatch is a
hard failure and should be investigated at the worker; SPARKLE does not retry
or accept an unsigned fallback. This release includes a reference worker but no
instance is deployed in the verified environment, so a live remote test remains
blocked until one is independently provisioned.

## `sparkle-worker --check` exits 2

This is a safe isolation refusal. Inspect the structured `executor.failure_type`
without exposing the signing key. Confirm Linux user namespaces and Bubblewrap
are permitted for the unprivileged service account. Container runtimes must
allow nested unprivileged namespaces; never fix this with `--privileged`.

The current build executor exposes Bubblewrap but denies the required namespace
operation, so readiness is false here. Use `process` mode only for loopback
protocol development; it intentionally reports both isolation fields false.

## Worker returns conflict

A job ID is bound to the SHA-256 digest of its exact canonical request. An exact
completed duplicate replays the signed result. A different body using the same
ID, or a duplicate while the first job is running, returns HTTP 409. Generate a
new job ID instead of deleting replay records.
