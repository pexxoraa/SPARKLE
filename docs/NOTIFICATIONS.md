# Notifications

SPARKLE notifications use provider-neutral protocol
`SPARKLE-NOTIFICATION/1`. The first real delivery adapter is `dashboard`: a
notification is persisted in `data_environment/notifications.sqlite3`, exposed
through the authenticated JSON API, and rendered in the dashboard Automation
panel. No model or provider is required.

Each notification has an explicit channel, title, body, severity, source,
status, creation/read time, and optional deduplication key. Supported
severities are `info`, `warning`, and `critical`. Titles are limited to 200
characters, bodies to 2,000, dedupe keys to 128 safe characters, API lists to
100 entries, and the store to the latest 1,000 records. Reusing a channel/key
updates the existing record and returns it to unread `delivered` state.

Manual delivery:

```json
POST /api/notifications
{
  "channel": "dashboard",
  "title": "Robot report deadline",
  "body": "Review the controls section today.",
  "severity": "warning",
  "dedupe_key": "deadline.robot_report"
}
```

List with `GET /api/notifications?unread=true`; mark one read with
`POST /api/notifications/read` and `{"notification_id": 1}`.

Automations can use the same strict action shape with
`"type": "notification"`. The runner records a linked execution trace with
the channel, severity, opaque notification ID, transformation, and storage
destination. It deliberately does not copy the title or body into the trace or
automation result summary.

The notification database contains user-visible message content by design and
therefore remains separate from secrets, memory, knowledge, and traces. The
current release does not implement email, SMS, mobile push, calendar, or
webhook delivery. Those future channels must implement the same bounded
contract, credential-reference boundary, idempotency behavior, and trace
non-disclosure rules.
