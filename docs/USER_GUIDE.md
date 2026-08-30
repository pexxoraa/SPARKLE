# User guide

## Inspect the system

```bash
sparkle status
```

This shows whether a provider key exists without exposing it.

It also reports whether API authentication is required and whether its token
reference is configured, never the token value.

## Chat

```bash
sparkle chat "Teach me inverse kinematics"
sparkle chat --agent research "Compare robot-arm control approaches"
sparkle chat --multi "Research robot arms and design a dashboard"
```

## Store useful context

```bash
sparkle remember goals robotics "Build a safe 5-DOF robot-arm prototype"
sparkle ingest notes/robotics.md
sparkle ingest paper.pdf --title "Robot manipulation paper"
```

Memory records can be archived and restored. Permanent memory, knowledge-source,
and automation deletion is available through the local API and requires
`"approved": true`. The storage classes also expose consistent SQLite backup
operations for an operator-controlled destination.

## Install a generated agent

Create `agent.json`:

```json
{
  "name": "robotics_research",
  "capability": "reasoning",
  "purpose": "Research robotics systems with explicit evidence standards.",
  "instructions": "Compare sources, cite evidence, and label uncertainty in every synthesis.",
  "tools": ["calculator", "knowledge_search", "memory_search"],
  "keywords": ["robotics research", "robot paper"]
}
```

Then explicitly approve installation:

```bash
sparkle agent-install agent.json --approve
sparkle chat --agent robotics_research "Compare two robot-arm control methods"
```

Use `--replace` to update a generated agent. Remove it with
`sparkle agent-remove robotics_research --approve`. Built-in agents cannot be
replaced or removed.

## Scaffold an application workspace

Create `app.json`:

```json
{
  "project_name": "robot_dashboard",
  "files": {
    "README.md": "# Robot Dashboard\n",
    "src/main.py": "print('SPARKLE workspace')\n"
  }
}
```

Create the bounded workspace with:

```bash
sparkle scaffold app.json --approve
```

Existing files are protected unless `--overwrite` is also supplied. Scaffolding
does not run the generated code or any shell command.

## Verify a generated workspace

Create `verification.json`:

```json
{
  "project_name": "robot_dashboard",
  "checks": [
    {"type": "python_compile", "path": "src/main.py"},
    {"type": "javascript_syntax", "path": "assets/app.js"},
    {"type": "json_parse", "path": "config/settings.json"}
  ]
}
```

Run the bounded checks with:

```bash
sparkle verify-workspace verification.json --approve
```

The command exits 0 only when every check passes. It records results and
durations even when syntax is invalid. It does not execute Python or JavaScript
application code, run tests, install packages, or invoke a shell. The equivalent
API endpoint is `POST /api/builds/verify`; history is available from
`GET /api/verifications`.

## Run fixed workspace tests

Workspace tests are disabled by default. In a disposable POSIX worker with a
strictly sanitized, allowlisted environment:

```bash
export SPARKLE_WORKSPACE_TESTS_ENABLED=true
sparkle test-workspace robot_dashboard --approve
```

SPARKLE runs only standard-library unittest discovery beneath `tests/`. It does
not accept custom commands, arguments, dependencies, or environment values.
Results are available from `GET /api/test-runs`; the equivalent execution route
is `POST /api/builds/test` with `project_name` and `approved: true`.

This is process-bounded execution, not filesystem or network isolation. Never
enable it in the MiniMax/API server process or any process carrying credentials.
Use a disposable worker and do not run hostile or untrusted code.

## Submit fixed tests to an external worker

This boundary is disabled until an operator configures a compatible HTTPS
worker and a secret-managed HMAC key. It sends the accepted UTF-8 source files,
so review the workspace before approving the transfer.

```bash
export SPARKLE_EXTERNAL_WORKER_ENABLED=true
export SPARKLE_EXTERNAL_WORKER_URL='https://worker.example/v1/jobs'
export SPARKLE_WORKER_SIGNING_KEY='configured-outside-source'
sparkle test-workspace-external robot_dashboard --approve
```

