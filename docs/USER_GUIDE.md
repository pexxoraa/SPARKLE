# User guide

## Inspect the system

```bash
sparkle status
```

This shows whether a provider key exists without exposing it.

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
agents, memory, automation runs, application builds, and traces.

## Data ownership

Runtime data is local under `var/` by default. Set `SPARKLE_DATA_DIR` before
startup to use another location. Remove or back up these SQLite files according
to your own retention policy.
