from __future__ import annotations

import hashlib
import json
import re
import sqlite3
from pathlib import Path, PurePosixPath
from typing import Any

from sparkle.config import data_root
from sparkle.storage import SQLiteStore, utc_now


class WorkspaceManager(SQLiteStore):
    """Creates bounded application workspaces without arbitrary command execution."""

    NAME_PATTERN = re.compile(r"^[a-z][a-z0-9_-]{1,63}$")

    def __init__(self, root: Path | None = None, path: Path | None = None):
        self.root = (root or data_root() / "applications").resolve()
        self.root.mkdir(parents=True, exist_ok=True)
        super().__init__(path or data_root() / "data_environment" / "builds.sqlite3")
        self.initialize()

    def initialize(self) -> None:
        with self.connect() as connection:
            connection.execute("""
                CREATE TABLE IF NOT EXISTS builds (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    project_name TEXT NOT NULL,
                    files_json TEXT NOT NULL,
                    total_bytes INTEGER NOT NULL,
                    status TEXT NOT NULL,
                    created_at TEXT NOT NULL
                )
            """)

    @staticmethod
    def _validate_relative_path(value: str) -> PurePosixPath:
        if not value or len(value) > 240 or "\0" in value or "\\" in value:
            raise ValueError("Build file paths must contain 1-240 POSIX characters")
        path = PurePosixPath(value)
        if path.is_absolute() or any(part in {"", ".", ".."} for part in path.parts):
            raise ValueError(f"Build file path escapes the workspace: {value}")
        return path

    def scaffold(
        self,
        project_name: str,
        files: dict[str, str],
        *,
        overwrite: bool = False,
    ) -> dict[str, Any]:
        if not self.NAME_PATTERN.fullmatch(project_name):
            raise ValueError("Project name must be a 2-64 character lowercase identifier")
        if not files or len(files) > 100:
            raise ValueError("A build manifest must contain 1-100 files")

        normalized: list[tuple[PurePosixPath, str]] = []
        total_bytes = 0
        for raw_path, content in files.items():
            if not isinstance(raw_path, str) or not isinstance(content, str):
                raise TypeError("Build manifest paths and contents must be strings")
            relative = self._validate_relative_path(raw_path)
            size = len(content.encode("utf-8"))
            if size > 250_000:
                raise ValueError(f"Build file exceeds 250000 bytes: {raw_path}")
            total_bytes += size
            normalized.append((relative, content))
        if total_bytes > 1_000_000:
            raise ValueError("Build manifest exceeds the 1000000-byte limit")

        target_root = (self.root / project_name).resolve()
        if target_root.parent != self.root:
            raise ValueError("Project path escapes the applications root")
        if target_root.exists() and target_root.is_symlink():
            raise ValueError("Application workspace cannot be a symlink")

        targets: list[tuple[Path, str, PurePosixPath]] = []
        for relative, content in normalized:
            target = (target_root / Path(*relative.parts)).resolve()
            if target_root not in target.parents:
                raise ValueError(f"Build file escapes the project workspace: {relative}")
            if target.exists() and not overwrite:
                raise FileExistsError(f"Build file already exists: {relative}")
            ancestor = target.parent
            while ancestor != target_root.parent:
                if ancestor.exists() and ancestor.is_symlink():
                    raise ValueError(f"Build path contains a symlink: {relative}")
                if ancestor == target_root:
                    break
                ancestor = ancestor.parent
            targets.append((target, content, relative))

        target_root.mkdir(parents=True, exist_ok=True)
        written: list[dict[str, Any]] = []
        for target, content, relative in targets:
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(content, encoding="utf-8")
            written.append({
                "path": relative.as_posix(),
                "sha256": hashlib.sha256(content.encode("utf-8")).hexdigest(),
                "bytes": len(content.encode("utf-8")),
            })

        now = utc_now()
        with self.connect() as connection:
            cursor = connection.execute("""
                INSERT INTO builds(project_name, files_json, total_bytes, status, created_at)
                VALUES(?,?,?,?,?)
            """, (
                project_name, json.dumps(written, separators=(",", ":")),
                total_bytes, "scaffolded", now,
            ))
        return {
            "build_id": int(cursor.lastrowid),
            "project_name": project_name,
            "workspace": str(target_root),
            "files": written,
            "total_bytes": total_bytes,
            "status": "scaffolded",
        }

    def list(self, *, limit: int = 20) -> list[dict[str, Any]]:
        with self.connect() as connection:
            rows = connection.execute(
                "SELECT * FROM builds ORDER BY id DESC LIMIT ?", (max(1, min(limit, 100)),)
            ).fetchall()
        return [self._public(row) for row in rows]

    @staticmethod
    def _public(row: sqlite3.Row) -> dict[str, Any]:
        return {
            "build_id": row["id"], "project_name": row["project_name"],
            "files": json.loads(row["files_json"]), "total_bytes": row["total_bytes"],
            "status": row["status"], "created_at": row["created_at"],
        }
