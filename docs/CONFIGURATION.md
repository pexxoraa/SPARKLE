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

Configuration files may contain secret *names* such as `MINIMAX_API_KEY`; they
must never contain secret values. Shell and web tools default to disabled.

`application/config.json` contains the `security` policy:

- `api_auth_required`: requires bearer authentication for every `/api/` route.
- `api_token_refs`: ordered environment secret reference names; never values.
- `allowed_origins`: exact HTTP(S) origins allowed in addition to same-origin.

`SPARKLE_API_AUTH_REQUIRED` accepts `true/false`, `1/0`, `yes/no`, or `on/off`.
Invalid values stop startup. Wildcard, credential-bearing, path-bearing, query,
and fragment origins are rejected.

Any non-loopback bind requires authentication to be enabled and an accepted
token reference to be present. If authentication is required but the token is
missing, `sparkle serve` fails closed even on loopback. `sparkle status` reports
only whether the token is configured.
