from __future__ import annotations

import ast
import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
from pathlib import Path, PurePosixPath
from typing import Any

from sparkle.ai_system_plan import (
    AISystemImplementationPlanner,
    AISystemImplementationPlanStore,
)
from sparkle.builders import WorkspaceManager
from sparkle.config import data_root
from sparkle.orchestrator import Orchestrator
from sparkle.storage import SQLiteStore, utc_now
from sparkle.trace import TraceStore


def _digest(value: str) -> bool:
    return (
        isinstance(value, str)
        and len(value) == 64
        and all(character in "0123456789abcdef" for character in value)
    )


class ProviderDisclosureStore(SQLiteStore):
    """Provider metadata kept separately from generated candidate source."""

    MAX_RECORDS = 1_000

    def __init__(self, path: Path | None = None):
        super().__init__(
            path or data_root() / "data_environment" / "source_provider_disclosures.sqlite3"
        )
        self.initialize()

    def initialize(self) -> None:
        with self.connect() as connection:
            connection.execute("""
                CREATE TABLE IF NOT EXISTS source_provider_disclosures (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    plan_id INTEGER NOT NULL,
                    plan_sha256 TEXT NOT NULL,
                    provider TEXT NOT NULL,
                    model TEXT NOT NULL,
                    model_identifier TEXT NOT NULL,
                    generation_task TEXT NOT NULL,
                    status TEXT NOT NULL,
                    approved_at TEXT,
                    candidate_id INTEGER,
                    generated_files_json TEXT NOT NULL DEFAULT '[]',
                    generation_status TEXT NOT NULL,
                    generated_at TEXT,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                )
            """)

    @staticmethod
    def _label(value: Any, field: str) -> str:
        if not isinstance(value, str) or not value or len(value) > 128:
            raise ValueError(f"Provider disclosure {field} is invalid")
        return value

    def create(
        self,
        *,
        plan_id: int,
        plan_sha256: str,
        provider: str,
        model: str,
        model_identifier: str,
        generation_task: str,
    ) -> int:
        if not isinstance(plan_id, int) or isinstance(plan_id, bool) or plan_id < 1:
            raise ValueError("Provider disclosure plan ID is invalid")
        if not _digest(plan_sha256):
            raise ValueError("Provider disclosure plan digest is invalid")
        if (
            not isinstance(generation_task, str)
            or not 10 <= len(generation_task.strip()) <= 500
        ):
            raise ValueError("Provider disclosure generation task is invalid")
        now = utc_now()
        with self.connect() as connection:
            cursor = connection.execute("""
                INSERT INTO source_provider_disclosures(
                    plan_id, plan_sha256, provider, model, model_identifier,
                    generation_task, status, generation_status, created_at, updated_at
                ) VALUES(?,?,?,?,?,?,'disclosure_pending','not_started',?,?)
            """, (
                plan_id,
                plan_sha256,
                self._label(provider, "provider"),
                self._label(model, "model"),
                self._label(model_identifier, "model identifier"),
                generation_task.strip(),
                now,
                now,
            ))
            connection.execute("""
                DELETE FROM source_provider_disclosures WHERE id NOT IN (
                    SELECT id FROM source_provider_disclosures
                    ORDER BY id DESC LIMIT ?
                )
            """, (self.MAX_RECORDS,))
        return int(cursor.lastrowid)

    def approve(self, disclosure_id: int, *, approved: bool) -> dict[str, Any]:
        if approved is not True:
            raise ValueError("Provider disclosure requires explicit approval")
        now = utc_now()
        with self.connect() as connection:
            cursor = connection.execute("""
                UPDATE source_provider_disclosures
                SET status='disclosure_approved', approved_at=?, updated_at=?
                WHERE id=? AND status='disclosure_pending'
            """, (now, now, disclosure_id))
        if cursor.rowcount != 1:
            raise ValueError("Provider disclosure is not pending approval")
        return self.get(disclosure_id)

    def bind_candidate(self, disclosure_id: int, candidate_id: int) -> None:
        with self.connect() as connection:
            cursor = connection.execute("""
                UPDATE source_provider_disclosures
                SET candidate_id=?, generation_status='generating', updated_at=?
                WHERE id=? AND status='disclosure_approved'
                  AND generation_status='not_started' AND candidate_id IS NULL
            """, (candidate_id, utc_now(), disclosure_id))
        if cursor.rowcount != 1:
            raise ValueError("Provider disclosure cannot start generation")

    def finish_generation(
        self,
        disclosure_id: int,
        *,
        status: str,
        files: list[str] | None = None,
    ) -> None:
        if status not in {"generated", "failed"}:
            raise ValueError("Provider disclosure generation status is invalid")
        values = files or []
        if (
            not isinstance(values, list)
            or len(values) > 20
            or any(not isinstance(item, str) or len(item) > 240 for item in values)
        ):
            raise ValueError("Provider disclosure generated files are invalid")
        now = utc_now()
        with self.connect() as connection:
            cursor = connection.execute("""
                UPDATE source_provider_disclosures
                SET generation_status=?, generated_files_json=?, generated_at=?,
                    updated_at=?
                WHERE id=? AND generation_status='generating'
            """, (
                status,
                json.dumps(values, separators=(",", ":")),
                now,
                now,
                disclosure_id,
            ))
        if cursor.rowcount != 1:
            raise ValueError("Provider disclosure generation transition failed")

    def get(self, disclosure_id: int) -> dict[str, Any]:
        if (
            not isinstance(disclosure_id, int)
            or isinstance(disclosure_id, bool)
            or disclosure_id < 1
        ):
            raise ValueError("Provider disclosure ID is invalid")
        with self.connect() as connection:
            row = connection.execute(
                "SELECT * FROM source_provider_disclosures WHERE id=?",
                (disclosure_id,),
            ).fetchone()
        if row is None:
            raise KeyError("Provider disclosure does not exist")
        return self._public(row)

    def list(self, *, limit: int = 50) -> list[dict[str, Any]]:
        with self.connect() as connection:
            rows = connection.execute("""
                SELECT * FROM source_provider_disclosures ORDER BY id DESC LIMIT ?
            """, (max(1, min(limit, 100)),)).fetchall()
        return [self._public(row) for row in rows]

    @staticmethod
    def _public(row: Any) -> dict[str, Any]:
        return {
            "disclosure_id": row["id"],
            "plan_id": row["plan_id"],
            "plan_sha256": row["plan_sha256"],
            "provider": row["provider"],
            "model": row["model"],
            "model_identifier": row["model_identifier"],
            "generation_task": row["generation_task"],
            "status": row["status"],
            "approved_at": row["approved_at"],
            "candidate_id": row["candidate_id"],
            "files_generated": json.loads(row["generated_files_json"]),
            "generation_status": row["generation_status"],
            "generated_at": row["generated_at"],
            "credentials_included": False,
            "created_at": row["created_at"],
            "updated_at": row["updated_at"],
        }


