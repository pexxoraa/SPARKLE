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

If API authentication is enabled, the built-in dashboard cannot submit or store
the bearer token and API requests return 401. Use an authenticated API client or
return to a loopback-only local configuration.

## API startup refuses the bind

A non-loopback host requires `SPARKLE_API_AUTH_REQUIRED=true` and a configured
`SPARKLE_API_TOKEN` secret reference. Required authentication also fails closed
on loopback if the token is absent. Use `sparkle status` to inspect presence
only; never print the value.

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
