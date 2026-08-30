from __future__ import annotations

import json
import re
import sqlite3
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from sparkle.config import data_root
from sparkle.storage import SQLiteStore, utc_now


class ProjectStore(SQLiteStore):
    """Bounded structured project state and content-free change evidence."""

    PROTOCOL = "SPARKLE-PROJECT/1"
    MAX_PROJECTS = 1_000
    MAX_EVENTS = 10_000
    STATUSES = {
        "idea", "requirements", "design", "architecture", "tasks",
        "implementation", "testing", "documentation", "deployment",
        "review", "blocked", "complete",
    }
    PRIORITIES = {"low", "medium", "high", "critical"}
    MILESTONE_STATUSES = {"pending", "in_progress", "blocked", "complete"}
    NAME_PATTERN = re.compile(r"^[a-z][a-z0-9_-]{1,63}$")
    CREATE_FIELDS = {
        "name", "title", "description", "status", "priority", "deadline",
        "dependencies", "risks", "milestones", "blockers", "next_action",
        "progress",
    }
    UPDATE_FIELDS = CREATE_FIELDS - {"name"}

    def __init__(self, path: Path | None = None):
        super().__init__(
            path or data_root() / "data_environment" / "projects.sqlite3"
        )
        self.initialize()

    def initialize(self) -> None:
        with self.connect() as connection:
            connection.executescript("""
                CREATE TABLE IF NOT EXISTS projects (
                    name TEXT PRIMARY KEY,
                    title TEXT NOT NULL,
                    description TEXT NOT NULL,
                    status TEXT NOT NULL,
                    priority TEXT NOT NULL,
                    deadline TEXT,
                    dependencies_json TEXT NOT NULL,
                    risks_json TEXT NOT NULL,
                    milestones_json TEXT NOT NULL,
                    blockers_json TEXT NOT NULL,
                    next_action TEXT NOT NULL,
                    progress INTEGER NOT NULL,
                    version INTEGER NOT NULL,
                    archived INTEGER NOT NULL DEFAULT 0,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS project_events (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    project_name TEXT NOT NULL,
                    action TEXT NOT NULL,
                    version INTEGER NOT NULL,
                    changed_fields_json TEXT NOT NULL,
                    status TEXT NOT NULL,
                    priority TEXT NOT NULL,
                    progress INTEGER NOT NULL,
                    created_at TEXT NOT NULL
                );
                CREATE INDEX IF NOT EXISTS idx_project_events_name
                ON project_events(project_name, id DESC);
            """)

    @staticmethod
    def _text(value: Any, *, field: str, minimum: int, maximum: int) -> str:
        if not isinstance(value, str):
            raise ValueError(f"Project {field} must be a string")
        normalized = value.strip()
        if not minimum <= len(normalized) <= maximum:
            raise ValueError(
                f"Project {field} must contain {minimum}-{maximum} characters"
            )
        return normalized

    @classmethod
    def _strings(
        cls,
        value: Any,
        *,
        field: str,
        maximum: int,
        max_chars: int,
        identifiers: bool = False,
    ) -> list[str]:
        if not isinstance(value, list) or len(value) > maximum:
            raise ValueError(
                f"Project {field} must contain at most {maximum} items"
            )
        normalized: list[str] = []
        for item in value:
            if not isinstance(item, str) or not item.strip():
                raise ValueError(f"Project {field} items must be non-empty strings")
            item = item.strip()
            if len(item) > max_chars:
                raise ValueError(
                    f"Project {field} items exceed {max_chars} characters"
                )
            if identifiers and cls.NAME_PATTERN.fullmatch(item) is None:
                raise ValueError(f"Project {field} contains an invalid identifier")
            normalized.append(item)
        if len({item.casefold() for item in normalized}) != len(normalized):
            raise ValueError(f"Project {field} must not contain duplicates")
        return normalized

    @staticmethod
    def _timestamp(value: Any, *, field: str, nullable: bool = True) -> str | None:
        if value is None and nullable:
            return None
        if not isinstance(value, str) or not value.strip():
            raise ValueError(f"Project {field} must be an ISO-8601 timestamp or null")
        raw = value.strip().replace("Z", "+00:00")
        try:
            parsed = datetime.fromisoformat(raw)
        except ValueError as exc:
            raise ValueError(
                f"Project {field} must be an ISO-8601 timestamp or null"
            ) from exc
        if parsed.tzinfo is None:
            raise ValueError(f"Project {field} must include a timezone")
        return parsed.astimezone(UTC).isoformat()

    @classmethod
    def _milestones(cls, value: Any) -> list[dict[str, Any]]:
        if not isinstance(value, list) or len(value) > 50:
            raise ValueError("Project milestones must contain at most 50 items")
        result: list[dict[str, Any]] = []
        names: set[str] = set()
        for item in value:
            if not isinstance(item, dict) or set(item) != {
                "name", "status", "due_at",
            }:
                raise ValueError(
                    "Project milestones require only name, status, and due_at"
                )
            name = cls._text(
                item["name"], field="milestone name", minimum=1, maximum=120,
            )
            if name.casefold() in names:
                raise ValueError("Project milestone names must be unique")
            names.add(name.casefold())
            status = item["status"]
            if not isinstance(status, str) or status not in cls.MILESTONE_STATUSES:
                raise ValueError("Project milestone status is unsupported")
            result.append({
                "name": name,
                "status": status,
                "due_at": cls._timestamp(
                    item["due_at"], field="milestone due_at",
                ),
            })
        return result

    @classmethod
    def validate(cls, value: Any) -> dict[str, Any]:
        if not isinstance(value, dict) or set(value) != cls.CREATE_FIELDS:
            raise ValueError(
                "Project manifest must contain the exact SPARKLE-PROJECT/1 fields"
            )
        name = value["name"]
        if not isinstance(name, str) or cls.NAME_PATTERN.fullmatch(name) is None:
            raise ValueError("Project name must be a 2-64 character lowercase identifier")
        status = value["status"]
        priority = value["priority"]
        if not isinstance(status, str) or status not in cls.STATUSES:
            raise ValueError("Project status is unsupported")
        if not isinstance(priority, str) or priority not in cls.PRIORITIES:
            raise ValueError("Project priority is unsupported")
        progress = value["progress"]
        if type(progress) is not int or not 0 <= progress <= 100:
            raise ValueError("Project progress must be an integer from 0 to 100")
        dependencies = cls._strings(
            value["dependencies"], field="dependencies", maximum=20,
            max_chars=64, identifiers=True,
        )
        if name in dependencies:
            raise ValueError("Project cannot depend on itself")
        risks = cls._strings(
            value["risks"], field="risks", maximum=20, max_chars=300,
        )
        blockers = cls._strings(
            value["blockers"], field="blockers", maximum=20, max_chars=300,
        )
        milestones = cls._milestones(value["milestones"])
        if status == "blocked" and not blockers:
            raise ValueError("A blocked project must contain a blocker")
        if status == "complete":
            if progress != 100 or blockers:
                raise ValueError(
                    "A complete project requires 100 progress and no blockers"
                )
            if any(item["status"] != "complete" for item in milestones):
                raise ValueError("A complete project cannot have open milestones")
        elif progress == 100:
            raise ValueError("Only a complete project may have 100 progress")
        return {
            "name": name,
            "title": cls._text(
                value["title"], field="title", minimum=1, maximum=120,
            ),
            "description": cls._text(
                value["description"], field="description", minimum=1,
                maximum=1_000,
            ),
            "status": status,
            "priority": priority,
            "deadline": cls._timestamp(value["deadline"], field="deadline"),
            "dependencies": dependencies,
            "risks": risks,
            "milestones": milestones,
            "blockers": blockers,
            "next_action": cls._text(
                value["next_action"], field="next_action", minimum=1,
                maximum=500,
            ),
            "progress": progress,
        }

    @staticmethod
    def _json(value: Any) -> str:
        return json.dumps(
            value, ensure_ascii=False, separators=(",", ":"), sort_keys=True,
            allow_nan=False,
        )

    def _event(
        self,
        connection: sqlite3.Connection,
        project: dict[str, Any],
        *,
        action: str,
        changed_fields: list[str],
    ) -> None:
        connection.execute("""
            INSERT INTO project_events(
                project_name, action, version, changed_fields_json, status,
                priority, progress, created_at
            ) VALUES(?,?,?,?,?,?,?,?)
        """, (
            project["name"], action, project["version"],
            self._json(sorted(changed_fields)), project["status"],
            project["priority"], project["progress"], utc_now(),
        ))
        connection.execute("""
            DELETE FROM project_events WHERE id NOT IN (
                SELECT id FROM project_events ORDER BY id DESC LIMIT ?
            )
        """, (self.MAX_EVENTS,))

    def create(self, manifest: dict[str, Any]) -> dict[str, Any]:
        project = self.validate(manifest)
        now = utc_now()
        with self.connect() as connection:
            count = connection.execute(
                "SELECT COUNT(*) FROM projects WHERE archived=0"
            ).fetchone()[0]
            if count >= self.MAX_PROJECTS:
                raise ValueError("Project store reached its 1000 active-project bound")
            try:
                connection.execute("""
                    INSERT INTO projects(
                        name, title, description, status, priority, deadline,
                        dependencies_json, risks_json, milestones_json,
                        blockers_json, next_action, progress, version, archived,
                        created_at, updated_at
                    ) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,1,0,?,?)
                """, (
                    project["name"], project["title"], project["description"],
                    project["status"], project["priority"], project["deadline"],
                    self._json(project["dependencies"]),
                    self._json(project["risks"]),
                    self._json(project["milestones"]),
                    self._json(project["blockers"]), project["next_action"],
                    project["progress"], now, now,
                ))
            except sqlite3.IntegrityError as exc:
                raise ValueError(f"Project already exists: {project['name']}") from exc
            created = {**project, "version": 1, "archived": False}
            self._event(
                connection, created, action="created",
                changed_fields=sorted(self.CREATE_FIELDS),
            )
        return self.get(project["name"])

    @staticmethod
    def _public(row: sqlite3.Row) -> dict[str, Any]:
        return {
            "protocol_version": ProjectStore.PROTOCOL,
            "name": row["name"],
            "title": row["title"],
            "description": row["description"],
            "status": row["status"],
            "priority": row["priority"],
            "deadline": row["deadline"],
            "dependencies": json.loads(row["dependencies_json"]),
            "risks": json.loads(row["risks_json"]),
            "milestones": json.loads(row["milestones_json"]),
            "blockers": json.loads(row["blockers_json"]),
            "next_action": row["next_action"],
            "progress": row["progress"],
            "version": row["version"],
            "archived": bool(row["archived"]),
            "created_at": row["created_at"],
            "updated_at": row["updated_at"],
        }

    def get(self, name: str) -> dict[str, Any]:
        if not isinstance(name, str) or self.NAME_PATTERN.fullmatch(name) is None:
            raise ValueError("Project name is invalid")
        with self.connect() as connection:
            row = connection.execute(
                "SELECT * FROM projects WHERE name=?", (name,),
            ).fetchone()
        if row is None:
            raise KeyError(f"Unknown project: {name}")
        return self._public(row)

    def update(
        self,
        name: str,
        changes: dict[str, Any],
        *,
        expected_version: int,
    ) -> dict[str, Any]:
        current = self.get(name)
        if current["archived"]:
            raise ValueError("Archived projects cannot be updated")
        if type(expected_version) is not int or expected_version < 1:
            raise ValueError("Project expected_version must be a positive integer")
        if not isinstance(changes, dict) or not changes:
            raise ValueError("Project changes must be a non-empty object")
        unknown = set(changes) - self.UPDATE_FIELDS
        if unknown:
            raise ValueError(
                "Unsupported project change fields: " + ", ".join(sorted(unknown))
            )
        candidate = {
            field: current[field] for field in self.CREATE_FIELDS
        }
        candidate.update(changes)
        project = self.validate(candidate)
        now = utc_now()
        with self.connect() as connection:
            cursor = connection.execute("""
                UPDATE projects SET
                    title=?, description=?, status=?, priority=?, deadline=?,
                    dependencies_json=?, risks_json=?, milestones_json=?,
                    blockers_json=?, next_action=?, progress=?,
                    version=version+1, updated_at=?
                WHERE name=? AND version=? AND archived=0
            """, (
                project["title"], project["description"], project["status"],
                project["priority"], project["deadline"],
                self._json(project["dependencies"]),
                self._json(project["risks"]),
                self._json(project["milestones"]),
                self._json(project["blockers"]), project["next_action"],
                project["progress"], now, name, expected_version,
            ))
            if cursor.rowcount != 1:
                raise ValueError("Project version conflict")
            updated = {
                **project, "version": expected_version + 1, "archived": False,
            }
            self._event(
                connection, updated, action="updated",
                changed_fields=sorted(changes),
            )
        return self.get(name)

    def archive(self, name: str, *, expected_version: int) -> dict[str, Any]:
        current = self.get(name)
        if current["archived"]:
            raise ValueError("Project is already archived")
        if type(expected_version) is not int or expected_version < 1:
            raise ValueError("Project expected_version must be a positive integer")
        now = utc_now()
        with self.connect() as connection:
            cursor = connection.execute("""
                UPDATE projects SET archived=1, version=version+1, updated_at=?
                WHERE name=? AND version=? AND archived=0
            """, (now, name, expected_version))
            if cursor.rowcount != 1:
                raise ValueError("Project version conflict")
            archived = {
                **current, "version": expected_version + 1, "archived": True,
            }
            self._event(
                connection, archived, action="archived",
                changed_fields=["archived"],
            )
        return self.get(name)

    def list(
        self, *, limit: int = 50, include_archived: bool = False,
    ) -> list[dict[str, Any]]:
        if type(include_archived) is not bool:
            raise ValueError("include_archived must be boolean")
        bounded = max(1, min(int(limit), 100))
        where = "" if include_archived else "WHERE archived=0"
        with self.connect() as connection:
            rows = connection.execute(f"""
                SELECT * FROM projects {where}
                ORDER BY
                    CASE priority
                        WHEN 'critical' THEN 0 WHEN 'high' THEN 1
                        WHEN 'medium' THEN 2 ELSE 3
                    END,
                    CASE WHEN deadline IS NULL THEN 1 ELSE 0 END,
                    deadline ASC, updated_at DESC, name ASC
                LIMIT ?
            """, (bounded,)).fetchall()
        return [self._public(row) for row in rows]

    def search(self, query: str, *, limit: int = 10) -> list[dict[str, Any]]:
        if not isinstance(query, str) or len(query.strip()) > 200:
            raise ValueError("Project search query must contain at most 200 characters")
        normalized = query.strip()
        if not normalized:
            return self.list(limit=max(1, min(int(limit), 20)))
        escaped = normalized.replace("!", "!!").replace("%", "!%").replace("_", "!_")
        pattern = f"%{escaped}%"
        with self.connect() as connection:
            rows = connection.execute("""
                SELECT * FROM projects
                WHERE archived=0 AND (
                    name LIKE ? ESCAPE '!' OR title LIKE ? ESCAPE '!'
                    OR description LIKE ? ESCAPE '!'
                    OR next_action LIKE ? ESCAPE '!'
                )
                ORDER BY updated_at DESC, name ASC LIMIT ?
            """, (
                pattern, pattern, pattern, pattern,
                max(1, min(int(limit), 20)),
            )).fetchall()
        return [self._public(row) for row in rows]

    def events(self, name: str, *, limit: int = 50) -> list[dict[str, Any]]:
        self.get(name)
        with self.connect() as connection:
            rows = connection.execute("""
                SELECT * FROM project_events
                WHERE project_name=? ORDER BY id DESC LIMIT ?
            """, (name, max(1, min(int(limit), 100)))).fetchall()
        return [{
            "event_id": row["id"],
            "project_name": row["project_name"],
            "action": row["action"],
            "version": row["version"],
            "changed_fields": json.loads(row["changed_fields_json"]),
            "status": row["status"],
            "priority": row["priority"],
            "progress": row["progress"],
            "created_at": row["created_at"],
        } for row in rows]

    def stats(self) -> dict[str, int]:
        with self.connect() as connection:
            row = connection.execute("""
                SELECT
                    SUM(CASE WHEN archived=0 THEN 1 ELSE 0 END) AS active,
                    SUM(CASE WHEN archived=1 THEN 1 ELSE 0 END) AS archived,
                    SUM(CASE WHEN archived=0 AND status='blocked' THEN 1 ELSE 0 END)
                        AS blocked
                FROM projects
            """).fetchone()
        return {
            "active": int(row["active"] or 0),
            "archived": int(row["archived"] or 0),
            "blocked": int(row["blocked"] or 0),
        }
