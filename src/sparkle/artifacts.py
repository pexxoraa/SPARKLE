from __future__ import annotations

import hashlib
import io
import json
import os
import re
import sqlite3
import stat
import zipfile
from pathlib import Path, PurePosixPath
from typing import Any

from sparkle.builders import WorkspaceManager
from sparkle.config import data_root
from sparkle.external_worker import ExternalWorkerClient
from sparkle.storage import SQLiteStore, utc_now


class ArtifactManager(SQLiteStore):
    """Creates content-addressed application ZIPs without executing project code."""

    PROTOCOL = "SPARKLE-ARTIFACT/1"
    MANIFEST_PATH = "SPARKLE_ARTIFACT_MANIFEST.json"
    MAX_FILES = 500
    MAX_FILE_BYTES = 1_000_000
    MAX_TOTAL_BYTES = 10_000_000
    TARGET_KINDS = {
        "container", "desktop", "local", "mobile", "server", "static_host",
    }
    REPORTED_OUTCOMES = {
        "planned", "attempted", "reported_success", "failed", "rolled_back",
    }
    SAFE_LABEL = re.compile(r"^[a-z][a-z0-9_-]{1,63}$")
    WINDOWS_DEVICES = {
        "aux", "con", "nul", "prn",
        *(f"com{number}" for number in range(1, 10)),
        *(f"lpt{number}" for number in range(1, 10)),
    }

    def __init__(
        self,
        workspace_root: Path | None = None,
        artifact_root: Path | None = None,
        path: Path | None = None,
    ):
        root = data_root()
        self.workspace_root = (
            workspace_root or root / "applications"
        ).resolve()
        self.artifact_root = (
            artifact_root or root / "data_environment" / "artifacts"
        ).resolve()
        self.workspace_root.mkdir(parents=True, exist_ok=True)
        self.artifact_root.mkdir(parents=True, exist_ok=True, mode=0o700)
        self.artifact_root.chmod(0o700)
        super().__init__(path or root / "data_environment" / "artifacts.sqlite3")
        self.initialize()

    def initialize(self) -> None:
        with self.connect() as connection:
            connection.executescript("""
                CREATE TABLE IF NOT EXISTS artifacts (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    project_name TEXT NOT NULL,
                    source_digest TEXT NOT NULL,
                    artifact_name TEXT NOT NULL,
                    artifact_sha256 TEXT NOT NULL,
                    manifest_json TEXT NOT NULL,
                    file_count INTEGER NOT NULL,
                    source_bytes INTEGER NOT NULL,
                    artifact_bytes INTEGER NOT NULL,
                    status TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    UNIQUE(project_name, source_digest),
                    UNIQUE(artifact_name)
                );
                CREATE TABLE IF NOT EXISTS deployment_records (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    artifact_id INTEGER NOT NULL REFERENCES artifacts(id),
                    environment_name TEXT NOT NULL,
                    target_kind TEXT NOT NULL,
                    reported_outcome TEXT NOT NULL,
                    verification_status TEXT NOT NULL,
                    external_action_executed INTEGER NOT NULL,
                    created_at TEXT NOT NULL
                );
                CREATE INDEX IF NOT EXISTS idx_deployments_artifact
                ON deployment_records(artifact_id, id);
            """)

    def _project_root(self, project_name: str) -> Path:
        if not WorkspaceManager.NAME_PATTERN.fullmatch(project_name):
            raise ValueError("Project name must be a 2-64 character lowercase identifier")
        project = self.workspace_root / project_name
        if project.is_symlink():
            raise ValueError("Artifact packaging rejects every symlink")
        resolved = project.resolve()
        if resolved.parent != self.workspace_root or not resolved.is_dir():
            raise ValueError(f"Application workspace does not exist: {project_name}")
        return resolved

    @staticmethod
    def _validate_path(relative: PurePosixPath) -> None:
        raw = relative.as_posix()
        lowered = [part.lower() for part in relative.parts]
        if (
            not raw
            or len(raw) > 240
            or raw.casefold() == ArtifactManager.MANIFEST_PATH.casefold()
            or any(part.startswith(".") for part in relative.parts)
            or any(
                any(ord(character) < 32 or character in '<>:"|?*' for character in part)
                or part.endswith((" ", "."))
                or part.split(".", 1)[0].casefold() in ArtifactManager.WINDOWS_DEVICES
                for part in relative.parts
            )
            or any(
                part in ExternalWorkerClient._SENSITIVE_PARTS
                or "secret" in part
                or "credential" in part
                for part in lowered
            )
            or relative.suffix.lower() in ExternalWorkerClient._SENSITIVE_SUFFIXES
        ):
            raise ValueError("Artifact packaging rejects hidden, reserved, or sensitive paths")

    def _source_files(
        self, project: Path,
    ) -> tuple[list[tuple[str, bytes]], list[dict[str, Any]], int]:
        files: list[tuple[str, bytes]] = []
        metadata: list[dict[str, Any]] = []
        portable_paths: set[str] = set()
        total_bytes = 0
        for current, directories, names in os.walk(project, followlinks=False):
            directories.sort()
            names.sort()
            current_path = Path(current)
            for name in [*directories, *names]:
                if (current_path / name).is_symlink():
                    raise ValueError("Artifact packaging rejects every symlink")
            for name in names:
                candidate = current_path / name
                relative_path = candidate.relative_to(project)
                relative = PurePosixPath(*relative_path.parts)
                self._validate_path(relative)
                content = self._read_stable_regular(candidate, self.MAX_FILE_BYTES)
                total_bytes += len(content)
                if len(files) + 1 > self.MAX_FILES or total_bytes > self.MAX_TOTAL_BYTES:
                    raise ValueError("Artifact source exceeds packaging bounds")
                raw_path = relative.as_posix()
                portable_path = raw_path.casefold()
                if portable_path in portable_paths:
                    raise ValueError("Artifact source paths collide on portable filesystems")
                portable_paths.add(portable_path)
                digest = hashlib.sha256(content).hexdigest()
                files.append((raw_path, content))
                metadata.append({
                    "path": raw_path,
                    "bytes": len(content),
                    "sha256": digest,
                })
        if not files:
            raise ValueError("Artifact source workspace cannot be empty")
        return files, metadata, total_bytes

    @staticmethod
    def _read_stable_regular(path: Path, maximum: int) -> bytes:
        flags = os.O_RDONLY | getattr(os, "O_CLOEXEC", 0) | getattr(os, "O_NOFOLLOW", 0)
        try:
            descriptor = os.open(path, flags)
        except OSError as exc:
            raise ValueError("Artifact packaging accepts regular non-symlink files only") from exc
        try:
            before = os.fstat(descriptor)
            if not stat.S_ISREG(before.st_mode):
                raise ValueError("Artifact packaging accepts regular files only")
            if before.st_size > maximum:
                raise ValueError(f"Artifact source file exceeds {maximum} bytes")
            chunks: list[bytes] = []
            remaining = maximum + 1
            while remaining:
                chunk = os.read(descriptor, min(65_536, remaining))
                if not chunk:
                    break
                chunks.append(chunk)
                remaining -= len(chunk)
            content = b"".join(chunks)
            after = os.fstat(descriptor)
        finally:
            os.close(descriptor)
        if len(content) > maximum:
            raise ValueError(f"Artifact source file exceeds {maximum} bytes")
        identity_before = (
            before.st_dev, before.st_ino, before.st_size, before.st_mtime_ns,
        )
        identity_after = (
            after.st_dev, after.st_ino, after.st_size, after.st_mtime_ns,
        )
        if identity_before != identity_after or len(content) != before.st_size:
            raise ValueError("Artifact source changed during packaging")
        return content

    @staticmethod
    def _canonical_json(value: dict[str, Any]) -> bytes:
        return json.dumps(
            value, sort_keys=True, separators=(",", ":"), ensure_ascii=False,
        ).encode("utf-8")

    @staticmethod
    def _zip_info(path: str) -> zipfile.ZipInfo:
        info = zipfile.ZipInfo(path, date_time=(1980, 1, 1, 0, 0, 0))
        info.compress_type = zipfile.ZIP_STORED
        info.create_system = 3
        info.external_attr = (stat.S_IFREG | 0o644) << 16
        info.flag_bits = 0x800
        return info

    def _build_archive(
        self,
        project_name: str,
        files: list[tuple[str, bytes]],
        metadata: list[dict[str, Any]],
        total_bytes: int,
    ) -> tuple[bytes, dict[str, Any]]:
        source_value = {
            "project_name": project_name,
            "files": metadata,
            "source_bytes": total_bytes,
        }
        source_digest = hashlib.sha256(self._canonical_json(source_value)).hexdigest()
        manifest = {
            "protocol_version": self.PROTOCOL,
            **source_value,
            "source_digest": source_digest,
            "archive_format": "zip-stored",
            "verification_status": "not_attested",
        }
        entries = [*files, (self.MANIFEST_PATH, self._canonical_json(manifest))]
        buffer = io.BytesIO()
        with zipfile.ZipFile(buffer, mode="w", compression=zipfile.ZIP_STORED) as archive:
            for raw_path, content in sorted(entries, key=lambda item: item[0]):
                archive.writestr(self._zip_info(raw_path), content)
        return buffer.getvalue(), manifest

    def package(self, project_name: str) -> dict[str, Any]:
        project = self._project_root(project_name)
        files, metadata, total_bytes = self._source_files(project)
        archive, manifest = self._build_archive(
            project_name, files, metadata, total_bytes,
        )
        source_digest = manifest["source_digest"]
        artifact_digest = hashlib.sha256(archive).hexdigest()
        artifact_name = f"{project_name}/{project_name}-{source_digest[:16]}.zip"
        target = self.artifact_root.joinpath(*PurePosixPath(artifact_name).parts)
        target.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
        target.parent.chmod(0o700)
        reused = target.exists()
        if reused:
            if target.is_symlink() or not target.is_file():
                raise ValueError("Artifact target must be a regular non-symlink file")
            existing = self._read_stable_regular(
                target, self.MAX_TOTAL_BYTES + 1_000_000,
            )
            if not hashlib.sha256(existing).hexdigest() == artifact_digest:
                raise RuntimeError("Existing immutable artifact failed integrity validation")
        else:
            try:
                with target.open("xb") as handle:
                    handle.write(archive)
                target.chmod(0o600)
            except Exception:
                target.unlink(missing_ok=True)
                raise

        now = utc_now()
        encoded_manifest = self._canonical_json(manifest).decode("utf-8")
        with self.connect() as connection:
            connection.execute("""
                INSERT INTO artifacts(
                    project_name, source_digest, artifact_name, artifact_sha256,
                    manifest_json, file_count, source_bytes, artifact_bytes,
                    status, created_at
                ) VALUES(?,?,?,?,?,?,?,?,?,?)
                ON CONFLICT(project_name, source_digest) DO NOTHING
            """, (
                project_name, source_digest, artifact_name, artifact_digest,
                encoded_manifest, len(metadata), total_bytes, len(archive),
                "packaged_unverified", now,
            ))
            row = connection.execute(
                "SELECT * FROM artifacts WHERE project_name=? AND source_digest=?",
                (project_name, source_digest),
            ).fetchone()
        if (
            row is None
            or row["artifact_name"] != artifact_name
            or row["artifact_sha256"] != artifact_digest
        ):
            raise RuntimeError("Artifact record failed immutable consistency validation")
        value = self._public_artifact(row)
        value["reused"] = reused
        return value

    def record_deployment(
        self,
        artifact_id: int,
        environment_name: str,
        target_kind: str,
        reported_outcome: str,
    ) -> dict[str, Any]:
        if isinstance(artifact_id, bool) or not isinstance(artifact_id, int):
            raise ValueError("Artifact ID must be an integer")
        if not self.SAFE_LABEL.fullmatch(environment_name):
            raise ValueError("Deployment environment must be a safe 2-64 character identifier")
        if target_kind not in self.TARGET_KINDS:
            raise ValueError("Deployment target kind is unsupported")
        if reported_outcome not in self.REPORTED_OUTCOMES:
            raise ValueError("Deployment reported outcome is unsupported")
        now = utc_now()
        with self.connect() as connection:
            if connection.execute(
                "SELECT 1 FROM artifacts WHERE id=?", (artifact_id,),
            ).fetchone() is None:
                raise ValueError("Artifact does not exist")
            cursor = connection.execute("""
                INSERT INTO deployment_records(
                    artifact_id, environment_name, target_kind, reported_outcome,
                    verification_status, external_action_executed, created_at
                ) VALUES(?,?,?,?, 'unverified', 0, ?)
            """, (
                artifact_id, environment_name, target_kind, reported_outcome, now,
            ))
            row = connection.execute(
                "SELECT * FROM deployment_records WHERE id=?", (cursor.lastrowid,),
            ).fetchone()
        return self._public_deployment(row)

    def list(self, *, limit: int = 20) -> list[dict[str, Any]]:
        with self.connect() as connection:
            rows = connection.execute(
                "SELECT * FROM artifacts ORDER BY id DESC LIMIT ?",
                (max(1, min(limit, 100)),),
            ).fetchall()
        return [self._public_artifact(row) for row in rows]

    def list_deployments(self, *, limit: int = 20) -> list[dict[str, Any]]:
        with self.connect() as connection:
            rows = connection.execute("""
                SELECT deployment_records.*, artifacts.project_name,
                       artifacts.artifact_sha256
                FROM deployment_records
                JOIN artifacts ON artifacts.id=deployment_records.artifact_id
                ORDER BY deployment_records.id DESC LIMIT ?
            """, (max(1, min(limit, 100)),)).fetchall()
        return [self._public_deployment(row) for row in rows]

    @staticmethod
    def _public_artifact(row: sqlite3.Row) -> dict[str, Any]:
        return {
            "artifact_id": row["id"],
            "project_name": row["project_name"],
            "source_digest": row["source_digest"],
            "artifact_name": row["artifact_name"],
            "artifact_sha256": row["artifact_sha256"],
            "manifest": json.loads(row["manifest_json"]),
            "file_count": row["file_count"],
            "source_bytes": row["source_bytes"],
            "artifact_bytes": row["artifact_bytes"],
            "status": row["status"],
            "created_at": row["created_at"],
        }

    @staticmethod
    def _public_deployment(row: sqlite3.Row) -> dict[str, Any]:
        value = {
            "deployment_id": row["id"],
            "artifact_id": row["artifact_id"],
            "environment_name": row["environment_name"],
            "target_kind": row["target_kind"],
            "reported_outcome": row["reported_outcome"],
            "verification_status": row["verification_status"],
            "external_action_executed": bool(row["external_action_executed"]),
            "created_at": row["created_at"],
        }
        if "project_name" in row.keys():
            value["project_name"] = row["project_name"]
            value["artifact_sha256"] = row["artifact_sha256"]
        return value