The equivalent authenticated API route is `POST /api/builds/test-external`
with `project_name` and `approved: true`; history is available from
`GET /api/external-test-runs`. The dashboard history is intentionally read-only.
SPARKLE verifies response authenticity and protocol consistency. It stores
worker sandbox flags only as claims and reports `isolation_verified: false`
until a deployed worker is independently validated. No compatible live worker
has been deployed or verified by this release.

## Package a workspace

Create a deterministic, content-addressed ZIP without executing project code:

```bash
sparkle package-workspace robot_dashboard --approve
```

Artifacts and their SHA-256 manifests are listed by `GET /api/artifacts` and
the dashboard. A target action performed outside SPARKLE can be logged with:

```bash
sparkle record-deployment 1 staging server reported_success --approve
```

The record is append-only but explicitly unverified. It is not evidence that
SPARKLE executed, observed, or validated the deployment.

## Execute automations

Run all currently due internal agent actions once:

```bash
sparkle automations-run
```

Run the supervised service:

```bash
sparkle-automations --check
sparkle-automations --interval 60 --lease-seconds 3600
```

The dashboard and `/api/automation-runs` show execution status, attempts,
trace IDs, and safe result summaries.
`sparkle-automations --status` shows persisted service state and
`--healthcheck` requires a fresh running heartbeat. Expired work is recovered
with an explicit run record; because this is at-least-once processing, future
external actions must be idempotent.

Inspect current evidence-backed alerts at `GET /api/proactive` or in the
dashboard Automation panel. Alerts are computed from explicit metadata fields,
not from memory prose. To drive an automation from an alert, create a
conditional automation through `POST /api/automations` with a condition such
as:

```json
{
  "type": "proactive_alert",
  "alert": "revision_due",
  "category": "learning",
  "key": "control_systems",
  "cooldown_minutes": 1440
}
```

Supported alerts are `deadline_approaching`, `overdue`, `weak_learning`,
`revision_due`, `project_incomplete`, and `repeated_mistake`. The full evidence
schema is documented in `docs/AUTOMATION.md`.

## Dashboard

```bash
sparkle serve
```

The dashboard displays model/configuration state, built-in and generated
agents, memory, proactive alerts, automation runs, application builds, static verifications,
bounded local test runs, signed external-worker evidence, immutable artifacts,
unverified deployment events, and traces. The API
audit panel shows only route outcomes and durations; it never
shows client identities, request content, queries, origins, headers, or tokens.

## Secure API access

Local loopback use remains unauthenticated by default. For a non-loopback bind,
set `SPARKLE_API_AUTH_REQUIRED=true` and provide `SPARKLE_API_TOKEN` through the
hosting or OS secret manager before starting the server. For dashboard sessions
on a non-loopback bind, also set `SPARKLE_SESSION_COOKIE_SECURE=true` and place a
trusted TLS-terminating reverse proxy in front of SPARKLE. API clients continue
to send the token in the standard `Authorization: Bearer …` header.

All `/api/` routes, including health, require the token in this mode. Cross-
origin browser clients must also use an exact origin listed in
`security.allowed_origins`; no wildcard is accepted.

The same-origin dashboard presents an authentication gate. The supplied bearer
credential is exchanged once for an expiring, bounded, process-local session;
the page clears the field and uses no browser storage. HttpOnly same-site
cookies protect reads, an in-memory CSRF token protects mutations, reload can
recover that CSRF token through the authenticated session endpoint, and **End
session** revokes the server record. Server restarts intentionally invalidate
all sessions.

All API requests are subject to the configured fixed-window quota. Successful
and rejected responses include `X-RateLimit-Limit` and
`X-RateLimit-Remaining`; HTTP 429 also includes `Retry-After`. Inspect recent
secret-free outcomes at `GET /api/audit`.

## Data ownership

Runtime data is local under `var/` by default. Set `SPARKLE_DATA_DIR` before
startup to use another location. Remove or back up these SQLite files according
to your own retention policy.