class SourceCandidateStore(SQLiteStore):
    MAX_RECORDS = 1_000
    STATES = {
        "generating",
        "generation_failed",
        "generated_human_review_required",
        "reviewed",
        "review_rejected",
        "static_verification_failed",
        "statically_verified",
        "approved",
    }

    def __init__(self, path: Path | None = None):
        super().__init__(
            path or data_root() / "data_environment" / "source_candidates.sqlite3"
        )
        self.initialize()

    def initialize(self) -> None:
        with self.connect() as connection:
            connection.execute("""
                CREATE TABLE IF NOT EXISTS source_candidates (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    disclosure_id INTEGER NOT NULL,
                    plan_id INTEGER NOT NULL,
                    system_name TEXT NOT NULL,
                    plan_sha256 TEXT NOT NULL,
                    status TEXT NOT NULL,
                    files_json TEXT NOT NULL DEFAULT '[]',
                    candidate_sha256 TEXT,
                    trace_id TEXT,
                    review_notes_sha256 TEXT,
                    reviewed_at TEXT,
                    verification_json TEXT,
                    verified_at TEXT,
                    approved_at TEXT,
                    error_type TEXT,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                )
            """)
            connection.execute("""
                CREATE TABLE IF NOT EXISTS source_candidate_events (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    candidate_id INTEGER NOT NULL,
                    state TEXT NOT NULL,
                    trace_id TEXT,
                    created_at TEXT NOT NULL
                )
            """)

    def begin(
        self,
        *,
        disclosure_id: int,
        plan_id: int,
        system_name: str,
        plan_sha256: str,
    ) -> int:
        if WorkspaceManager.NAME_PATTERN.fullmatch(system_name) is None:
            raise ValueError("Source candidate system name is invalid")
        if not _digest(plan_sha256):
            raise ValueError("Source candidate plan digest is invalid")
        now = utc_now()
        with self.connect() as connection:
            cursor = connection.execute("""
                INSERT INTO source_candidates(
                    disclosure_id, plan_id, system_name, plan_sha256, status,
                    created_at, updated_at
                ) VALUES(?,?,?,?,'generating',?,?)
            """, (
                disclosure_id, plan_id, system_name, plan_sha256, now, now,
            ))
            candidate_id = int(cursor.lastrowid)
            connection.execute("""
                INSERT INTO source_candidate_events(candidate_id,state,created_at)
                VALUES(?,'generating',?)
            """, (candidate_id, now))
            connection.execute("""
                DELETE FROM source_candidates WHERE id NOT IN (
                    SELECT id FROM source_candidates ORDER BY id DESC LIMIT ?
                )
            """, (self.MAX_RECORDS,))
            connection.execute("""
                DELETE FROM source_candidate_events WHERE candidate_id NOT IN (
                    SELECT id FROM source_candidates
                )
            """)
        return candidate_id

    def mark_generated(
        self,
        candidate_id: int,
        *,
        files: list[dict[str, Any]],
        candidate_sha256: str,
        trace_id: str,
    ) -> dict[str, Any]:
        if not _digest(candidate_sha256):
            raise ValueError("Source candidate digest is invalid")
        now = utc_now()
        with self.connect() as connection:
            cursor = connection.execute("""
                UPDATE source_candidates
                SET status='generated_human_review_required', files_json=?,
                    candidate_sha256=?, trace_id=?, updated_at=?
                WHERE id=? AND status='generating'
            """, (
                json.dumps(files, separators=(",", ":"), sort_keys=True),
                candidate_sha256, trace_id, now, candidate_id,
            ))
            if cursor.rowcount == 1:
                connection.execute("""
                    INSERT INTO source_candidate_events(
                        candidate_id,state,trace_id,created_at
                    ) VALUES(?,'generated_human_review_required',?,?)
                """, (candidate_id, trace_id, now))
        if cursor.rowcount != 1:
            raise ValueError("Source candidate generation transition failed")
        return self.get(candidate_id)

    def fail_generation(self, candidate_id: int, error_type: str) -> None:
        now = utc_now()
        with self.connect() as connection:
            cursor = connection.execute("""
                UPDATE source_candidates
                SET status='generation_failed', error_type=?, updated_at=?
                WHERE id=? AND status='generating'
            """, (error_type[:128], now, candidate_id))
            if cursor.rowcount == 1:
                connection.execute("""
                    INSERT INTO source_candidate_events(candidate_id,state,created_at)
                    VALUES(?,'generation_failed',?)
                """, (candidate_id, now))

    def review(
        self,
        candidate_id: int,
        *,
        decision: str,
        notes_sha256: str,
    ) -> dict[str, Any]:
        if decision not in {"accept", "reject"} or not _digest(notes_sha256):
            raise ValueError("Source candidate review is invalid")
        state = "reviewed" if decision == "accept" else "review_rejected"
        now = utc_now()
        with self.connect() as connection:
            cursor = connection.execute("""
                UPDATE source_candidates
                SET status=?, review_notes_sha256=?, reviewed_at=?, updated_at=?
                WHERE id=? AND status='generated_human_review_required'
            """, (state, notes_sha256, now, now, candidate_id))
            if cursor.rowcount == 1:
                connection.execute("""
                    INSERT INTO source_candidate_events(
                        candidate_id,state,trace_id,created_at
                    ) SELECT ?,?,trace_id,? FROM source_candidates WHERE id=?
                """, (candidate_id, state, now, candidate_id))
        if cursor.rowcount != 1:
            raise ValueError("Source candidate is not awaiting human review")
        return self.get(candidate_id)

    def record_verification(
        self,
        candidate_id: int,
        verification: dict[str, Any],
    ) -> dict[str, Any]:
        state = (
            "statically_verified"
            if verification.get("status") == "passed"
            else "static_verification_failed"
        )
        now = utc_now()
        with self.connect() as connection:
            cursor = connection.execute("""
                UPDATE source_candidates
                SET status=?, verification_json=?, verified_at=?, updated_at=?
                WHERE id=? AND status='reviewed'
            """, (
                state,
                json.dumps(verification, separators=(",", ":"), sort_keys=True),
                now, now, candidate_id,
            ))
            if cursor.rowcount == 1:
                connection.execute("""
                    INSERT INTO source_candidate_events(
                        candidate_id,state,trace_id,created_at
                    ) SELECT ?,?,trace_id,? FROM source_candidates WHERE id=?
                """, (candidate_id, state, now, candidate_id))
        if cursor.rowcount != 1:
            raise ValueError("Only a reviewed source candidate can be verified")
        return self.get(candidate_id)

    def approve(self, candidate_id: int, *, approved: bool) -> dict[str, Any]:
        if approved is not True:
            raise ValueError("Source candidate approval requires explicit approval")
        now = utc_now()
        with self.connect() as connection:
            cursor = connection.execute("""
                UPDATE source_candidates
                SET status='approved', approved_at=?, updated_at=?
                WHERE id=? AND status='statically_verified'
            """, (now, now, candidate_id))
            if cursor.rowcount == 1:
                connection.execute("""
                    INSERT INTO source_candidate_events(
                        candidate_id,state,trace_id,created_at
                    ) SELECT ?,'approved',trace_id,? FROM source_candidates WHERE id=?
                """, (candidate_id, now, candidate_id))
        if cursor.rowcount != 1:
            raise ValueError(
                "Only a statically verified source candidate can be approved"
            )
        return self.get(candidate_id)

    def get(self, candidate_id: int) -> dict[str, Any]:
        if not isinstance(candidate_id, int) or isinstance(candidate_id, bool) or candidate_id < 1:
            raise ValueError("Source candidate ID is invalid")
        with self.connect() as connection:
            row = connection.execute(
                "SELECT * FROM source_candidates WHERE id=?", (candidate_id,),
            ).fetchone()
            events = connection.execute("""
                SELECT state, trace_id, created_at FROM source_candidate_events
                WHERE candidate_id=? ORDER BY id
            """, (candidate_id,)).fetchall()
        if row is None:
            raise KeyError("Source candidate does not exist")
        value = self._public(row)
        value["lifecycle"] = [dict(event) for event in events]
        return value

    def list(self, *, limit: int = 50) -> list[dict[str, Any]]:
        with self.connect() as connection:
            rows = connection.execute("""
                SELECT * FROM source_candidates ORDER BY id DESC LIMIT ?
            """, (max(1, min(limit, 100)),)).fetchall()
        return [self._public(row) for row in rows]

    @staticmethod
    def _public(row: Any) -> dict[str, Any]:
        verification = (
            json.loads(row["verification_json"])
            if row["verification_json"] else None
        )
        return {
            "candidate_id": row["id"],
            "disclosure_id": row["disclosure_id"],
            "plan_id": row["plan_id"],
            "system_name": row["system_name"],
            "plan_sha256": row["plan_sha256"],
            "status": row["status"],
            "files": json.loads(row["files_json"]),
            "candidate_sha256": row["candidate_sha256"],
            "trace_id": row["trace_id"],
            "review_notes_sha256": row["review_notes_sha256"],
            "reviewed_at": row["reviewed_at"],
            "static_verification": verification,
            "verified_at": row["verified_at"],
            "approved_at": row["approved_at"],
            "error_type": row["error_type"],
            "human_review_completed": row["reviewed_at"] is not None,
            "static_verification_executed": verification is not None,
            "runtime_tests_executed": False,
            "external_worker_called": False,
            "production_source_modified": False,
            "external_deployment_executed": False,
            "created_at": row["created_at"],
            "updated_at": row["updated_at"],
        }


