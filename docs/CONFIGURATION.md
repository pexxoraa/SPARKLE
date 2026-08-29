# Configuration

Application behavior is configured in `application/config.json`. Model/provider
records and routes are configured in
`ai_environment/configurations/models.json`.

Environment overrides:

| Variable | Purpose | Secret |
|---|---|---|
| `MINIMAX_API_KEY` | Preferred MiniMax credential reference | Yes |
| `SPARKLE_LLM_API_KEY` | Existing deployment alias | Yes |
| `SPARKLE_DATA_DIR` | Runtime database root | No |
| `SPARKLE_HOST` | HTTP bind host | No |
| `SPARKLE_PORT` | HTTP bind port | No |
| `SPARKLE_API_AUTH_REQUIRED` | Override API bearer-auth policy | No |
| `SPARKLE_API_TOKEN` | Default API bearer-token reference | Yes |
| `SPARKLE_API_RATE_LIMIT_REQUESTS` | Requests allowed per client/window (1–10000) | No |
| `SPARKLE_API_RATE_LIMIT_WINDOW_SECONDS` | Fixed-window duration (1–3600 seconds) | No |
| `SPARKLE_WORKSPACE_TESTS_ENABLED` | Opt in to fixed Python workspace tests | No |
| `SPARKLE_WORKSPACE_TEST_TIMEOUT_SECONDS` | Test wall/CPU limit (1–60 seconds) | No |

Configuration files may contain secret *names* such as `MINIMAX_API_KEY`; they
must never contain secret values. Shell and web tools default to disabled.

`application/config.json` contains the `security` policy:

- `api_auth_required`: requires bearer authentication for every `/api/` route.
- `api_token_refs`: ordered environment secret reference names; never values.
- `allowed_origins`: exact HTTP(S) origins allowed in addition to same-origin.
- `rate_limit_requests`: allowed API requests per client per fixed window.
- `rate_limit_window_seconds`: fixed-window duration in seconds.

`SPARKLE_API_AUTH_REQUIRED` accepts `true/false`, `1/0`, `yes/no`, or `on/off`.
Invalid values stop startup. Wildcard, credential-bearing, path-bearing, query,
and fragment origins are rejected.

Any non-loopback bind requires authentication to be enabled and an accepted
token reference to be present. If authentication is required but the token is
missing, `sparkle serve` fails closed even on loopback. `sparkle status` reports
only whether the token is configured.

Rate-limit values outside their documented bounds stop configuration loading.
Client identifiers exist only in bounded process memory and are never written
to the audit store.

The `development` section keeps workspace test execution disabled by default.
Enable it only in a dedicated POSIX worker whose parent environment contains
only SPARKLE's narrow runtime/configuration allowlist. SPARKLE refuses execution otherwise. This process-level
runner does not provide filesystem or network isolation.
