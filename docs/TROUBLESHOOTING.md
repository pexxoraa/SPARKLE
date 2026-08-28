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

## PDF/DOCX ingestion unavailable

Install `python3 -m pip install -e '.[documents]'`.
