# Browser and computer interaction lifecycle

SPARKLE keeps browser and GUI execution behind provider-neutral adapters and does not register raw interaction as a model tool. The software-side lifecycle now includes persistent operator-owned sessions, explicit permissions, revision-bound actions, expiry, close semantics and bounded action evidence.

## Browser sessions

A browser session declares 1-32 allowlisted HTTPS hosts and a TTL from 30 seconds to 24 hours. Every navigation reuses the existing `BrowserRequest` safety contract: credential-free HTTPS on port 443, bounded timeout and bounded extracted text. Adapter results are revalidated so redirects cannot escape the allowlist. Each successful navigation appends a content-bounded event record and advances the session revision.

## Computer sessions

A computer session declares its permitted action kinds from screenshot, click, type_text and key. Each action remains subject to the existing typed coordinate/text/key bounds. Actions outside the session permission set fail closed. Successful adapter evidence is persisted with the action and advances the session revision.

## Lifecycle and concurrency

Sessions are active, closed or expired. Every execution and close operation requires the exact current revision. Stale requests fail closed. Expired or closed sessions cannot execute. Active sessions and per-session event histories are bounded. Session state is stored under `SPARKLE_DATA_DIR/data_environment/interaction_sessions.sqlite3` and is reported through the existing system interaction status.

The `sparkle-interaction` CLI exposes start, inspect, history, browse, action and close operations. Execution still depends on a configured BrowserAdapter or ComputerAdapter. The default adapters remain disabled, so installing this lifecycle does not falsely imply browser or desktop access.

## External acceptance boundary

The repository now contains the software-side session, permission, validation, persistence and evidence architecture. Real browser engines, GUI hosts, screenshots, operating-system permission prompts and action correctness remain externally dependent acceptance work. These dependencies do not weaken the fail-closed default or become evidence of real-world verification merely because an injected test adapter succeeds.
