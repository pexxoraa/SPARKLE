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

Existing text messages remain unchanged. Provider-neutral image, audio, and
document input is available through `POST /api/chat` with a
`SPARKLE-CONTENT/1` object in the `content` field. For example, a small
document request can omit `content_id`; SPARKLE derives it after validation:

```json
{
  "agent": "research",
  "content": {
    "protocol_version": "SPARKLE-CONTENT/1",
    "parts": [
      {
        "type": "text",
        "media_type": "text/plain",
        "encoding": "utf-8",
        "data": "Review these notes",
        "metadata": {}
      },
      {
        "type": "document",
        "media_type": "text/plain",
        "encoding": "base64",
        "data": "bm90ZXM=",
        "metadata": {"filename": "notes.txt"}
      }
    ]
  }
}
```

Inspect exact types and bounds at `GET /api/content-contract`. The current
MiniMax-M3 adapter is text-only and rejects non-text content before a provider
call. A compatible future adapter can process the same envelope without core
changes. The deterministic test adapter proves the complete transport path; it
does not prove semantic non-text understanding. See `MULTIMODAL.md`.

## Store useful context

```bash
sparkle remember goals robotics "Build a safe 5-DOF robot-arm prototype"
sparkle ingest notes/robotics.md
sparkle ingest paper.pdf --title "Robot manipulation paper"
sparkle ingest papers/robotics.md --monitor-key robotics.papers
```

Memory records can be archived and restored. Permanent memory, knowledge-source,
and automation deletion is available through the local API and requires
`"approved": true`. The storage classes also expose consistent SQLite backup
operations for an operator-controlled destination.

Re-ingesting a changed file with the same `--monitor-key` creates a bounded
`research_change` alert. API clients can supply equivalent knowledge metadata:
`{"research_monitor":true,"monitor_key":"robotics.papers"}`. SPARKLE does
not poll the source by itself; an operator or future connector must submit each
new observation.

## Plan an AI system implementation

Exact structured AI system requirements can be prepared as a Blueprint or
converted from natural language as described in `AI_BUILDER.md`. After review,
derive a deterministic implementation plan without calling a model or writing
source:

```bash
sparkle ai-system-plan requirements.json
```

To add only the canonical reviewable plan manifest to the bounded application
workspace:

```bash
sparkle ai-system-plan-build requirements.json --approve
```

The output proposes source and evaluation paths and orders the work, but
`human_review_completed`, `source_generation_executed`,
`runtime_evaluation_executed`, and `external_deployment_executed` remain false.
Materializing a plan is not approval for any later source generation.

## Install a generated agent

The recommended path starts from structured requirements and performs a
non-mutating static preparation before installation. Create
`agent-requirements.json`:

```json
{
  "name": "robotics_research",
  "capability": "reasoning",
  "purpose": "Research robotics systems with explicit evidence standards.",
  "tools": ["calculator", "knowledge_search", "memory_search"],
  "keywords": ["robotics research", "robot paper"],
  "workflow": ["Collect evidence.", "Cross-check sources.", "Label uncertainty."],
  "guardrails": ["Never fabricate sources or completed tests."],
  "evaluations": [
    {
      "name": "robot_paper",
      "prompt": "Start robotics research for a robot paper.",
      "assertions": {
        "contains_all": ["robot paper"],
        "excludes_all": ["fabricated source"],
        "max_chars": 4000
      }
    }
  ]
}
```

Prepare, inspect, and explicitly approve installation:

```bash
sparkle agent-prepare agent-requirements.json
sparkle agent-build agent-requirements.json --approve
sparkle agent-evaluate robotics_research --approve
sparkle chat --agent robotics_research "Compare two robot-arm control methods"
```

Preparation never installs the agent. It validates that each fixture routes to
the candidate but does not call a model. The separate approved evaluation
command calls the configured model using no personal context and no tools, then
persists only response hashes/lengths and check results. It evaluates bounded
lexical/length contracts, not semantic correctness, source generation, or
external deployment.

The lower-level reviewed-manifest path remains available. Create `agent.json`:

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

## Track structured projects

Create a project manifest using the exact contract in
[`PROJECTS.md`](PROJECTS.md):

```bash
sparkle project-create project.json
sparkle projects
sparkle project-update sparkle_core changes.json --expected-version 1
```

Updates require the current version so concurrent or stale changes fail rather
than overwrite. Archive is explicit and approval-gated:

```bash
sparkle project-archive sparkle_core --expected-version 2 --approve
sparkle projects --include-archived
```

The dashboard shows active projects. Personal, Project, and Productivity
agents can read them through `project_search`; model-facing writes are not
available. The authenticated API provides equivalent create/update/archive,
list/search, and content-free change-evidence routes.

## Track evidence-based skill mastery

Create a skill and add explicit evidence using the exact contract in
[`SKILLS.md`](SKILLS.md):

```bash
sparkle skill-create skill.json
sparkle skill-evidence evidence.json
sparkle skills --query Python
```

The current level is derived from verified evidence and cannot be directly
edited. Metadata updates use optimistic versions, and archive requires
approval:

```bash
sparkle skill-update python changes.json --expected-version 2
sparkle skill-archive python --expected-version 3 --approve
```

Personal, Learning, and Skill agents can read bounded summaries through
`skill_search`; evidence summaries, artifact references, verification, and all
writes remain outside model tools. The dashboard shows active skill levels and
counts. The authenticated API exposes equivalent skill/evidence routes.

## Prepare an AI system scaffold

To convert natural-language requirements into a reviewable structured draft,
put the text in a UTF-8 file and explicitly approve the provider call:

```bash
sparkle ai-system-draft requirements.txt --approve
```

This operation uses no memory, knowledge context, history, user identity, or
tools. Review the returned requirements and Blueprint carefully: schema success
does not prove semantic fidelity. Draft evidence is available from
`GET /api/ai-system-drafts`, without storing the input or generated JSON.

Create a structured requirements file using the schema in
[`AI_BUILDER.md`](AI_BUILDER.md), then validate it without mutation:

```bash
sparkle ai-system-prepare requirements.json
```

After reviewing the resolved model routes, agents, tools, environment
boundaries, interfaces, evaluations, and deployment plan, explicitly approve
materialization:

```bash
sparkle ai-system-build requirements.json --approve
```

The build creates a bounded application workspace containing `README.md` and
the canonical `SPARKLE_AI_SYSTEM.json`. It does not call a model, run the
declared evaluations, or deploy the system. History is available from
`GET /api/ai-system-blueprints`; authenticated API clients can use
`POST /api/ai-systems/prepare` and `POST /api/ai-systems/build`.

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

Automations may use a provider-neutral dashboard notification instead of an
agent call:

```json
{
  "type": "notification",
  "channel": "dashboard",
  "title": "Revision due",
  "body": "Review control systems today.",
  "severity": "warning",
  "dedupe_key": "revision.control_systems"
}
```

Manual notification delivery uses `POST /api/notifications`; list or mark read
through `/api/notifications` and `/api/notifications/read`. See
`NOTIFICATIONS.md` for bounds and the external-channel gap.

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

Supported alerts are `deadline_approaching`, `overdue`, `schedule_conflict`,
`research_change`, `weak_learning`, `revision_due`, `project_incomplete`, and
`repeated_mistake`.
Schedule records use bounded ISO-8601 `starts_at` and `ends_at` metadata. The full evidence
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
System metrics expose multimodal contract types and bounds, but the dashboard
command field remains a text client in this release.

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
