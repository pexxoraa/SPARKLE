# Supervised automation deployment

The unit in this directory runs the existing SPARKLE automation engine as one
long-lived, non-root process. It does not introduce a second scheduler or a
general command runner.

Install SPARKLE under `/opt/sparkle`, create the `sparkle` system account, and
give that account exclusive access to `/var/lib/sparkle`. Copy
`sparkle-automations.service` to the systemd unit directory. If a live provider
is used, provision `/etc/sparkle/automation.conf` through the host secret
manager with owner-only permissions; it may contain secret environment
references such as `MINIMAX_API_KEY`, never committed values.

```bash
sudo systemctl daemon-reload
sudo systemctl enable --now sparkle-automations
sudo -u sparkle SPARKLE_DATA_DIR=/var/lib/sparkle \
  /opt/sparkle/.venv/bin/sparkle-automations --status
```

`--check` verifies database/lock readiness before startup. `--healthcheck`
requires a fresh healthy persisted heartbeat. The service holds a no-follow,
mode-0600 POSIX lock for its lifetime, so a second local instance fails closed.
SIGTERM sets the in-process drain event and stops after the current bounded
model operation; normal control flow then persists stopped state. If systemd
must terminate a wedged operation after
`TimeoutStopSec`, its claim remains fenced and becomes recoverable when the
configured lease expires.

The service provides at-least-once recovery, not exactly-once delivery. An
external effect performed before a crash may repeat after lease recovery;
automation actions therefore remain limited to SPARKLE agent requests and
must use idempotent external tools when such tools are added later.
