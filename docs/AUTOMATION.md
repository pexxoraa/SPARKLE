# Automation and proactive intelligence

The automation store supports once, daily, weekly, and conditional records with
agent actions, schedule metadata, next-run time, enabled state, and last-run
state. The runner atomically claims due work, invokes a single agent or a
multi-agent workflow, retries up to three times, records every run, and
reschedules daily and weekly work. Once-only work is disabled after execution.

Every claim now carries a random fencing token and expiration. A crashed
service cannot leave work permanently disabled: the supervised service recovers
expired claims at startup and before each cycle, records a `recovered` run with
`AutomationLeaseExpired`, and makes the work eligible again. A claimant whose
token was recovered or cancelled cannot commit a result. This is at-least-once
recovery, not exactly-once delivery; actions with future external effects must
be idempotent.

The proactive engine currently detects overdue and approaching deadlines from
task, exam, project, and goal memory metadata. A `memory_deadline` condition can
filter by alert type, category, and key; its cooldown prevents repeat execution.
It does not invent alerts when no deadline data exists.

Run one worker cycle with:

```bash
sparkle automations-run
```

For the supervised foreground service:

```bash
sparkle-automations --check
sparkle-automations --interval 60 --lease-seconds 3600
```

`sparkle automations-run --watch` uses the same service lifecycle for backward
compatibility. `sparkle-automations --once` executes one supervised cycle;
`--status` reads persisted lifecycle state; `--healthcheck` succeeds only for a
fresh running heartbeat.

The API can create, run, enable/disable, and delete automations and list run
history. Automation-triggered model activity is traced with input source
`automation`.

The service holds a no-follow, mode-0600 POSIX lock, refuses a second local
instance, persists running/degraded/draining/stopped/stale state, and handles
SIGINT/SIGTERM without claiming new work. A hardened non-root systemd profile
is provided in `automation_environment/`; its bounded forced-stop policy leaves
an interrupted claim fenced until lease recovery. Signal handlers perform no
database I/O: they set the drain event, prevent another cycle, and normal
service control flow persists the terminal state.

Notification delivery, calendar connectors, and external event webhooks are
not implemented. Live scheduled model work also requires a configured provider
credential; deterministic service execution is covered by the test suite.
