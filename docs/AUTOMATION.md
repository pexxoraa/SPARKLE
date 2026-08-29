# Automation and proactive intelligence

The automation store supports once, daily, weekly, and conditional records with
agent actions, schedule metadata, next-run time, enabled state, and last-run
state. The runner atomically claims due work, invokes a single agent or a
multi-agent workflow, retries up to three times, records every run, and
reschedules daily and weekly work. Once-only work is disabled after execution.

The proactive engine currently detects overdue and approaching deadlines from
task, exam, project, and goal memory metadata. A `memory_deadline` condition can
filter by alert type, category, and key; its cooldown prevents repeat execution.
It does not invent alerts when no deadline data exists.

Run one worker cycle with:

```bash
sparkle automations-run
```

For a foreground polling worker:

```bash
sparkle automations-run --watch --interval 60
```

The API can create, run, enable/disable, and delete automations and list run
history. Automation-triggered model activity is traced with input source
`automation`.

A service manager, notification delivery, calendar connector, and external
event webhooks are not yet packaged. The foreground watcher is an execution
worker, not a production daemon.
