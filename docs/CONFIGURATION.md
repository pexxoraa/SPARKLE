# Configuration

In a source checkout, application behavior is configured in
`application/config.json` and model/provider records in
`ai_environment/configurations/models.json`. A wheel installation materializes
the same bundled defaults beneath `SPARKLE_DATA_DIR/application/` and
`SPARKLE_DATA_DIR/ai_environment/configurations/` on first use, with mode 0600;
the model registry therefore remains writable outside installed package code.
Without an explicit data root, source checkouts use `var/`; installed POSIX
packages use `$XDG_STATE_HOME/sparkle` or the user's `.local/state/sparkle`.

Environment overrides:

| Variable | Purpose | Secret |
|---|---|---|
| `MINIMAX_API_KEY` | Preferred MiniMax credential reference | Yes |
| `SPARKLE_LLM_API_KEY` | Existing deployment alias | Yes |
| `SPARKLE_DATA_DIR` | Runtime database root | No |
| `SPARKLE_APPLICATION_CONFIG` | Explicit application configuration file | No |
| `SPARKLE_MODEL_CONFIG` | Explicit writable model-registry file | No |
| `SPARKLE_HOST` | HTTP bind host | No |
| `SPARKLE_PORT` | HTTP bind port | No |
| `SPARKLE_API_AUTH_REQUIRED` | Override API bearer-auth policy | No |
| `SPARKLE_API_TOKEN` | Default API bearer-token reference | Yes |
| `SPARKLE_API_RATE_LIMIT_REQUESTS` | Requests allowed per client/window (1–10000) | No |
| `SPARKLE_API_RATE_LIMIT_WINDOW_SECONDS` | Fixed-window duration (1–3600 seconds) | No |
| `SPARKLE_SESSION_AUTH_ENABLED` | Enable browser-session exchange when API auth is required | No |
| `SPARKLE_SESSION_COOKIE_SECURE` | Add `Secure` and permit non-loopback session binding | No |
| `SPARKLE_SESSION_TTL_SECONDS` | Absolute session lifetime (60–86400 seconds) | No |
| `SPARKLE_SESSION_MAX_ACTIVE` | Bounded in-memory session capacity (1–1000) | No |
| `SPARKLE_WORKSPACE_TESTS_ENABLED` | Opt in to fixed Python workspace tests | No |
| `SPARKLE_WORKSPACE_TEST_TIMEOUT_SECONDS` | Test wall/CPU limit (1–60 seconds) | No |
| `SPARKLE_EXTERNAL_WORKER_ENABLED` | Opt in to external workspace transfer/execution | No |
| `SPARKLE_EXTERNAL_WORKER_URL` | Signed worker HTTPS job endpoint | No |
| `SPARKLE_WORKER_SIGNING_KEY` | Default request/response HMAC key reference | Yes |
| `SPARKLE_EXTERNAL_WORKER_REQUEST_TIMEOUT_SECONDS` | HTTP request timeout (1–120 seconds) | No |
| `SPARKLE_EXTERNAL_WORKER_JOB_TIMEOUT_SECONDS` | Requested fixed-test timeout (1–60 seconds) | No |
| `SPARKLE_EXTERNAL_WORKER_MAX_PAYLOAD_BYTES` | Serialized request bound (1–20 MB) | No |
| `SPARKLE_AUTOMATION_INTERVAL_SECONDS` | Supervised service poll interval (1–3600 seconds) | No |
| `SPARKLE_AUTOMATION_LEASE_SECONDS` | Claim recovery/fencing lease (30–86400 seconds) | No |

Configuration files may contain secret *names* such as `MINIMAX_API_KEY`; they
must never contain secret values. Shell and web tools default to disabled.

Model records may declare `"modalities": ["text"]`; accepted values are
`text`, `image`, `audio`, and `document`. The list must be non-empty and unique.
It describes intended configuration, while the instantiated adapter's
`supported_modalities` remains the execution-time authority. The bundled
MiniMax-M3 record is text-only.

`application/config.json` contains the `security` policy:

- `api_auth_required`: requires bearer authentication for every `/api/` route.
- `api_token_refs`: ordered environment secret reference names; never values.
- `allowed_origins`: exact HTTP(S) origins allowed in addition to same-origin.
- `rate_limit_requests`: allowed API requests per client per fixed window.
- `rate_limit_window_seconds`: fixed-window duration in seconds.
- `session_auth_enabled`: allows the dashboard to exchange the configured API
  credential for a process-local session when API authentication is required.
- `session_cookie_secure`: adds the cookie `Secure` attribute and is mandatory
  for session-enabled non-loopback binds.
- `session_ttl_seconds`: absolute session expiry; sessions are not persisted.
- `session_max_active`: maximum active sessions before oldest-session eviction.

