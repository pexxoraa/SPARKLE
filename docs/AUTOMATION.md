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

The proactive engine implements protocol `SPARKLE-PROACTIVE/1`. It evaluates
only explicit structured metadata on active memory records and emits at most
200 deterministically ordered alerts. It never infers conditions from the
memory value or sends that value in alert evidence.

| Alert | Eligible categories | Required metadata |
|---|---|---|
| `deadline_approaching`, `overdue` | tasks, exams, projects, goals | ISO-8601 `deadline` or `due_at` |
| `weak_learning` | skills, learning, exams | positive integer `evidence_count` and either `mastery_level` below `target_level`, or `accuracy` below `target_accuracy` with positive integer `attempts` |
| `revision_due` | skills, learning, exams | ISO-8601 `next_review_at` at or before evaluation time |
| `project_incomplete` | projects | `status` in active, blocked, in_progress, or paused, plus `progress_percent` below 100 |
| `repeated_mistake` | mistakes | integer `repeat_count` of at least 2 |

Numbers, timestamps, categories, keys, evidence counts, and condition fields
are bounded and type checked. Invalid or incomplete evidence produces no
alert. GET `/api/proactive` returns the protocol version and safe structured
alerts; the dashboard renders their type, severity, category, key, and source
memory ID.

Conditional automations accept the backwards-compatible `memory_deadline`
type for deadline alerts or `proactive_alert` for any supported alert. They can
filter by `alert`, `category`, and `key`; `cooldown_minutes` must be between 1
and 10,080. Unknown condition fields and unsupported alert/category values are
rejected before persistence. Cooldowns prevent repeated execution.

Example condition:

```json
{
  "type": "proactive_alert",
  "alert": "weak_learning",
  "category": "skills",
  "key": "python",
  "cooldown_minutes": 1440
}
```

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
