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

## Dashboard

```bash
sparkle serve
```

The dashboard displays model/configuration state, agents, memory, and traces.

## Data ownership

Runtime data is local under `var/` by default. Set `SPARKLE_DATA_DIR` before
startup to use another location. Remove or back up these SQLite files according
to your own retention policy.