`SPARKLE_API_AUTH_REQUIRED` accepts `true/false`, `1/0`, `yes/no`, or `on/off`.
Invalid values stop startup. Wildcard, credential-bearing, path-bearing, query,
and fragment origins are rejected.

Any non-loopback bind requires authentication to be enabled and an accepted
token reference to be present. If authentication is required but the token is
missing, `sparkle serve` fails closed even on loopback. `sparkle status` reports
only whether the token is configured.

With session authentication enabled, non-loopback binding also requires
`SPARKLE_SESSION_COOKIE_SECURE=true`. Place a trusted TLS reverse proxy in front
of SPARKLE; the standard-library server does not terminate TLS. Set
`SPARKLE_SESSION_AUTH_ENABLED=false` only for bearer-only API deployments that
do not serve the browser dashboard.

Rate-limit values outside their documented bounds stop configuration loading.
Client identifiers exist only in bounded process memory and are never written
to the audit store.

The `development` section keeps workspace test execution disabled by default.
Enable it only in a dedicated POSIX worker whose parent environment contains
only SPARKLE's narrow runtime/configuration allowlist. SPARKLE refuses execution otherwise. This process-level
runner does not provide filesystem or network isolation.

The separate external worker is also disabled by default. Enabling it requires
an HTTPS URL, a pinned `external_worker_id`, and a signing key of at least 32 bytes supplied through one of the
configured `external_worker_secret_refs`. The URL may not contain credentials,
a query, or a fragment. Status reports only configuration booleans—not the URL,
secret-reference names, or secret value.

The client sends one fixed `python_unittest` operation and does not retry. It
caps the workspace at 500 UTF-8 regular files, 500 KB per file, 5 MB total, and
the configured serialized payload limit. Symlinks, hidden paths,
credential/secret-like paths, credential-file suffixes, and source containing
the configured signing-key value are rejected before transfer. Each invocation
still requires explicit operator approval. Deploying and validating a
compatible hardened worker is separate work; setting these values alone does
not make filesystem or network isolation verified.

Application-side worker settings are `SPARKLE_EXTERNAL_WORKER_URL` for the
credential-free HTTPS `/v1/jobs` endpoint, `SPARKLE_EXTERNAL_WORKER_ID` for the
exact expected public worker identity, and the configured secret-reference
name (by default `SPARKLE_WORKER_SIGNING_KEY`) for HMAC injection. A controlled
execution is not configured unless all three are present. The key value must be
injected by the process secret manager and never placed in JSON configuration.

The separate `sparkle-worker` process uses its own environment:

| Variable | Purpose | Secret |
|---|---|---|
| `SPARKLE_WORKER_HOST` / `SPARKLE_WORKER_PORT` | Worker bind address | No |
| `SPARKLE_WORKER_ID` | Bounded public worker identifier | No |
| `SPARKLE_WORKER_STATE_DIR` | Independent replay database root | No |
| `SPARKLE_WORKER_SIGNING_KEY_FILE` | Mode-0600/0400 key file | Reference path |
| `SPARKLE_WORKER_SIGNING_KEY` | Environment fallback for local secret managers | Yes |
| `SPARKLE_WORKER_EXECUTOR` | `bubblewrap` (default) or explicit unsafe `process` | No |
| `SPARKLE_WORKER_BWRAP` / `SPARKLE_WORKER_PYTHON` | Fixed executable paths | No |
| `SPARKLE_WORKER_ALLOW_UNSAFE_PROCESS_EXECUTOR` | Required opt-in for development process mode | No |
| `SPARKLE_WORKER_MAX_BODY_BYTES` | Request body bound (1–20 MB) | No |
| `SPARKLE_WORKER_MAX_CONCURRENCY` | Concurrent jobs (1–32) | No |
| `SPARKLE_WORKER_REPLAY_TTL_SECONDS` | Replay retention (300–604800 seconds) | No |
| `SPARKLE_WORKER_MAX_REPLAY_ENTRIES` | Replay capacity (100–1000000) | No |
| `SPARKLE_WORKER_TLS_CERT_FILE` / `SPARKLE_WORKER_TLS_KEY_FILE` | Optional direct TLS pair | Key file is secret |
| `SPARKLE_WORKER_TRUSTED_TLS_TERMINATION` | Permit non-loopback HTTP only behind the supplied trusted edge | No |

Non-loopback startup requires direct TLS or explicit trusted termination. The
key file is opened without symlink following and must deny group/other access.
Health/status reports only presence and control state. See `WORKER.md`.

The separately installed `sparkle-automations` process reads its two bounds
from the variables above or equivalent CLI flags. The lease should exceed the
longest expected bounded model/retry cycle. Its lock and status remain beneath
`SPARKLE_DATA_DIR/data_environment`; no secret value is written there. See
`AUTOMATION.md` and `automation_environment/README.md`.
