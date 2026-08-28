# Secrets environment

SPARKLE resolves provider credentials from the process environment through
`SecretResolver`. It never stores secret values in source, SQLite, traces, the
dashboard, or errors.

MiniMax lookup order:

1. `MINIMAX_API_KEY`
2. `SPARKLE_LLM_API_KEY` (supported for existing deployments)

Use the hosting platform's server-side secret manager. Do not prefix these
variables with a browser-exposed frontend prefix.
