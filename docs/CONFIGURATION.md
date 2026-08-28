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

Configuration files may contain secret *names* such as `MINIMAX_API_KEY`; they
must never contain secret values. Shell and web tools default to disabled.
