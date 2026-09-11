from __future__ import annotations

import hashlib
import json
import re
import uuid
from pathlib import Path
from typing import Any

from sparkle.config import data_root
from sparkle.contracts import ToolDefinition
from sparkle.knowledge_evidence import verify_citations
from sparkle.storage import KnowledgeStore, SQLiteStore, utc_now


class ResearchWorkflowError(ValueError):
    pass


class ResearchService(SQLiteStore):
    """Persistent research plans, exact stored evidence, claims and reports."""

    NAME = re.compile(r"^[a-z][a-z0-9_-]{1,63}$")
    STATUS = {"planning", "collecting", "synthesizing", "complete", "archived"}
    TRANSITIONS = {
        "planning": {"collecting", "archived"},
        "collecting": {"planning", "synthesizing", "archived"},
        "synthesizing": {"collecting", "complete", "archived"},
        "complete": {"collecting", "archived"},
        "archived": set(),
    }
    QUALITY = {"unknown", "low", "medium", "high", "authoritative"}
    CLAIM_KIND = {"fact", "inference", "comparison", "recommendation"}
    UNCERTAINTY = {"low", "medium", "high"}
    MAX_PROJECTS = 500
    MAX_QUESTIONS = 50
    MAX_EVIDENCE = 500
    MAX_CLAIMS = 200

    def __init__(self, knowledge: KnowledgeStore, path: Path | None = None):
        self.knowledge = knowledge
        super().__init__(path or data_root() / "data_environment" / "research.sqlite3")
        self.initialize()

    def initialize(self) -> None:
        with self.connect() as db:
            db.executescript("""
                CREATE TABLE IF NOT EXISTS research_projects(
                    name TEXT PRIMARY KEY,title TEXT NOT NULL,objective TEXT NOT NULL,
                    questions_json TEXT NOT NULL,status TEXT NOT NULL,revision INTEGER NOT NULL,
                    created_at TEXT NOT NULL,updated_at TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS research_evidence(
                    id TEXT PRIMARY KEY,project_name TEXT NOT NULL,source_id INTEGER NOT NULL,
                    chunk_id INTEGER NOT NULL,citation_digest TEXT NOT NULL,quote TEXT NOT NULL,
                    source_quality TEXT NOT NULL,quality_rationale TEXT NOT NULL,
                    citation_integrity TEXT NOT NULL,claim_truth TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    FOREIGN KEY(project_name) REFERENCES research_projects(name)
                );
                CREATE INDEX IF NOT EXISTS idx_research_evidence_project
                    ON research_evidence(project_name,created_at,id);
                CREATE TABLE IF NOT EXISTS research_claims(
                    id TEXT PRIMARY KEY,project_name TEXT NOT NULL,kind TEXT NOT NULL,
                    statement TEXT NOT NULL,evidence_ids_json TEXT NOT NULL,
                    uncertainty TEXT NOT NULL,notes TEXT NOT NULL,created_at TEXT NOT NULL,
                    FOREIGN KEY(project_name) REFERENCES research_projects(name)
                );
                CREATE INDEX IF NOT EXISTS idx_research_claims_project
                    ON research_claims(project_name,created_at,id);
                CREATE TABLE IF NOT EXISTS research_events(
                    id INTEGER PRIMARY KEY AUTOINCREMENT,project_name TEXT NOT NULL,
                    event TEXT NOT NULL,revision INTEGER NOT NULL,actor TEXT NOT NULL,
                    created_at TEXT NOT NULL
                );
            """)

    @staticmethod
    def _json(value: Any) -> str:
        return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False)

    @classmethod
    def _name(cls, value: Any) -> str:
        if not isinstance(value, str) or not cls.NAME.fullmatch(value):
            raise ResearchWorkflowError("Research name must be a 2-64 character lowercase identifier")
        return value

    @staticmethod
    def _text(value: Any, field: str, maximum: int) -> str:
        if not isinstance(value, str) or not value.strip() or len(value.strip()) > maximum:
            raise ResearchWorkflowError(f"{field} must contain 1-{maximum} characters")
        return value.strip()

    @staticmethod
    def _actor(value: Any) -> str:
        if not isinstance(value, str) or not value.strip() or len(value.strip()) > 80:
            raise ResearchWorkflowError("Research actor is required")
        return value.strip()

    @classmethod
    def _questions(cls, value: Any) -> list[str]:
        if not isinstance(value, list) or not 1 <= len(value) <= cls.MAX_QUESTIONS:
            raise ResearchWorkflowError("Research plan requires 1-50 questions")
        questions = [cls._text(item, "question", 500) for item in value]
        if len(questions) != len(set(questions)):
            raise ResearchWorkflowError("Research questions must be unique")
        return questions

    def create(self, definition: dict[str, Any], *, actor: str = "operator") -> dict[str, Any]:
        if not isinstance(definition, dict) or set(definition) != {"name", "title", "objective", "questions"}:
            raise ResearchWorkflowError("Research definition fields are invalid")
        name = self._name(definition["name"])
        title = self._text(definition["title"], "title", 200)
        objective = self._text(definition["objective"], "objective", 2000)
        questions = self._questions(definition["questions"])
        actor, now = self._actor(actor), utc_now()
        with self.connect() as db:
            db.execute("BEGIN IMMEDIATE")
            if db.execute("SELECT 1 FROM research_projects WHERE name=?", (name,)).fetchone():
                raise ResearchWorkflowError("Research project already exists")
            if db.execute("SELECT count(*) FROM research_projects").fetchone()[0] >= self.MAX_PROJECTS:
                raise ResearchWorkflowError("Research project limit reached")
            db.execute("INSERT INTO research_projects VALUES(?,?,?,?, 'planning',1,?,?)",
                       (name, title, objective, self._json(questions), now, now))
            db.execute("INSERT INTO research_events(project_name,event,revision,actor,created_at) VALUES(?,?,?,?,?)",
                       (name, "create", 1, actor, now))
        return self.inspect(name)

    def inspect(self, name: str, *, include_archived: bool = False) -> dict[str, Any]:
        name = self._name(name)
        with self.connect() as db:
            row = db.execute("SELECT * FROM research_projects WHERE name=?", (name,)).fetchone()
            if row is None or (row["status"] == "archived" and not include_archived):
                raise ResearchWorkflowError("Unknown active research project")
            evidence = db.execute("SELECT * FROM research_evidence WHERE project_name=? ORDER BY created_at,id", (name,)).fetchall()
            claims = db.execute("SELECT * FROM research_claims WHERE project_name=? ORDER BY created_at,id", (name,)).fetchall()
        return {
            "name": row["name"], "title": row["title"], "objective": row["objective"],
            "questions": json.loads(row["questions_json"]), "status": row["status"],
            "revision": row["revision"], "created_at": row["created_at"], "updated_at": row["updated_at"],
            "evidence": [self._evidence(item) for item in evidence],
            "claims": [self._claim(item) for item in claims],
        }

    def list(self, *, include_archived: bool = False, limit: int = 100) -> list[dict[str, Any]]:
        if type(limit) is not int or not 1 <= limit <= 100:
            raise ResearchWorkflowError("Research list limit must be 1-100")
        query = "SELECT name,title,objective,status,revision,updated_at FROM research_projects"
        if not include_archived:
            query += " WHERE status!='archived'"
        with self.connect() as db:
            rows = db.execute(query + " ORDER BY updated_at DESC,name LIMIT ?", (limit,)).fetchall()
        return [dict(row) for row in rows]

    def transition(self, name: str, status: str, *, expected_revision: int, actor: str = "operator") -> dict[str, Any]:
        name, actor = self._name(name), self._actor(actor)
        if status not in self.STATUS:
            raise ResearchWorkflowError("Research status is invalid")
        with self.connect() as db:
            db.execute("BEGIN IMMEDIATE")
            row = db.execute("SELECT status,revision FROM research_projects WHERE name=?", (name,)).fetchone()
            if row is None:
                raise ResearchWorkflowError("Unknown research project")
            if row["revision"] != expected_revision:
                raise ResearchWorkflowError(f"Research revision conflict: expected {expected_revision}, current {row['revision']}")
            if status not in self.TRANSITIONS[row["status"]]:
                raise ResearchWorkflowError(f"Invalid research transition: {row['status']} -> {status}")
            if status == "complete":
                claims = db.execute("SELECT count(*) FROM research_claims WHERE project_name=?", (name,)).fetchone()[0]
                if claims == 0:
                    raise ResearchWorkflowError("Research cannot complete without claims")
            revision, now = expected_revision + 1, utc_now()
            db.execute("UPDATE research_projects SET status=?,revision=?,updated_at=? WHERE name=?",
                       (status, revision, now, name))
            db.execute("INSERT INTO research_events(project_name,event,revision,actor,created_at) VALUES(?,?,?,?,?)",
                       (name, f"status:{status}", revision, actor, now))
        return self.inspect(name, include_archived=True)

    def add_evidence(self, name: str, citation: dict[str, Any], *, source_quality: str = "unknown",
                     quality_rationale: str = "Not independently assessed", actor: str = "operator") -> dict[str, Any]:
        name, actor = self._name(name), self._actor(actor)
        project = self.inspect(name)
        if project["status"] not in {"collecting", "synthesizing"}:
            raise ResearchWorkflowError("Evidence can only be added while collecting or synthesizing")
        if source_quality not in self.QUALITY:
            raise ResearchWorkflowError("Source quality label is invalid")
        rationale = self._text(quality_rationale, "quality rationale", 1000)
        verification = verify_citations(self.knowledge, [citation])
        if verification["citation_integrity"] == "REJECTED":
            raise ResearchWorkflowError("Stored citation integrity was rejected")
        with self.connect() as db:
            count = db.execute("SELECT count(*) FROM research_evidence WHERE project_name=?", (name,)).fetchone()[0]
            if count >= self.MAX_EVIDENCE:
                raise ResearchWorkflowError("Research evidence limit reached")
            evidence_id = f"SPK-RESEARCH-EV-{uuid.uuid4().hex.upper()}"
            now = utc_now()
            db.execute("""INSERT INTO research_evidence VALUES(?,?,?,?,?,?,?,?,?,?,?)""", (
                evidence_id, name, citation["source_id"], citation["chunk_id"], citation["digest"], citation["quote"],
                source_quality, rationale, verification["citation_integrity"], verification["claim_truth"], now,
            ))
            db.execute("INSERT INTO research_events(project_name,event,revision,actor,created_at) VALUES(?,?,?,?,?)",
                       (name, "evidence:add", project["revision"], actor, now))
            row = db.execute("SELECT * FROM research_evidence WHERE id=?", (evidence_id,)).fetchone()
        return self._evidence(row)

    def add_claim(self, name: str, claim: dict[str, Any], *, actor: str = "operator") -> dict[str, Any]:
        name, actor = self._name(name), self._actor(actor)
        project = self.inspect(name)
        if project["status"] != "synthesizing":
            raise ResearchWorkflowError("Claims can only be added while synthesizing")
        if not isinstance(claim, dict) or set(claim) != {"kind", "statement", "evidence_ids", "uncertainty", "notes"}:
            raise ResearchWorkflowError("Research claim fields are invalid")
        if claim["kind"] not in self.CLAIM_KIND or claim["uncertainty"] not in self.UNCERTAINTY:
            raise ResearchWorkflowError("Research claim classification is invalid")
        statement = self._text(claim["statement"], "claim statement", 3000)
        notes = self._text(claim["notes"], "claim notes", 2000)
        evidence_ids = claim["evidence_ids"]
        if not isinstance(evidence_ids, list) or len(evidence_ids) > 20 or len(evidence_ids) != len(set(evidence_ids)):
            raise ResearchWorkflowError("Claim evidence IDs are invalid")
        if claim["kind"] == "fact" and not evidence_ids:
            raise ResearchWorkflowError("Factual claims require stored evidence")
        with self.connect() as db:
            known = {row["id"] for row in db.execute("SELECT id FROM research_evidence WHERE project_name=?", (name,)).fetchall()}
            if any(item not in known for item in evidence_ids):
                raise ResearchWorkflowError("Claim references unknown research evidence")
            if db.execute("SELECT count(*) FROM research_claims WHERE project_name=?", (name,)).fetchone()[0] >= self.MAX_CLAIMS:
                raise ResearchWorkflowError("Research claim limit reached")
            claim_id = f"SPK-RESEARCH-CL-{uuid.uuid4().hex.upper()}"
            now = utc_now()
            db.execute("INSERT INTO research_claims VALUES(?,?,?,?,?,?,?,?)",
                       (claim_id, name, claim["kind"], statement, self._json(evidence_ids), claim["uncertainty"], notes, now))
            db.execute("INSERT INTO research_events(project_name,event,revision,actor,created_at) VALUES(?,?,?,?,?)",
                       (name, "claim:add", project["revision"], actor, now))
            row = db.execute("SELECT * FROM research_claims WHERE id=?", (claim_id,)).fetchone()
        return self._claim(row)

    def report(self, name: str) -> dict[str, Any]:
        project = self.inspect(name, include_archived=True)
        lines = [f"# {project['title']}", "", project["objective"], "", "## Research questions"]
        lines.extend(f"- {question}" for question in project["questions"])
        lines.extend(["", "## Findings"])
        if not project["claims"]:
            lines.append("No synthesized claims have been recorded.")
        for claim in project["claims"]:
            evidence = ", ".join(claim["evidence_ids"]) or "none"
            lines.extend([f"### {claim['kind'].title()}", claim["statement"],
                          f"Uncertainty: {claim['uncertainty']}. Evidence: {evidence}.", claim["notes"], ""])
        lines.append("## Evidence")
        for item in project["evidence"]:
            lines.append(
                f"- {item['id']}: source {item['source_id']}, chunk {item['chunk_id']}; "
                f"integrity={item['citation_integrity']}; source_quality={item['source_quality']}; claim_truth={item['claim_truth']}."
            )
        report = "\n".join(lines).rstrip() + "\n"
        return {"project": name, "revision": project["revision"], "status": project["status"],
                "report": report, "sha256": hashlib.sha256(report.encode()).hexdigest(),
                "claim_truth_established": False, "external_source_verification": False}

    @staticmethod
    def _evidence(row: Any) -> dict[str, Any]:
        return {name: row[name] for name in row.keys()}

    @staticmethod
    def _claim(row: Any) -> dict[str, Any]:
        value = {name: row[name] for name in row.keys() if name != "evidence_ids_json"}
        value["evidence_ids"] = json.loads(row["evidence_ids_json"])
        return value

    def stats(self) -> dict[str, Any]:
        with self.connect() as db:
            projects = db.execute("SELECT count(*) FROM research_projects WHERE status!='archived'").fetchone()[0]
            evidence = db.execute("SELECT count(*) FROM research_evidence").fetchone()[0]
            claims = db.execute("SELECT count(*) FROM research_claims").fetchone()[0]
        return {"status": "ready", "projects": projects, "evidence": evidence, "claims": claims}


class ResearchReadTool:
    name = "research_workspace"
    description = "Read a persistent research plan, exact stored evidence, claims, uncertainty and deterministic report. Cannot mutate research state."
    parameters = {"type": "object", "properties": {"project": {"type": "string"}, "report": {"type": "boolean"}},
                  "required": ["project"], "additionalProperties": False}

    def __init__(self, service: ResearchService):
        self.service = service

    def definition(self) -> ToolDefinition:
        return ToolDefinition(self.name, self.description, self.parameters)

    def run(self, arguments: dict[str, Any]) -> Any:
        if not isinstance(arguments, dict) or set(arguments) - {"project", "report"} or "project" not in arguments:
            raise ResearchWorkflowError("Research project identity is required")
        if type(arguments.get("report", False)) is not bool:
            raise ResearchWorkflowError("Research report flag must be boolean")
        return self.service.report(str(arguments["project"])) if arguments.get("report") else self.service.inspect(str(arguments["project"]))
