from __future__ import annotations

import hashlib
import json
import os
import re
from pathlib import Path, PurePosixPath
from typing import Any

from sparkle.config import data_root, project_root
from sparkle.contracts import ToolDefinition
from sparkle.storage import SQLiteStore, utc_now


class EngineeringWorkflowError(ValueError):
    pass


class RepositoryEngineeringService(SQLiteStore):
    """Bounded repository inventory plus persistent engineering decision/work state."""

    NAME = re.compile(r"^[a-z][a-z0-9_-]{1,63}$")
    STATES = {"planned", "in_progress", "blocked", "ready_for_review", "complete", "archived"}
    TRANSITIONS = {
        "planned": {"in_progress", "blocked", "archived"},
        "in_progress": {"blocked", "ready_for_review", "archived"},
        "blocked": {"in_progress", "archived"},
        "ready_for_review": {"in_progress", "complete", "archived"},
        "complete": {"in_progress", "archived"},
        "archived": set(),
    }
    PRIORITIES = {"P0", "P1", "P2", "P3"}
    MAX_FILES = 5_000
    MAX_FILE_BYTES = 1_000_000
    MAX_PLAN_ITEMS = 200
    MAX_TEXT = 20_000
    EXCLUDED = {".git", ".venv", "venv", "node_modules", "__pycache__", ".pytest_cache", "dist", "build"}

    def __init__(self, root: Path | None = None, path: Path | None = None):
        self.root = (root or project_root()).resolve()
        if not self.root.is_dir():
            raise EngineeringWorkflowError("Repository root is unavailable")
        super().__init__(path or data_root() / "data_environment" / "engineering.sqlite3")
        self.initialize()

    def initialize(self) -> None:
        with self.connect() as db:
            db.executescript("""
                CREATE TABLE IF NOT EXISTS engineering_work_items(
                    name TEXT PRIMARY KEY,title TEXT NOT NULL,objective TEXT NOT NULL,
                    requirements_json TEXT NOT NULL,design_json TEXT NOT NULL,files_json TEXT NOT NULL,
                    risks_json TEXT NOT NULL,tests_json TEXT NOT NULL,debt_json TEXT NOT NULL,
                    release_notes TEXT NOT NULL,priority TEXT NOT NULL,state TEXT NOT NULL,
                    revision INTEGER NOT NULL,created_at TEXT NOT NULL,updated_at TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS engineering_events(
                    id INTEGER PRIMARY KEY AUTOINCREMENT,work_item TEXT NOT NULL,event TEXT NOT NULL,
                    revision INTEGER NOT NULL,actor TEXT NOT NULL,created_at TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS repository_snapshots(
                    id INTEGER PRIMARY KEY AUTOINCREMENT,tree_sha256 TEXT NOT NULL,file_count INTEGER NOT NULL,
                    total_bytes INTEGER NOT NULL,manifest_json TEXT NOT NULL,created_at TEXT NOT NULL
                );
            """)

    @staticmethod
    def _json(value: Any) -> str:
        return json.dumps(value, ensure_ascii=False, separators=(",", ":"), sort_keys=True, allow_nan=False)

    @classmethod
    def _name(cls, value: Any) -> str:
        if not isinstance(value, str) or not cls.NAME.fullmatch(value):
            raise EngineeringWorkflowError("Work item name must be a 2-64 character lowercase identifier")
        return value

    @classmethod
    def _text(cls, value: Any, field: str, maximum: int | None = None) -> str:
        limit = maximum or cls.MAX_TEXT
        if not isinstance(value, str) or not value.strip() or len(value.strip()) > limit:
            raise EngineeringWorkflowError(f"{field} must contain 1-{limit} characters")
        return value.strip()

    @classmethod
    def _strings(cls, value: Any, field: str, maximum: int = 100) -> list[str]:
        if not isinstance(value, list) or len(value) > maximum:
            raise EngineeringWorkflowError(f"{field} must be a bounded string list")
        items = [cls._text(item, field, 1000) for item in value]
        if len(items) != len(set(items)):
            raise EngineeringWorkflowError(f"{field} must not contain duplicates")
        return items

    def _walk(self) -> list[dict[str, Any]]:
        files: list[dict[str, Any]] = []
        for current, directories, names in os.walk(self.root, followlinks=False):
            directories[:] = sorted(d for d in directories if d not in self.EXCLUDED and not d.startswith("."))
            base = Path(current)
            for name in sorted(names):
                target = base / name
                if target.is_symlink() or not target.is_file():
                    continue
                relative = target.relative_to(self.root)
                if any(part in self.EXCLUDED for part in relative.parts) or relative.name.startswith(".env"):
                    continue
                size = target.stat().st_size
                if size > self.MAX_FILE_BYTES:
                    continue
                files.append({"path": relative.as_posix(), "bytes": size, "suffix": target.suffix.lower()})
                if len(files) > self.MAX_FILES:
                    raise EngineeringWorkflowError("Repository exceeds the bounded file inventory")
        return files

    def snapshot(self, *, persist: bool = True) -> dict[str, Any]:
        manifest = self._walk()
        total = sum(item["bytes"] for item in manifest)
        digest = hashlib.sha256(self._json(manifest).encode()).hexdigest()
        languages: dict[str, int] = {}
        for item in manifest:
            key = item["suffix"] or "[none]"
            languages[key] = languages.get(key, 0) + 1
        value = {"tree_sha256": digest, "file_count": len(manifest), "total_bytes": total,
                 "languages": dict(sorted(languages.items())), "manifest": manifest}
        if persist:
            now = utc_now()
            with self.connect() as db:
                cursor = db.execute("INSERT INTO repository_snapshots(tree_sha256,file_count,total_bytes,manifest_json,created_at) VALUES(?,?,?,?,?)",
                                    (digest, len(manifest), total, self._json(manifest), now))
            value |= {"snapshot_id": int(cursor.lastrowid), "created_at": now}
        return value

    def inspect_file(self, path: str, *, max_chars: int = 20_000) -> dict[str, Any]:
        if not isinstance(path, str) or not path or "\\" in path:
            raise EngineeringWorkflowError("Repository path is invalid")
        relative = PurePosixPath(path)
        if relative.is_absolute() or any(part in {"", ".", ".."} or part in self.EXCLUDED for part in relative.parts):
            raise EngineeringWorkflowError("Repository path is invalid")
        target = self.root.joinpath(*relative.parts)
        if target.is_symlink() or not target.is_file() or self.root not in target.resolve().parents:
            raise EngineeringWorkflowError("Repository file is unavailable")
        if target.stat().st_size > self.MAX_FILE_BYTES:
            raise EngineeringWorkflowError("Repository file exceeds inspection bound")
        try:
            text = target.read_text(encoding="utf-8")
        except UnicodeDecodeError as exc:
            raise EngineeringWorkflowError("Repository inspection accepts UTF-8 text only") from exc
        if type(max_chars) is not int or not 1 <= max_chars <= self.MAX_TEXT:
            raise EngineeringWorkflowError("Repository inspection character bound is invalid")
        encoded = target.read_bytes()
        return {"path": relative.as_posix(), "bytes": len(encoded), "sha256": hashlib.sha256(encoded).hexdigest(),
                "content": text[:max_chars], "truncated": len(text) > max_chars}

    def create_work_item(self, definition: dict[str, Any], *, actor: str = "operator") -> dict[str, Any]:
        required = {"name", "title", "objective", "requirements", "design", "files", "risks", "tests", "debt", "priority"}
        if not isinstance(definition, dict) or set(definition) != required:
            raise EngineeringWorkflowError("Engineering work-item fields are invalid")
        name = self._name(definition["name"])
        priority = definition["priority"]
        if priority not in self.PRIORITIES:
            raise EngineeringWorkflowError("Engineering priority is invalid")
        values = {
            "title": self._text(definition["title"], "title", 200),
            "objective": self._text(definition["objective"], "objective", 3000),
            "requirements": self._strings(definition["requirements"], "requirements"),
            "design": self._strings(definition["design"], "design"),
            "files": self._strings(definition["files"], "files"),
            "risks": self._strings(definition["risks"], "risks"),
            "tests": self._strings(definition["tests"], "tests"),
            "debt": self._strings(definition["debt"], "debt"),
        }
        actor = self._text(actor, "actor", 80)
        now = utc_now()
        with self.connect() as db:
            db.execute("BEGIN IMMEDIATE")
            if db.execute("SELECT 1 FROM engineering_work_items WHERE name=?", (name,)).fetchone():
                raise EngineeringWorkflowError("Engineering work item already exists")
            if db.execute("SELECT count(*) FROM engineering_work_items").fetchone()[0] >= self.MAX_PLAN_ITEMS:
                raise EngineeringWorkflowError("Engineering work-item limit reached")
            db.execute("INSERT INTO engineering_work_items VALUES(?,?,?,?,?,?,?,?,?,?,?, 'planned',1,?,?)", (
                name, values["title"], values["objective"], self._json(values["requirements"]), self._json(values["design"]),
                self._json(values["files"]), self._json(values["risks"]), self._json(values["tests"]), self._json(values["debt"]),
                "", priority, now, now,
            ))
            db.execute("INSERT INTO engineering_events(work_item,event,revision,actor,created_at) VALUES(?,?,?,?,?)",
                       (name, "create", 1, actor, now))
        return self.work_item(name)

    def work_item(self, name: str, *, include_archived: bool = False) -> dict[str, Any]:
        name = self._name(name)
        with self.connect() as db:
            row = db.execute("SELECT * FROM engineering_work_items WHERE name=?", (name,)).fetchone()
        if row is None or (row["state"] == "archived" and not include_archived):
            raise EngineeringWorkflowError("Unknown active engineering work item")
        value = {key: row[key] for key in ("name", "title", "objective", "release_notes", "priority", "state", "revision", "created_at", "updated_at")}
        for key in ("requirements", "design", "files", "risks", "tests", "debt"):
            value[key] = json.loads(row[f"{key}_json"])
        return value

    def list_work(self, *, include_archived: bool = False, limit: int = 100) -> list[dict[str, Any]]:
        if type(limit) is not int or not 1 <= limit <= 100:
            raise EngineeringWorkflowError("Engineering list limit is invalid")
        query = "SELECT name,title,priority,state,revision,updated_at FROM engineering_work_items"
        if not include_archived:
            query += " WHERE state!='archived'"
        with self.connect() as db:
            rows = db.execute(query + " ORDER BY priority,name LIMIT ?", (limit,)).fetchall()
        return [dict(row) for row in rows]

    def transition(self, name: str, state: str, *, expected_revision: int,
                   release_notes: str | None = None, actor: str = "operator") -> dict[str, Any]:
        name = self._name(name)
        if state not in self.STATES:
            raise EngineeringWorkflowError("Engineering state is invalid")
        actor = self._text(actor, "actor", 80)
        with self.connect() as db:
            db.execute("BEGIN IMMEDIATE")
            row = db.execute("SELECT state,revision,release_notes FROM engineering_work_items WHERE name=?", (name,)).fetchone()
            if row is None:
                raise EngineeringWorkflowError("Unknown engineering work item")
            if row["revision"] != expected_revision:
                raise EngineeringWorkflowError(f"Engineering revision conflict: expected {expected_revision}, current {row['revision']}")
            if state not in self.TRANSITIONS[row["state"]]:
                raise EngineeringWorkflowError(f"Invalid engineering transition: {row['state']} -> {state}")
            notes = row["release_notes"]
            if release_notes is not None:
                notes = self._text(release_notes, "release notes", 10_000)
            if state == "complete" and not notes:
                raise EngineeringWorkflowError("Completed engineering work requires release notes")
            revision, now = expected_revision + 1, utc_now()
            db.execute("UPDATE engineering_work_items SET state=?,release_notes=?,revision=?,updated_at=? WHERE name=?",
                       (state, notes, revision, now, name))
            db.execute("INSERT INTO engineering_events(work_item,event,revision,actor,created_at) VALUES(?,?,?,?,?)",
                       (name, f"state:{state}", revision, actor, now))
        return self.work_item(name, include_archived=True)

    def readiness(self, name: str) -> dict[str, Any]:
        item = self.work_item(name, include_archived=True)
        checks = {
            "requirements_defined": bool(item["requirements"]),
            "design_defined": bool(item["design"]),
            "files_identified": bool(item["files"]),
            "tests_defined": bool(item["tests"]),
            "risks_recorded": bool(item["risks"]),
            "release_notes_present": bool(item["release_notes"]),
            "workflow_complete": item["state"] == "complete",
        }
        return {"work_item": name, "checks": checks, "ready": all(checks.values()),
                "execution_verified": False, "deployment_verified": False}

    def stats(self) -> dict[str, Any]:
        with self.connect() as db:
            active = db.execute("SELECT count(*) FROM engineering_work_items WHERE state!='archived'").fetchone()[0]
            snapshots = db.execute("SELECT count(*) FROM repository_snapshots").fetchone()[0]
        return {"status": "ready", "active_work_items": active, "snapshots": snapshots}


