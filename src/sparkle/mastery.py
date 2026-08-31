from __future__ import annotations

import json
import hashlib
import re
import sqlite3
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

from sparkle.config import data_root
from sparkle.storage import SQLiteStore, utc_now


class SkillMasteryStore(SQLiteStore):
    """Bounded structured skills whose mastery is derived from evidence."""

    PROTOCOL = "SPARKLE-SKILL/1"
    MAX_SKILLS = 1_000
    MAX_EVIDENCE_PER_SKILL = 100
    NAME_PATTERN = re.compile(r"^[a-z][a-z0-9_-]{1,63}$")
    EVIDENCE_TYPES = {
        "question",
        "exercise",
        "test",
        "project",
        "implementation",
        "independent_problem_solving",
    }
    CREATE_FIELDS = {"name", "title", "description", "target_level"}
    UPDATE_FIELDS = {"title", "description", "target_level"}
    EVIDENCE_FIELDS = {
        "skill_name", "evidence_type", "score", "verified", "summary",
        "artifact_ref", "occurred_at",
    }
    LEVEL_NAMES = {
        0: "awareness",
        1: "fundamentals",
        2: "beginner",
        3: "intermediate",
        4: "advanced",
        5: "professional",
        6: "expert_research",
    }

    def __init__(self, path: Path | None = None):
        super().__init__(
            path or data_root() / "data_environment" / "skills.sqlite3"
        )
        self.initialize()

    def initialize(self) -> None:
        with self.connect() as connection:
            connection.executescript("""
                CREATE TABLE IF NOT EXISTS skills (
                    name TEXT PRIMARY KEY,
                    title TEXT NOT NULL,
                    description TEXT NOT NULL,
                    target_level INTEGER NOT NULL,
                    current_level INTEGER NOT NULL,
                    version INTEGER NOT NULL,
                    archived INTEGER NOT NULL DEFAULT 0,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS skill_evidence (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    skill_name TEXT NOT NULL,
                    evidence_type TEXT NOT NULL,
                    score INTEGER NOT NULL,
                    verified INTEGER NOT NULL,
                    summary TEXT NOT NULL,
                    artifact_ref TEXT,
                    occurred_at TEXT NOT NULL,
                    evidence_digest TEXT NOT NULL,
                    created_at TEXT NOT NULL
                );
                CREATE INDEX IF NOT EXISTS idx_skill_evidence_name
                ON skill_evidence(skill_name, id DESC);
                CREATE UNIQUE INDEX IF NOT EXISTS idx_skill_evidence_digest
                ON skill_evidence(skill_name, evidence_digest);
            """)

    @staticmethod
    def _text(value: Any, *, field: str, minimum: int, maximum: int) -> str:
        if not isinstance(value, str):
            raise ValueError(f"Skill {field} must be a string")
        normalized = value.strip()
        if not minimum <= len(normalized) <= maximum:
            raise ValueError(
                f"Skill {field} must contain {minimum}-{maximum} characters"
            )
        return normalized

    @staticmethod
    def _timestamp(value: Any) -> str:
        if not isinstance(value, str) or not value.strip():
            raise ValueError("Skill occurred_at must be an ISO-8601 timestamp")
        try:
            parsed = datetime.fromisoformat(value.strip().replace("Z", "+00:00"))
        except ValueError as exc:
            raise ValueError(
                "Skill occurred_at must be an ISO-8601 timestamp"
            ) from exc
        if parsed.tzinfo is None:
            raise ValueError("Skill occurred_at must include a timezone")
        normalized = parsed.astimezone(UTC)
        if normalized > datetime.now(UTC) + timedelta(minutes=5):
            raise ValueError("Skill occurred_at cannot be in the future")
        return normalized.isoformat()

    @classmethod
    def validate(cls, value: Any) -> dict[str, Any]:
        if not isinstance(value, dict) or set(value) != cls.CREATE_FIELDS:
            raise ValueError(
                "Skill manifest must contain the exact SPARKLE-SKILL/1 fields"
            )
        name = value["name"]
        if not isinstance(name, str) or cls.NAME_PATTERN.fullmatch(name) is None:
            raise ValueError("Skill name must be a 2-64 character lowercase identifier")
        target = value["target_level"]
        if type(target) is not int or not 0 <= target <= 6:
            raise ValueError("Skill target_level must be an integer from 0 to 6")
        return {
            "name": name,
            "title": cls._text(
                value["title"], field="title", minimum=1, maximum=120,
            ),
            "description": cls._text(
                value["description"], field="description", minimum=1,
                maximum=1_000,
            ),
            "target_level": target,
        }

    @classmethod
    def validate_evidence(cls, value: Any) -> dict[str, Any]:
        if not isinstance(value, dict) or set(value) != cls.EVIDENCE_FIELDS:
            raise ValueError(
                "Skill evidence must contain the exact SPARKLE-SKILL/1 fields"
            )
        name = value["skill_name"]
        if not isinstance(name, str) or cls.NAME_PATTERN.fullmatch(name) is None:
            raise ValueError("Skill evidence skill_name is invalid")
        evidence_type = value["evidence_type"]
        if (
            not isinstance(evidence_type, str)
            or evidence_type not in cls.EVIDENCE_TYPES
        ):
            raise ValueError("Skill evidence_type is unsupported")
        score = value["score"]
        if type(score) is not int or not 0 <= score <= 100:
            raise ValueError("Skill evidence score must be an integer from 0 to 100")
        if type(value["verified"]) is not bool:
            raise ValueError("Skill evidence verified must be boolean")
        artifact_ref = value["artifact_ref"]
        if artifact_ref is not None:
            artifact_ref = cls._text(
                artifact_ref, field="artifact_ref", minimum=1, maximum=200,
            )
        return {
            "skill_name": name,
            "evidence_type": evidence_type,
            "score": score,
            "verified": value["verified"],
            "summary": cls._text(
                value["summary"], field="evidence summary", minimum=1,
                maximum=500,
            ),
            "artifact_ref": artifact_ref,
            "occurred_at": cls._timestamp(value["occurred_at"]),
        }

    @classmethod
    def _level(cls, evidence: list[dict[str, Any]]) -> int:
        verified = [item for item in evidence if item["verified"]]
        if not verified:
            return 0
        count = len(verified)
        kinds = {item["evidence_type"] for item in verified}
        average = sum(item["score"] for item in verified) / count
        applied = kinds & {
            "exercise", "test", "project", "implementation",
            "independent_problem_solving",
        }
        level = 0
        if count >= 1 and average >= 60:
            level = 1
        if count >= 2 and len(kinds) >= 2 and average >= 65:
            level = 2
        if count >= 3 and len(kinds) >= 2 and applied and average >= 70:
            level = 3
        if count >= 5 and len(kinds) >= 3 and len(applied) >= 2 and average >= 75:
            level = 4
        if (
            count >= 7 and len(kinds) >= 4 and average >= 80
            and {"project", "implementation"} <= kinds
        ):
            level = 5
        if (
            count >= 10 and len(kinds) >= 5 and average >= 85
            and {
                "project", "implementation", "independent_problem_solving",
            } <= kinds
        ):
            level = 6
        return level

    @classmethod
    def _requirements(cls, level: int) -> list[str]:
        if level >= 6:
            return []
        return {
            0: ["1 verified item", "average score >= 60"],
            1: ["2 verified items", "2 evidence types", "average score >= 65"],
            2: ["3 verified items", "2 evidence types", "applied evidence", "average score >= 70"],
            3: ["5 verified items", "3 evidence types", "2 applied types", "average score >= 75"],
            4: ["7 verified items", "4 evidence types", "project and implementation", "average score >= 80"],
            5: ["10 verified items", "5 evidence types", "project, implementation, and independent problem solving", "average score >= 85"],
        }[level]

    def create(self, manifest: dict[str, Any]) -> dict[str, Any]:
        skill = self.validate(manifest)
        now = utc_now()
        with self.connect() as connection:
            count = connection.execute(
                "SELECT COUNT(*) FROM skills WHERE archived=0"
            ).fetchone()[0]
            if count >= self.MAX_SKILLS:
                raise ValueError("Skill store reached its 1000 active-skill bound")
            try:
                connection.execute("""
                    INSERT INTO skills(
                        name, title, description, target_level, current_level,
                        version, archived, created_at, updated_at
                    ) VALUES(?,?,?,?,0,1,0,?,?)
                """, (
                    skill["name"], skill["title"], skill["description"],
                    skill["target_level"], now, now,
                ))
            except sqlite3.IntegrityError as exc:
                raise ValueError(f"Skill already exists: {skill['name']}") from exc
        return self.get(skill["name"])

    @staticmethod
    def _record(row: sqlite3.Row) -> dict[str, Any]:
        return {
            "protocol_version": SkillMasteryStore.PROTOCOL,
            "name": row["name"],
            "title": row["title"],
            "description": row["description"],
            "target_level": row["target_level"],
            "current_level": row["current_level"],
            "current_level_name": SkillMasteryStore.LEVEL_NAMES[
                row["current_level"]
            ],
            "version": row["version"],
            "archived": bool(row["archived"]),
            "created_at": row["created_at"],
            "updated_at": row["updated_at"],
        }

    def get(self, name: str) -> dict[str, Any]:
        if not isinstance(name, str) or self.NAME_PATTERN.fullmatch(name) is None:
            raise ValueError("Skill name is invalid")
        with self.connect() as connection:
            row = connection.execute(
                "SELECT * FROM skills WHERE name=?", (name,),
            ).fetchone()
        if row is None:
            raise KeyError(f"Unknown skill: {name}")
        return {**self._record(row), **self.summary(name)}

    def update(
        self, name: str, changes: dict[str, Any], *, expected_version: int,
    ) -> dict[str, Any]:
        current = self.get(name)
        if current["archived"]:
            raise ValueError("Archived skills cannot be updated")
        if type(expected_version) is not int or expected_version < 1:
            raise ValueError("Skill expected_version must be a positive integer")
        if not isinstance(changes, dict) or not changes:
            raise ValueError("Skill changes must be a non-empty object")
        if set(changes) - self.UPDATE_FIELDS:
            raise ValueError("Unsupported skill change fields")
        candidate = {
            "name": name,
            "title": current["title"],
            "description": current["description"],
            "target_level": current["target_level"],
        }
        candidate.update(changes)
        skill = self.validate(candidate)
        now = utc_now()
        with self.connect() as connection:
            cursor = connection.execute("""
                UPDATE skills SET title=?, description=?, target_level=?,
                    version=version+1, updated_at=?
                WHERE name=? AND version=? AND archived=0
            """, (
                skill["title"], skill["description"], skill["target_level"],
                now, name, expected_version,
            ))
            if cursor.rowcount != 1:
                raise ValueError("Skill version conflict")
        return self.get(name)

    def add_evidence(self, manifest: dict[str, Any]) -> dict[str, Any]:
        evidence = self.validate_evidence(manifest)
        with self.connect() as connection:
            # Serialize the active-state, count, insert, and derived-level update.
            # Without one immediate transaction, a concurrent archive or evidence
            # insertion could cross the checked boundary before the write.
            connection.execute("BEGIN IMMEDIATE")
            skill = connection.execute(
                "SELECT archived FROM skills WHERE name=?",
                (evidence["skill_name"],),
            ).fetchone()
            if skill is None:
                raise KeyError(f"Unknown skill: {evidence['skill_name']}")
            if bool(skill["archived"]):
                raise ValueError("Archived skills cannot receive evidence")
            count = connection.execute(
                "SELECT COUNT(*) FROM skill_evidence WHERE skill_name=?",
                (evidence["skill_name"],),
            ).fetchone()[0]
            if count >= self.MAX_EVIDENCE_PER_SKILL:
                raise ValueError("Skill reached its 100-evidence bound")
            digest = hashlib.sha256(json.dumps(
                evidence, ensure_ascii=False, separators=(",", ":"),
                sort_keys=True, allow_nan=False,
            ).encode("utf-8")).hexdigest()
            try:
                cursor = connection.execute("""
                    INSERT INTO skill_evidence(
                        skill_name, evidence_type, score, verified, summary,
                        artifact_ref, occurred_at, evidence_digest, created_at
                    ) VALUES(?,?,?,?,?,?,?,?,?)
                """, (
                    evidence["skill_name"], evidence["evidence_type"],
                    evidence["score"], int(evidence["verified"]),
                    evidence["summary"], evidence["artifact_ref"],
                    evidence["occurred_at"], digest, utc_now(),
                ))
            except sqlite3.IntegrityError as exc:
                raise ValueError("Duplicate skill evidence is not allowed") from exc
            rows = connection.execute(
                "SELECT * FROM skill_evidence WHERE skill_name=? ORDER BY id",
                (evidence["skill_name"],),
            ).fetchall()
            level = self._level([self._evidence(row) for row in rows])
            updated = connection.execute("""
                UPDATE skills SET current_level=?, version=version+1,
                    updated_at=? WHERE name=? AND archived=0
            """, (level, utc_now(), evidence["skill_name"]))
            if updated.rowcount != 1:
                raise ValueError("Skill changed while evidence was added")
            evidence_id = cursor.lastrowid
        return {
            "evidence": self.evidence_by_id(int(evidence_id)),
            "skill": self.get(evidence["skill_name"]),
        }

    @staticmethod
    def _evidence(row: sqlite3.Row) -> dict[str, Any]:
        return {
            "evidence_id": row["id"],
            "skill_name": row["skill_name"],
            "evidence_type": row["evidence_type"],
            "score": row["score"],
            "verified": bool(row["verified"]),
            "summary": row["summary"],
            "artifact_ref": row["artifact_ref"],
            "occurred_at": row["occurred_at"],
            "created_at": row["created_at"],
        }

    def evidence_by_id(self, evidence_id: int) -> dict[str, Any]:
        if type(evidence_id) is not int or evidence_id < 1:
            raise ValueError("Skill evidence_id must be a positive integer")
        with self.connect() as connection:
            row = connection.execute(
                "SELECT * FROM skill_evidence WHERE id=?", (evidence_id,),
            ).fetchone()
        if row is None:
            raise KeyError(f"Unknown skill evidence: {evidence_id}")
        return self._evidence(row)

    def evidence(self, name: str, *, limit: int = 100) -> list[dict[str, Any]]:
        self.get(name)
        bounded = max(1, min(int(limit), 100))
        with self.connect() as connection:
            rows = connection.execute("""
                SELECT * FROM skill_evidence WHERE skill_name=?
                ORDER BY occurred_at DESC, id DESC LIMIT ?
            """, (name, bounded)).fetchall()
        return [self._evidence(row) for row in rows]

    def summary(self, name: str) -> dict[str, Any]:
        with self.connect() as connection:
            rows = connection.execute(
                "SELECT * FROM skill_evidence WHERE skill_name=? ORDER BY id",
                (name,),
            ).fetchall()
        values = [self._evidence(row) for row in rows]
        verified = [item for item in values if item["verified"]]
        current_level = self._level(values)
        return {
            "current_level": current_level,
            "current_level_name": self.LEVEL_NAMES[current_level],
            "total_evidence_count": len(values),
            "verified_evidence_count": len(verified),
            "evidence_types": sorted({
                item["evidence_type"] for item in verified
            }),
            "average_verified_score": (
                round(sum(item["score"] for item in verified) / len(verified), 2)
                if verified else None
            ),
            "last_evidence_at": max(
                (item["occurred_at"] for item in values), default=None,
            ),
            "next_level_requirements": self._requirements(current_level),
        }

    def list(
        self, *, limit: int = 100, include_archived: bool = False,
    ) -> list[dict[str, Any]]:
        if type(include_archived) is not bool:
            raise ValueError("include_archived must be boolean")
        where = "" if include_archived else "WHERE archived=0"
        with self.connect() as connection:
            rows = connection.execute(f"""
                SELECT * FROM skills {where}
                ORDER BY (target_level-current_level) DESC,
                    target_level DESC, updated_at ASC, name ASC LIMIT ?
            """, (max(1, min(int(limit), 100)),)).fetchall()
        return [{**self._record(row), **self.summary(row["name"])} for row in rows]

    def search(self, query: str, *, limit: int = 20) -> list[dict[str, Any]]:
        if not isinstance(query, str) or len(query.strip()) > 200:
            raise ValueError("Skill search query must contain at most 200 characters")
        normalized = query.strip()
        if not normalized:
            return self.list(limit=max(1, min(int(limit), 20)))
        escaped = normalized.replace("!", "!!").replace("%", "!%").replace("_", "!_")
        pattern = f"%{escaped}%"
        with self.connect() as connection:
            rows = connection.execute("""
                SELECT * FROM skills WHERE archived=0 AND (
                    name LIKE ? ESCAPE '!' OR title LIKE ? ESCAPE '!'
                    OR description LIKE ? ESCAPE '!'
                ) ORDER BY (target_level-current_level) DESC,
                    updated_at ASC, name ASC LIMIT ?
            """, (
                pattern, pattern, pattern, max(1, min(int(limit), 20)),
            )).fetchall()
        return [{**self._record(row), **self.summary(row["name"])} for row in rows]

    def agent_search(self, query: str, *, limit: int = 10) -> list[dict[str, Any]]:
        return [{
            "protocol_version": self.PROTOCOL,
            "name": item["name"],
            "title": item["title"],
            "current_level": item["current_level"],
            "current_level_name": item["current_level_name"],
            "target_level": item["target_level"],
            "mastery_gap": max(0, item["target_level"] - item["current_level"]),
            "verified_evidence_count": item["verified_evidence_count"],
            "total_evidence_count": item["total_evidence_count"],
            "evidence_types": item["evidence_types"],
            "average_verified_score": item["average_verified_score"],
            "last_evidence_at": item["last_evidence_at"],
            "next_level_requirements": item["next_level_requirements"],
        } for item in self.search(query, limit=limit)]

    def archive(self, name: str, *, expected_version: int) -> dict[str, Any]:
        current = self.get(name)
        if current["archived"]:
            raise ValueError("Skill is already archived")
        if type(expected_version) is not int or expected_version < 1:
            raise ValueError("Skill expected_version must be a positive integer")
        with self.connect() as connection:
            cursor = connection.execute("""
                UPDATE skills SET archived=1, version=version+1, updated_at=?
                WHERE name=? AND version=? AND archived=0
            """, (utc_now(), name, expected_version))
            if cursor.rowcount != 1:
                raise ValueError("Skill version conflict")
        return self.get(name)

    def stats(self) -> dict[str, int]:
        with self.connect() as connection:
            row = connection.execute("""
                SELECT
                    SUM(CASE WHEN archived=0 THEN 1 ELSE 0 END) AS active,
                    SUM(CASE WHEN archived=1 THEN 1 ELSE 0 END) AS archived,
                    SUM(CASE WHEN archived=0 AND current_level < target_level
                        THEN 1 ELSE 0 END) AS below_target
                FROM skills
            """).fetchone()
        return {
            "active": int(row["active"] or 0),
            "archived": int(row["archived"] or 0),
            "below_target": int(row["below_target"] or 0),
        }
