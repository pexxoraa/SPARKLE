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

## Execute automations

Run all currently due internal agent actions once:

```bash
sparkle automations-run
```

Run a foreground polling worker:

```bash
sparkle automations-run --watch --interval 60
```

The dashboard and `/api/automation-runs` show execution status, attempts,
trace IDs, and safe result summaries.

## Dashboard

```bash
sparkle serve
```

The dashboard displays model/configuration state, built-in and generated
agents, memory, automation runs, application builds, static verifications, and
bounded test runs and traces. The API audit panel shows only route outcomes and durations; it never
shows client identities, request content, queries, origins, headers, or tokens.

## Secure API access

Local loopback use remains unauthenticated by default. For a non-loopback bind,
set `SPARKLE_API_AUTH_REQUIRED=true` and provide `SPARKLE_API_TOKEN` through the
hosting or OS secret manager before starting the server. API clients then send
that value in the standard `Authorization: Bearer …` header.

All `/api/` routes, including health, require the token in this mode. Cross-
origin browser clients must also use an exact origin listed in
`security.allowed_origins`; no wildcard is accepted. The built-in dashboard
does not accept or persist bearer tokens, so use it with the default local
configuration.

All API requests are subject to the configured fixed-window quota. Successful
and rejected responses include `X-RateLimit-Limit` and
`X-RateLimit-Remaining`; HTTP 429 also includes `Retry-After`. Inspect recent
secret-free outcomes at `GET /api/audit`.

## Data ownership

Runtime data is local under `var/` by default. Set `SPARKLE_DATA_DIR` before
startup to use another location. Remove or back up these SQLite files according
to your own retention policy.
