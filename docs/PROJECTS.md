# Structured projects

SPARKLE v0.22 implements the provider-neutral `SPARKLE-PROJECT/1` contract.
Project state is stored separately in `data_environment/projects.sqlite3` and
does not depend on MiniMax, an agent prompt, memory prose, or a third-party
project-management service.

## Project contract

Create requires the exact structured fields:

```json
{
  "name": "sparkle_core",
  "title": "SPARKLE core platform",
  "description": "Build and verify the provider-neutral personal AI platform.",
  "status": "implementation",
  "priority": "critical",
  "deadline": "2026-09-30T12:30:00Z",
  "dependencies": [],
  "risks": ["External provider verification is unavailable."],
  "milestones": [
    {
      "name": "Structured project tracking",
      "status": "in_progress",
      "due_at": "2026-09-05T12:00:00Z"
    }
  ],
  "blockers": [],
  "next_action": "Complete structured project-state integration.",
  "progress": 90
}
```

Statuses follow the requested lifecycle from `idea`, `requirements`, `design`,
and `architecture` through tasks, implementation, testing, documentation,
deployment, review, blocked, and complete. Priority, identifiers, list sizes,
text lengths, timestamps, milestones, completion claims, and dependencies are
strictly validated. Complete projects require 100% progress, no blockers, and
no open milestones. Blocked projects require explicit blocker evidence.

Updates use an `expected_version` integer. A stale writer fails with a version
conflict instead of silently overwriting newer state. Archival also requires
the expected version plus explicit operator approval at the API or CLI
boundary. Archived projects are immutable and excluded from normal lists.

## Interfaces

```bash
sparkle project-create project.json
sparkle project-update sparkle_core changes.json --expected-version 1
sparkle projects
sparkle projects --query SPARKLE
sparkle project-archive sparkle_core --expected-version 2 --approve
```

Authenticated API routes are:

- `GET /api/projects`
- `GET /api/project-events?name=sparkle_core`
- `POST /api/projects`
- `POST /api/projects/update`
- `POST /api/projects/archive`

The dashboard exposes a read-only active portfolio. Personal, Project, and
Productivity agents can call the read-only `project_search` tool. Other agents
do not receive that tool, and no model-facing tool can create, update, or
archive a project.

## Evidence and bounds

At most 1,000 active projects are accepted. Lists return at most 100 records
and model-facing searches at most 20. Project changes create append-only,
latest-10,000 evidence records containing only the project identifier, action,
version, changed field names, status, priority, progress, and timestamp. They
do not duplicate descriptions, risks, blockers, milestone names, or next-action
text.

Structured active projects feed the existing proactive engine directly.
Incomplete and deadline evidence contains only bounded status/count/progress
metadata; raw project text is not copied into proactive alerts.

This increment does not claim semantic project decisions, third-party project
connectors, calendar synchronization, or live-model response quality.