class EngineeringReadTool:
    name = "engineering_inspect"
    description = "Inspect bounded repository structure/file identity or persistent engineering work plans. Read-only; does not modify source or claim tests ran."
    parameters = {"type": "object", "properties": {
        "operation": {"type": "string", "enum": ["snapshot", "file", "work_item", "readiness"]},
        "path": {"type": "string"}, "name": {"type": "string"}},
        "required": ["operation"], "additionalProperties": False}

    def __init__(self, service: RepositoryEngineeringService):
        self.service = service

    def definition(self) -> ToolDefinition:
        return ToolDefinition(self.name, self.description, self.parameters)

    def run(self, arguments: dict[str, Any]) -> Any:
        if not isinstance(arguments, dict) or set(arguments) - {"operation", "path", "name"}:
            raise EngineeringWorkflowError("Engineering inspection fields are invalid")
        operation = arguments.get("operation")
        if operation == "snapshot":
            return self.service.snapshot(persist=False)
        if operation == "file":
            return self.service.inspect_file(str(arguments.get("path", "")))
        if operation == "work_item":
            return self.service.work_item(str(arguments.get("name", "")))
        if operation == "readiness":
            return self.service.readiness(str(arguments.get("name", "")))
        raise EngineeringWorkflowError("Unsupported engineering inspection operation")
