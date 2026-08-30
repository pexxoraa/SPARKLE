from __future__ import annotations

import re
import sqlite3
from pathlib import Path
from typing import Any

from sparkle.config import data_root
from sparkle.storage import SQLiteStore, utc_now


class NotificationStore(SQLiteStore):
    """Bounded provider-neutral notification outbox with a dashboard channel."""

    PROTOCOL = "SPARKLE-NOTIFICATION/1"
    CHANNELS = frozenset({"dashboard"})
    SEVERITIES = frozenset({"info", "warning", "critical"})
    SOURCES = frozenset({"manual", "automation", "system"})
    MAX_RECORDS = 1_000
    MAX_TITLE_CHARS = 200
    MAX_BODY_CHARS = 2_000
    _DEDUPE_KEY = re.compile(r"[A-Za-z0-9][A-Za-z0-9._:-]{0,127}\Z")

    def __init__(self, path: Path | None = None):
        super().__init__(
            path or data_root() / "data_environment" / "notifications.sqlite3"
        )
        self.initialize()

    def initialize(self) -> None:
        with self.connect() as connection:
            connection.executescript("""
                CREATE TABLE IF NOT EXISTS notifications (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    protocol_version TEXT NOT NULL,
                    channel TEXT NOT NULL,
                    title TEXT NOT NULL,
                    body TEXT NOT NULL,
                    severity TEXT NOT NULL,
                    dedupe_key TEXT,
                    source TEXT NOT NULL,
                    status TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    read_at TEXT,
                    UNIQUE(channel, dedupe_key)
                );
                CREATE INDEX IF NOT EXISTS idx_notifications_status
                    ON notifications(status, id DESC);
            """)

    @classmethod
    def validate(
        cls,
        *,
        channel: Any,
        title: Any,
        body: Any,
        severity: Any,
        dedupe_key: Any = None,
        source: Any,
    ) -> dict[str, str | None]:
        if channel not in cls.CHANNELS:
            raise ValueError("Notification channel is unsupported")
        if (
            not isinstance(title, str)
            or not title.strip()
            or len(title.strip()) > cls.MAX_TITLE_CHARS
        ):
            raise ValueError("Notification title must contain 1-200 characters")
        if (
            not isinstance(body, str)
            or not body.strip()
            or len(body.strip()) > cls.MAX_BODY_CHARS
        ):
            raise ValueError("Notification body must contain 1-2000 characters")
        if severity not in cls.SEVERITIES:
            raise ValueError("Notification severity is unsupported")
        if source not in cls.SOURCES:
            raise ValueError("Notification source is unsupported")
        if dedupe_key is not None and (
            not isinstance(dedupe_key, str)
            or cls._DEDUPE_KEY.fullmatch(dedupe_key) is None
        ):
            raise ValueError("Notification dedupe_key is invalid")
        return {
            "channel": channel,
            "title": title.strip(),
            "body": body.strip(),
            "severity": severity,
            "dedupe_key": dedupe_key,
            "source": source,
        }

    def deliver(
        self,
        *,
        channel: str,
        title: str,
        body: str,
        severity: str = "info",
        dedupe_key: str | None = None,
        source: str = "manual",
    ) -> dict[str, Any]:
        value = self.validate(
            channel=channel,
            title=title,
            body=body,
            severity=severity,
            dedupe_key=dedupe_key,
            source=source,
        )
        now = utc_now()
        with self.connect() as connection:
            if value["dedupe_key"] is None:
                cursor = connection.execute("""
                    INSERT INTO notifications(
                        protocol_version, channel, title, body, severity,
                        dedupe_key, source, status, created_at
                    ) VALUES(?,?,?,?,?,?,?,'delivered',?)
                """, (
                    self.PROTOCOL, value["channel"], value["title"],
                    value["body"], value["severity"], None, value["source"], now,
                ))
                notification_id = int(cursor.lastrowid)
            else:
                connection.execute("""
                    INSERT INTO notifications(
                        protocol_version, channel, title, body, severity,
                        dedupe_key, source, status, created_at
                    ) VALUES(?,?,?,?,?,?,?,'delivered',?)
                    ON CONFLICT(channel, dedupe_key) DO UPDATE SET
                        title=excluded.title,
                        body=excluded.body,
                        severity=excluded.severity,
                        source=excluded.source,
                        status='delivered',
                        created_at=excluded.created_at,
                        read_at=NULL
                """, (
                    self.PROTOCOL, value["channel"], value["title"],
                    value["body"], value["severity"], value["dedupe_key"],
                    value["source"], now,
                ))
                row = connection.execute(
                    "SELECT id FROM notifications WHERE channel=? AND dedupe_key=?",
                    (value["channel"], value["dedupe_key"]),
                ).fetchone()
                notification_id = int(row["id"])
            connection.execute("""
                DELETE FROM notifications WHERE id NOT IN (
                    SELECT id FROM notifications
                    ORDER BY created_at DESC, id DESC LIMIT ?
                )
            """, (self.MAX_RECORDS,))
            row = connection.execute(
                "SELECT * FROM notifications WHERE id=?", (notification_id,)
            ).fetchone()
        return self._public(row)

    def list(
        self, *, limit: int = 50, unread_only: bool = False,
    ) -> list[dict[str, Any]]:
        where = "WHERE status='delivered'" if unread_only else ""
        with self.connect() as connection:
            rows = connection.execute(
                f"SELECT * FROM notifications {where} "
                "ORDER BY created_at DESC, id DESC LIMIT ?",
                (max(1, min(limit, 100)),),
            ).fetchall()
        return [self._public(row) for row in rows]

    def mark_read(self, notification_id: int) -> bool:
        if isinstance(notification_id, bool) or not isinstance(notification_id, int):
            raise ValueError("Notification ID must be an integer")
        with self.connect() as connection:
            cursor = connection.execute("""
                UPDATE notifications SET status='read', read_at=?
                WHERE id=? AND status='delivered'
            """, (utc_now(), notification_id))
        return cursor.rowcount == 1

    def stats(self) -> dict[str, int]:
        with self.connect() as connection:
            total = int(connection.execute(
                "SELECT COUNT(*) FROM notifications"
            ).fetchone()[0])
            unread = int(connection.execute(
                "SELECT COUNT(*) FROM notifications WHERE status='delivered'"
            ).fetchone()[0])
        return {"total": total, "unread": unread}

    @staticmethod
    def _public(row: sqlite3.Row) -> dict[str, Any]:
        return {
            "notification_id": row["id"],
            "protocol_version": row["protocol_version"],
            "channel": row["channel"],
            "title": row["title"],
            "body": row["body"],
            "severity": row["severity"],
            "dedupe_key": row["dedupe_key"],
            "source": row["source"],
            "status": row["status"],
            "created_at": row["created_at"],
            "read_at": row["read_at"],
        }