class SourceCandidateWorkspace:
    MANIFEST = "SPARKLE_SOURCE_CANDIDATE.json"
    MAX_FILES = 20
    MAX_FILE_BYTES = 64_000
    MAX_TOTAL_BYTES = 256_000

    def __init__(self, root: Path | None = None):
        self.root = (
            root or data_root() / "candidate_environment" / "source_candidates"
        ).resolve()
        self.root.mkdir(parents=True, exist_ok=True)

    @staticmethod
    def name(candidate_id: int) -> str:
        return f"candidate-{candidate_id:06d}"

    def _root(self, candidate_id: int, *, require: bool = True) -> Path:
        candidate = self.root / self.name(candidate_id)
        if candidate.is_symlink():
            raise ValueError("Source candidate workspace cannot be a symlink")
        resolved = candidate.resolve()
        if resolved.parent != self.root:
            raise ValueError("Source candidate workspace escapes its root")
        if require and not resolved.is_dir():
            raise ValueError("Source candidate workspace does not exist")
        return resolved

    @staticmethod
    def _path(value: str) -> PurePosixPath:
        return WorkspaceManager._validate_relative_path(value)

    def write(
        self,
        *,
        candidate_id: int,
        plan_id: int,
        plan_sha256: str,
        files: list[dict[str, str]],
    ) -> tuple[str, list[dict[str, Any]], str]:
        if not 1 <= len(files) <= self.MAX_FILES:
            raise ValueError("Source candidate must contain 1-20 files")
        root = self._root(candidate_id, require=False)
        if root.exists():
            raise FileExistsError("Source candidate workspace already exists")
        metadata: list[dict[str, Any]] = []
        normalized: list[tuple[PurePosixPath, str]] = []
        total = 0
        seen: set[str] = set()
        for item in files:
            path = self._path(item["path"])
            relative = path.as_posix()
            content = item["content"]
            size = len(content.encode("utf-8"))
            if relative == self.MANIFEST or relative in seen:
                raise ValueError("Source candidate paths must be unique and non-reserved")
            if not 1 <= size <= self.MAX_FILE_BYTES:
                raise ValueError("Source candidate file size is invalid")
            total += size
            if total > self.MAX_TOTAL_BYTES:
                raise ValueError("Source candidate exceeds the total byte limit")
            seen.add(relative)
            normalized.append((path, content))
            metadata.append({
                "path": relative,
                "bytes": size,
                "sha256": hashlib.sha256(content.encode("utf-8")).hexdigest(),
            })
        candidate_sha256 = hashlib.sha256(
            json.dumps(metadata, separators=(",", ":"), sort_keys=True).encode("utf-8")
        ).hexdigest()
        manifest = {
            "protocol_version": AISystemSourceCandidateService.PROTOCOL,
            "candidate_id": candidate_id,
            "plan_id": plan_id,
            "plan_sha256": plan_sha256,
            "status": "generated_human_review_required",
            "files": metadata,
            "candidate_sha256": candidate_sha256,
            "runtime_tests_executed": False,
            "external_deployment_executed": False,
        }
        root.mkdir(mode=0o700)
        try:
            for path, content in normalized:
                target = root / Path(*path.parts)
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_text(content, encoding="utf-8")
                target.chmod(0o400)
            target = root / self.MANIFEST
            target.write_text(
                json.dumps(
                    manifest, ensure_ascii=False, separators=(",", ":"),
                    sort_keys=True,
                ) + "\n",
                encoding="utf-8",
            )
            target.chmod(0o400)
        except Exception:
            shutil.rmtree(root, ignore_errors=True)
            raise
        return str(root), metadata, candidate_sha256

    def read(self, candidate_id: int, path: str) -> str:
        root = self._root(candidate_id)
        relative = self._path(path)
        target = root / Path(*relative.parts)
        current = target
        while current != root:
            if current.is_symlink():
                raise ValueError("Source candidate path contains a symlink")
            current = current.parent
        resolved = target.resolve()
        if root not in resolved.parents or not resolved.is_file():
            raise ValueError("Source candidate file is missing or outside its workspace")
        if resolved.stat().st_size > self.MAX_FILE_BYTES:
            raise ValueError("Source candidate file exceeds the read limit")
        return resolved.read_text(encoding="utf-8")

    def load(self, candidate_id: int) -> tuple[dict[str, Any], dict[str, str]]:
        root = self._root(candidate_id)
        manifest = json.loads(self.read(candidate_id, self.MANIFEST))
        actual: dict[str, str] = {}
        for path in sorted(root.rglob("*")):
            if path.is_symlink():
                raise ValueError("Source candidate workspace contains a symlink")
            if path.is_file():
                relative = path.relative_to(root).as_posix()
                if relative != self.MANIFEST:
                    actual[relative] = self.read(candidate_id, relative)
        return manifest, actual

    def discard(self, candidate_id: int) -> None:
        """Remove only one failed candidate workspace, never production source."""
        root = self._root(candidate_id, require=False)
        if root.exists():
            shutil.rmtree(root)


class SourceCandidateStaticVerifier:
    """Non-executing candidate validation; no import or candidate code execution."""

    FORBIDDEN_MODULES = {"subprocess", "socket", "requests", "httpx", "pickle"}
    FORBIDDEN_CALLS = {"eval", "exec", "__import__"}
    CREDENTIAL_PATTERN = re.compile(
        r"(?:sk-[A-Za-z0-9_-]{16,}|ghp_[A-Za-z0-9]{20,}|"
        r"AKIA[0-9A-Z]{16}|-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----)"
    )

    def __init__(self, workspace: SourceCandidateWorkspace):
        self.workspace = workspace
        self.node_binary = shutil.which("node")

    @staticmethod
    def _check(kind: str, path: str, passed: bool, detail: str) -> dict[str, str]:
        return {
            "type": kind,
            "path": path,
            "status": "passed" if passed else "failed",
            "detail": detail[:500],
        }

    def verify(
        self,
        candidate: dict[str, Any],
        plan: dict[str, Any],
    ) -> dict[str, Any]:
        checks: list[dict[str, str]] = []
        try:
            manifest, files = self.workspace.load(candidate["candidate_id"])
        except Exception as exc:
            return {
                "status": "failed",
                "checks": [self._check(
                    "candidate_isolation", "", False, type(exc).__name__,
                )],
                "runtime_tests_executed": False,
            }
        expected_manifest_fields = {
            "protocol_version", "candidate_id", "plan_id", "plan_sha256",
            "status", "files", "candidate_sha256", "runtime_tests_executed",
            "external_deployment_executed",
        }
        manifest_ok = (
            isinstance(manifest, dict)
            and set(manifest) == expected_manifest_fields
            and manifest.get("protocol_version") == AISystemSourceCandidateService.PROTOCOL
            and manifest.get("candidate_id") == candidate["candidate_id"]
            and manifest.get("plan_id") == candidate["plan_id"]
            and manifest.get("plan_sha256") == candidate["plan_sha256"]
            and manifest.get("candidate_sha256") == candidate["candidate_sha256"]
            and manifest.get("status") == "generated_human_review_required"
            and manifest.get("runtime_tests_executed") is False
            and manifest.get("external_deployment_executed") is False
        )
        checks.append(self._check(
            "manifest_validation", SourceCandidateWorkspace.MANIFEST,
            manifest_ok, "Candidate manifest matches the immutable protocol",
        ))
        metadata = manifest.get("files", []) if isinstance(manifest, dict) else []
        metadata_paths = {
            item.get("path") for item in metadata if isinstance(item, dict)
        }
        paths_ok = (
            isinstance(metadata, list)
            and len(metadata_paths) == len(metadata)
            and metadata == candidate["files"]
            and metadata_paths == set(files)
            and metadata_paths == {
            item["path"] for item in candidate["files"]
            }
        )
        planned_paths = {item["path"] for item in plan["proposed_source_files"]}
        paths_ok = paths_ok and set(files) <= planned_paths
        checks.append(self._check(
            "path_validation", "", paths_ok,
            "Candidate files are confined to paths declared by the approved plan",
        ))
        integrity_ok = True
        for item in metadata if isinstance(metadata, list) else []:
            if not isinstance(item, dict) or set(item) != {"path", "bytes", "sha256"}:
                integrity_ok = False
                continue
            content = files.get(item["path"], "")
            integrity_ok = integrity_ok and (
                len(content.encode("utf-8")) == item["bytes"]
                and hashlib.sha256(content.encode("utf-8")).hexdigest()
                == item["sha256"]
            )
        checks.append(self._check(
            "integrity_validation", "", integrity_ok,
            "Candidate file digests and byte counts match the immutable manifest",
        ))
        computed_candidate_digest = hashlib.sha256(
            json.dumps(
                metadata, separators=(",", ":"), sort_keys=True,
            ).encode("utf-8")
        ).hexdigest()
        checks.append(self._check(
            "candidate_digest_validation", "",
            integrity_ok
            and computed_candidate_digest == candidate["candidate_sha256"]
            and computed_candidate_digest == manifest.get("candidate_sha256"),
            "Candidate digest matches stored evidence and the immutable manifest",
        ))

        package_roots = {
            PurePosixPath(path).parts[1]
            for path in planned_paths
            if len(PurePosixPath(path).parts) >= 3
            and PurePosixPath(path).parts[0] == "src"
        }
        local_modules: set[str] = set()
        for candidate_path in files:
            parts = PurePosixPath(candidate_path).parts
            if len(parts) >= 3 and parts[0] == "src" and parts[-1].endswith(".py"):
                module_parts = list(parts[1:])
                module_parts[-1] = module_parts[-1][:-3]
                if module_parts[-1] == "__init__":
                    module_parts.pop()
                if module_parts:
                    local_modules.add(".".join(module_parts))
        for path, content in files.items():
            formatting_ok = (
                content.endswith("\n")
                and "\t" not in content
                and all(
                    line == line.rstrip() and len(line) <= 120
                    for line in content.splitlines()
                )
            )
            checks.append(self._check(
                "formatting_quality", path, formatting_ok,
                "UTF-8 text has a final newline, no tabs/trailing spaces, and bounded lines",
            ))
            credential_free = self.CREDENTIAL_PATTERN.search(content) is None
            checks.append(self._check(
                "credential_pattern_scan", path, credential_free,
                "No known live credential or private-key pattern was found",
            ))
            suffix = PurePosixPath(path).suffix.lower()
            if suffix == ".py":
                try:
                    tree = ast.parse(content, filename=path)
                    syntax_ok = True
                except (SyntaxError, ValueError, RecursionError):
                    tree = None
                    syntax_ok = False
                checks.append(self._check(
                    "python_syntax", path, syntax_ok,
                    "Python parsed without executing candidate code",
                ))
                if tree is None:
                    continue
                imports: set[str] = set()
                security_ok = True
                references_ok = True
                for node in ast.walk(tree):
                    if isinstance(node, ast.Import):
                        for alias in node.names:
                            imports.add(alias.name.split(".")[0])
                            if alias.name.split(".")[0] in package_roots:
                                references_ok = references_ok and (
                                    alias.name in local_modules
                                    or any(
                                        module.startswith(alias.name + ".")
                                        for module in local_modules
                                    )
                                )
                    elif isinstance(node, ast.ImportFrom):
                        if node.level == 0 and node.module:
                            imports.add(node.module.split(".")[0])
                            if node.module.split(".")[0] in package_roots:
                                references_ok = references_ok and (
                                    node.module in local_modules
                                    or any(
                                        module.startswith(node.module + ".")
                                        for module in local_modules
                                    )
                                )
                        elif node.level > 0:
                            parts = list(PurePosixPath(path).parts[1:])
                            parts[-1] = parts[-1][:-3]
                            if parts[-1] != "__init__":
                                parts.pop()
                            remove = node.level - 1
                            base = parts[:-remove] if remove else parts
                            target = ".".join([
                                *base,
                                *([] if not node.module else node.module.split(".")),
                            ])
                            references_ok = references_ok and bool(target) and (
                                target in local_modules
                                or any(
                                    module.startswith(target + ".")
                                    for module in local_modules
                                )
                            )
                        if any(alias.name == "*" for alias in node.names):
                            references_ok = False
                    elif isinstance(node, ast.Call):
                        if isinstance(node.func, ast.Name) and node.func.id in self.FORBIDDEN_CALLS:
                            security_ok = False
                        if (
                            isinstance(node.func, ast.Attribute)
                            and isinstance(node.func.value, ast.Name)
                            and node.func.value.id == "os"
                            and node.func.attr in {"system", "popen"}
                        ):
                            security_ok = False
                        if any(
                            keyword.arg == "shell"
                            and isinstance(keyword.value, ast.Constant)
                            and keyword.value.value is True
                            for keyword in node.keywords
                        ):
                            security_ok = False
                external = imports - set(sys.stdlib_module_names) - package_roots - {"sparkle"}
                dependency_ok = not external
                security_ok = security_ok and not (imports & self.FORBIDDEN_MODULES)
                checks.append(self._check(
                    "import_reference", path, references_ok,
                    "Imports are explicit and statically inspectable",
                ))
                checks.append(self._check(
                    "dependency_consistency", path, dependency_ok,
                    "Imports use only the standard library, SPARKLE, or candidate-local modules",
                ))
                checks.append(self._check(
                    "security_pattern_scan", path, security_ok,
                    "No forbidden dynamic execution, shell, network, or unsafe serialization pattern was found",
                ))
            elif suffix == ".json":
                try:
                    value = json.loads(content)
                    config_ok = isinstance(value, (dict, list))
                except (json.JSONDecodeError, UnicodeDecodeError, RecursionError):
                    config_ok = False
                checks.append(self._check(
                    "configuration_validation", path, config_ok,
                    "JSON configuration parsed without execution",
                ))
            elif suffix in {".js", ".mjs", ".cjs"}:
                if not self.node_binary:
                    passed, detail = False, "Node.js is unavailable"
                else:
                    completed = subprocess.run(
                        [self.node_binary, "--check", "--", path],
                        cwd=self.workspace._root(candidate["candidate_id"]),
                        env={
                            "PATH": os.path.dirname(self.node_binary),
                            "LANG": "C.UTF-8", "LC_ALL": "C.UTF-8",
                            "NODE_OPTIONS": "--no-warnings",
                        },
                        capture_output=True, text=True, timeout=5, check=False,
                    )
                    passed = completed.returncode == 0
                    detail = "JavaScript syntax check passed" if passed else "JavaScript syntax check failed"
                checks.append(self._check("javascript_syntax", path, passed, detail))
            else:
                checks.append(self._check(
                    "language_static_analysis", path, False,
                    "Candidate file type has no supported static analyzer",
                ))
        passed = sum(item["status"] == "passed" for item in checks)
        return {
            "status": "passed" if passed == len(checks) else "failed",
            "passed": passed,
            "failed": len(checks) - passed,
            "checks": checks,
            "runtime_tests_executed": False,
            "external_worker_called": False,
        }


class AISystemSourceCandidateService:
    PROTOCOL = "SPARKLE-AI-SYSTEM-SOURCE-CANDIDATE/1"
    MAX_RESPONSE_CHARS = 300_000
    SENSITIVE_TASK = re.compile(
        r"(?:sk-[A-Za-z0-9_-]{16,}|ghp_[A-Za-z0-9]{20,}|"
        r"AKIA[0-9A-Z]{16}|-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----)"
    )

    def __init__(
        self,
        planner: AISystemImplementationPlanner,
        plans: AISystemImplementationPlanStore,
        orchestrator: Orchestrator,
        traces: TraceStore,
        disclosures: ProviderDisclosureStore,
        candidates: SourceCandidateStore,
        workspace: SourceCandidateWorkspace,
    ):
        self.planner = planner
        self.plans = plans
        self.orchestrator = orchestrator
        self.traces = traces
        self.disclosures = disclosures
        self.candidates = candidates
        self.workspace = workspace
        self.verifier = SourceCandidateStaticVerifier(workspace)

    @staticmethod
    def _unique_object(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
        value: dict[str, Any] = {}
        for key, item in pairs:
            if key in value:
                raise ValueError(f"Source candidate JSON contains duplicate key: {key}")
            value[key] = item
        return value

    def _approved_plan(
        self, plan_id: int, requirements: dict[str, Any],
    ) -> tuple[dict[str, Any], dict[str, Any]]:
        record = self.plans.get(plan_id)
        if record["review_status"] != "approved_for_generation":
            raise ValueError("Implementation plan is not approved for source generation")
        plan = self.planner.prepare(requirements)
        if plan["plan_sha256"] != record["plan_sha256"]:
            raise ValueError("Implementation plan and requirements do not match")
        return record, plan

    def review_plan(self, plan_id: int, *, approved: bool) -> dict[str, Any]:
        return self.plans.approve_for_generation(plan_id, approved=approved)

    def prepare_disclosure(
        self,
        plan_id: int,
        requirements: dict[str, Any],
        *,
        generation_task: str,
    ) -> dict[str, Any]:
        record, _ = self._approved_plan(plan_id, requirements)
        if (
            not isinstance(generation_task, str)
            or self.SENSITIVE_TASK.search(generation_task)
        ):
            raise ValueError("Generation task contains a credential-like value")
        spec = self.orchestrator.agents.get("application_builder")
        model_identifier, adapter = self.orchestrator.models.select_with_record(
            spec.capability, modalities={"text"},
        )
        disclosure_id = self.disclosures.create(
            plan_id=plan_id,
            plan_sha256=record["plan_sha256"],
            provider=adapter.provider,
            model=adapter.model_id,
            model_identifier=model_identifier,
            generation_task=generation_task,
        )
        return self.disclosures.get(disclosure_id)

    def approve_disclosure(
        self, disclosure_id: int, *, approved: bool,
    ) -> dict[str, Any]:
        return self.disclosures.approve(disclosure_id, approved=approved)

    @staticmethod
    def _prompt(plan: dict[str, Any], task: str) -> str:
        return (
            "Generate a bounded source candidate for the approved implementation "
            "plan. Return exactly one JSON object with only protocol_version, "
            "plan_sha256, and files. protocol_version must be "
            "SPARKLE-AI-SYSTEM-SOURCE-CANDIDATE/1. files must contain 1-20 "
            "objects with exactly path and content. Every path must be one of "
            "proposed_source_files. Do not return Markdown, credentials, package "
            "installation, shell commands, deployment actions, or claims that code "
            "was reviewed, tested, verified, approved, or deployed.\n\nPlan:\n"
            + json.dumps(plan, ensure_ascii=False, separators=(",", ":"), sort_keys=True)
            + "\n\nGeneration task:\n"
            + task
        )

    def _files(self, response: str, plan: dict[str, Any]) -> list[dict[str, str]]:
        if len(response) > self.MAX_RESPONSE_CHARS:
            raise ValueError("Source candidate response exceeds 300000 characters")
        try:
            value = json.loads(response, object_pairs_hook=self._unique_object)
        except json.JSONDecodeError as exc:
            raise ValueError("Source candidate response is not exact JSON") from exc
        if not isinstance(value, dict) or set(value) != {
            "protocol_version", "plan_sha256", "files",
        }:
            raise ValueError("Source candidate response fields are invalid")
        if value["protocol_version"] != self.PROTOCOL:
            raise ValueError("Source candidate protocol is invalid")
        if value["plan_sha256"] != plan["plan_sha256"]:
            raise ValueError("Source candidate plan digest does not match")
        files = value["files"]
        if not isinstance(files, list) or not 1 <= len(files) <= 20:
            raise ValueError("Source candidate files must contain 1-20 entries")
        planned = {item["path"] for item in plan["proposed_source_files"]}
        result: list[dict[str, str]] = []
        seen: set[str] = set()
        total = 0
        for item in files:
            if not isinstance(item, dict) or set(item) != {"path", "content"}:
                raise ValueError("Source candidate file fields are invalid")
            path, content = item["path"], item["content"]
            if not isinstance(path, str) or path not in planned or path in seen:
                raise ValueError("Source candidate path is not declared by the plan")
            if not isinstance(content, str):
                raise ValueError("Source candidate content must be text")
            size = len(content.encode("utf-8"))
            if not 1 <= size <= SourceCandidateWorkspace.MAX_FILE_BYTES:
                raise ValueError("Source candidate file size is invalid")
            total += size
            if total > SourceCandidateWorkspace.MAX_TOTAL_BYTES:
                raise ValueError("Source candidate total size is invalid")
            seen.add(path)
            result.append({"path": path, "content": content})
        return result

    def generate(
        self,
        plan_id: int,
        requirements: dict[str, Any],
        disclosure_id: int,
        *,
        approved: bool,
    ) -> dict[str, Any]:
        if approved is not True:
            raise ValueError("Source candidate generation requires explicit approval")
        plan_record, plan = self._approved_plan(plan_id, requirements)
        disclosure = self.disclosures.get(disclosure_id)
        if (
            disclosure["status"] != "disclosure_approved"
            or disclosure["generation_status"] != "not_started"
            or disclosure["plan_id"] != plan_id
            or disclosure["plan_sha256"] != plan_record["plan_sha256"]
        ):
            raise ValueError("Approved provider disclosure does not match the plan")
        spec = self.orchestrator.agents.get("application_builder")
        model_identifier, adapter = self.orchestrator.models.select_with_record(
            spec.capability, modalities={"text"},
        )
        if (
            disclosure["provider"] != adapter.provider
            or disclosure["model"] != adapter.model_id
            or disclosure["model_identifier"] != model_identifier
        ):
            raise ValueError("Current provider metadata differs from the approved disclosure")
        candidate_id = self.candidates.begin(
            disclosure_id=disclosure_id,
            plan_id=plan_id,
            system_name=plan["system_name"],
            plan_sha256=plan["plan_sha256"],
        )
        self.disclosures.bind_candidate(disclosure_id, candidate_id)
        try:
            result = self.orchestrator.run(
                self._prompt(plan, disclosure["generation_task"]),
                agent_name="application_builder",
                input_source="ai_system_source_candidate",
                execution_profile="evaluation",
            )
            if not result.provider or not result.model:
                raise ValueError("Generated source candidate is missing provider metadata")
            if (
                result.provider != disclosure["provider"]
                or result.model != disclosure["model"]
            ):
                raise ValueError("Generated source candidate provider metadata is incorrect")
            files = self._files(result.text, plan)
            workspace, metadata, digest = self.workspace.write(
                candidate_id=candidate_id,
                plan_id=plan_id,
                plan_sha256=plan["plan_sha256"],
                files=files,
            )
            candidate = self.candidates.mark_generated(
                candidate_id,
                files=metadata,
                candidate_sha256=digest,
                trace_id=result.trace_id,
            )
            self.disclosures.finish_generation(
                disclosure_id,
                status="generated",
                files=[item["path"] for item in metadata],
            )
            self._trace(candidate, "generated_human_review_required")
            return {**candidate, "workspace": workspace}
        except Exception as exc:
            self.candidates.fail_generation(candidate_id, type(exc).__name__)
            self.disclosures.finish_generation(disclosure_id, status="failed")
            self.workspace.discard(candidate_id)
            raise

    def review(
        self,
        candidate_id: int,
        *,
        decision: str,
        notes: str,
        approved: bool,
    ) -> dict[str, Any]:
        if approved is not True:
            raise ValueError("Human source review requires explicit confirmation")
        if not isinstance(notes, str) or not 1 <= len(notes.strip()) <= 2_000:
            raise ValueError("Human source review notes are invalid")
        candidate = self.candidates.review(
            candidate_id,
            decision=decision,
            notes_sha256=hashlib.sha256(notes.strip().encode("utf-8")).hexdigest(),
        )
        self._trace(candidate, candidate["status"])
        return candidate

    def verify(
        self,
        candidate_id: int,
        requirements: dict[str, Any],
    ) -> dict[str, Any]:
        candidate = self.candidates.get(candidate_id)
        if candidate["status"] != "reviewed":
            raise ValueError("Only a human-reviewed source candidate can be verified")
        plan_record, plan = self._approved_plan(candidate["plan_id"], requirements)
        if plan_record["plan_sha256"] != candidate["plan_sha256"]:
            raise ValueError("Source candidate and implementation plan do not match")
        verification = self.verifier.verify(candidate, plan)
        updated = self.candidates.record_verification(candidate_id, verification)
        self._trace(updated, updated["status"])
        return updated

    def approve(self, candidate_id: int, *, approved: bool) -> dict[str, Any]:
        candidate = self.candidates.approve(candidate_id, approved=approved)
        self._trace(candidate, "approved")
        return candidate

    def read_file(self, candidate_id: int, path: str) -> dict[str, Any]:
        candidate = self.candidates.get(candidate_id)
        allowed = {item["path"] for item in candidate["files"]}
        if path not in allowed:
            raise ValueError("Source candidate file is not declared")
        return {
            "candidate_id": candidate_id,
            "path": path,
            "content": self.workspace.read(candidate_id, path),
        }

    def _trace(self, candidate: dict[str, Any], state: str) -> None:
        trace_id = candidate.get("trace_id")
        if not trace_id:
            return
        stages = [
            "user_requirement", "blueprint_revalidation", "implementation_plan",
            "provider_disclosure", "source_candidate_generation",
        ]
        if candidate["human_review_completed"]:
            stages.append("human_review")
        if candidate["static_verification_executed"]:
            stages.append("static_verification")
        if state == "approved":
            stages.append("candidate_approval")
        self.traces.annotate_lifecycle(
            trace_id,
            processing_stage=state,
            transformations=stages,
            data_accessed=["data_environment", "candidate_environment"],
            data_created=[
                f"implementation_plan:{candidate['plan_id']}",
                f"source_candidate:{candidate['candidate_id']}",
            ],
            storage_destinations=["trace_environment", "candidate_environment"],
            execution_metadata={
                "protocol_version": self.PROTOCOL,
                "plan_id": candidate["plan_id"],
                "candidate_id": candidate["candidate_id"],
                "disclosure_id": candidate["disclosure_id"],
                "lifecycle_state": state,
                "provider_disclosure_approved": True,
                "runtime_tests_executed": False,
                "external_worker_called": False,
                "external_deployment_executed": False,
            },
            result_summary="Source candidate lifecycle evidence updated",
        )
