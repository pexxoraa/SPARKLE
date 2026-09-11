from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path
from typing import Any

from sparkle.config import data_root
from sparkle.contracts import ToolDefinition
from sparkle.storage import SQLiteStore, utc_now


class ContentWorkflowError(ValueError):
    pass


class ContentWorkflowService(SQLiteStore):
    """Persistent, revisioned content briefs/drafts and deterministic templates."""

    NAME = re.compile(r"^[a-z][a-z0-9_-]{1,63}$")
    VARIABLE = re.compile(r"^[A-Za-z][A-Za-z0-9_]{0,63}$")
    PLACEHOLDER = re.compile(r"\{\{([A-Za-z][A-Za-z0-9_]{0,63})\}\}")
    KINDS = {"article", "script", "post", "email", "brief", "notes", "generic"}
    STATUSES = {"draft", "review", "approved", "archived"}
    TRANSITIONS = {
        "draft": {"review", "archived"},
        "review": {"draft", "approved", "archived"},
        "approved": {"draft", "archived"},
        "archived": set(),
    }
    TRANSFORMS = {"append", "prepend", "replace", "trim"}
    EXPORTS = {"md", "json", "txt"}
    MAX_BODY = 200_000
    MAX_TEMPLATE = 100_000
    MAX_METADATA = 20_000
    MAX_ITEMS = 2_000
    MAX_TEMPLATES = 200

    def __init__(self, path: Path | None = None, export_root: Path | None = None):
        root = data_root()
        super().__init__(path or root / "data_environment" / "content.sqlite3")
        self.export_root = (export_root or root / "data_environment" / "content_exports").resolve()
        self.export_root.mkdir(parents=True, exist_ok=True)
        self.initialize()

    def initialize(self) -> None:
        with self.connect() as db:
            db.execute("""CREATE TABLE IF NOT EXISTS content_templates(
                name TEXT PRIMARY KEY,title TEXT NOT NULL,kind TEXT NOT NULL,body_template TEXT NOT NULL,
                variables_json TEXT NOT NULL,revision INTEGER NOT NULL,archived INTEGER NOT NULL DEFAULT 0,
                created_at TEXT NOT NULL,updated_at TEXT NOT NULL)""")
            db.execute("""CREATE TABLE IF NOT EXISTS content_items(
                name TEXT PRIMARY KEY,title TEXT NOT NULL,kind TEXT NOT NULL,audience TEXT NOT NULL,
                body TEXT NOT NULL,metadata_json TEXT NOT NULL,template_name TEXT,status TEXT NOT NULL,
                revision INTEGER NOT NULL,digest TEXT NOT NULL,created_at TEXT NOT NULL,updated_at TEXT NOT NULL)""")
            db.execute("""CREATE TABLE IF NOT EXISTS content_versions(
                id INTEGER PRIMARY KEY AUTOINCREMENT,item_name TEXT NOT NULL,revision INTEGER NOT NULL,
                snapshot_json TEXT NOT NULL,digest TEXT NOT NULL,event TEXT NOT NULL,operator TEXT NOT NULL,created_at TEXT NOT NULL,
                UNIQUE(item_name,revision),FOREIGN KEY(item_name) REFERENCES content_items(name))""")
            db.execute("CREATE INDEX IF NOT EXISTS idx_content_versions ON content_versions(item_name,revision DESC)")
            db.execute("""CREATE TABLE IF NOT EXISTS content_events(
                id INTEGER PRIMARY KEY AUTOINCREMENT,subject_kind TEXT NOT NULL,subject_name TEXT NOT NULL,
                event TEXT NOT NULL,revision INTEGER NOT NULL,operator TEXT NOT NULL,created_at TEXT NOT NULL)""")

    @staticmethod
    def _json(value: Any) -> str:
        return json.dumps(value, ensure_ascii=False, separators=(",", ":"), sort_keys=True, allow_nan=False)

    @classmethod
    def _digest(cls, value: Any) -> str:
        return hashlib.sha256(cls._json(value).encode("utf-8")).hexdigest()

    @classmethod
    def _name(cls, value: Any) -> str:
        if not isinstance(value, str) or not cls.NAME.fullmatch(value):
            raise ContentWorkflowError("Name must be a 2-64 character lowercase identifier")
        return value

    @staticmethod
    def _operator(value: Any) -> str:
        if not isinstance(value, str) or not value.strip() or len(value.strip()) > 80:
            raise ContentWorkflowError("Operator identity is required")
        return value.strip()

    @staticmethod
    def _text(value: Any, field: str, maximum: int, *, allow_empty: bool = False) -> str:
        if not isinstance(value, str):
            raise ContentWorkflowError(f"{field} must be text")
        normalized = value.strip() if field != "body" else value
        if (not allow_empty and not normalized.strip()) or len(normalized) > maximum:
            raise ContentWorkflowError(f"{field} must contain 1-{maximum} characters")
        return normalized

    @classmethod
    def _metadata(cls, value: Any) -> dict[str, Any]:
        if value is None:
            return {}
        if not isinstance(value, dict):
            raise ContentWorkflowError("Metadata must be an object")
        try:
            encoded = cls._json(value)
        except (TypeError, ValueError) as exc:
            raise ContentWorkflowError("Metadata must contain finite JSON values") from exc
        if len(encoded.encode("utf-8")) > cls.MAX_METADATA:
            raise ContentWorkflowError("Metadata exceeds 20 KB")
        return json.loads(encoded)

    @classmethod
    def _variables(cls, value: Any) -> list[str]:
        if not isinstance(value, list) or len(value) > 50 or not all(isinstance(item, str) and cls.VARIABLE.fullmatch(item) for item in value):
            raise ContentWorkflowError("Template variables must be up to 50 identifiers")
        if len(value) != len(set(value)):
            raise ContentWorkflowError("Template variables must be unique")
        return list(value)

    def save_template(self, definition: dict[str, Any], *, expected_revision: int = 0, operator: str = "operator") -> dict[str, Any]:
        if not isinstance(definition, dict) or set(definition) != {"name", "title", "kind", "body", "variables"}:
            raise ContentWorkflowError("Template definition fields are invalid")
        name = self._name(definition["name"])
        title = self._text(definition["title"], "title", 200)
        kind = definition["kind"]
        if kind not in self.KINDS:
            raise ContentWorkflowError("Unsupported content kind")
        body = self._text(definition["body"], "body", self.MAX_TEMPLATE)
        variables = self._variables(definition["variables"])
        placeholders = set(self.PLACEHOLDER.findall(body))
        if placeholders != set(variables):
            raise ContentWorkflowError("Template placeholders must exactly match declared variables")
        if type(expected_revision) is not int or expected_revision < 0:
            raise ContentWorkflowError("Invalid expected revision")
        actor, now = self._operator(operator), utc_now()
        with self.connect() as db:
            db.execute("BEGIN IMMEDIATE")
            count = db.execute("SELECT count(*) FROM content_templates").fetchone()[0]
            row = db.execute("SELECT revision,created_at FROM content_templates WHERE name=?", (name,)).fetchone()
            if row is None and count >= self.MAX_TEMPLATES:
                raise ContentWorkflowError("Template limit reached")
            actual = int(row["revision"]) if row else 0
            if actual != expected_revision:
                raise ContentWorkflowError(f"Template revision conflict: expected {expected_revision}, current {actual}")
            revision, created = actual + 1, row["created_at"] if row else now
            db.execute("""INSERT INTO content_templates VALUES(?,?,?,?,?,?,0,?,?)
                ON CONFLICT(name) DO UPDATE SET title=excluded.title,kind=excluded.kind,body_template=excluded.body_template,
                variables_json=excluded.variables_json,revision=excluded.revision,archived=0,updated_at=excluded.updated_at""",
                (name, title, kind, body, self._json(variables), revision, created, now))
            db.execute("INSERT INTO content_events(subject_kind,subject_name,event,revision,operator,created_at) VALUES(?,?,?,?,?,?)",
                       ("template", name, "save", revision, actor, now))
        return self.template(name)

    def template(self, name: str, *, include_archived: bool = False) -> dict[str, Any]:
        name = self._name(name)
        with self.connect() as db:
            row = db.execute("SELECT * FROM content_templates WHERE name=?", (name,)).fetchone()
        if row is None or (row["archived"] and not include_archived):
            raise ContentWorkflowError("Unknown active template")
        return {"name": row["name"], "title": row["title"], "kind": row["kind"], "body": row["body_template"],
                "variables": json.loads(row["variables_json"]), "revision": row["revision"], "archived": bool(row["archived"]),
                "created_at": row["created_at"], "updated_at": row["updated_at"]}

    def templates(self, *, include_archived: bool = False) -> list[dict[str, Any]]:
        query = "SELECT name,title,kind,revision,archived,updated_at FROM content_templates"
        if not include_archived:
            query += " WHERE archived=0"
        with self.connect() as db:
            rows = db.execute(query + " ORDER BY name").fetchall()
        return [dict(row) | {"archived": bool(row["archived"])} for row in rows]

    def render(self, template_name: str, variables: dict[str, Any]) -> str:
        template = self.template(template_name)
        if not isinstance(variables, dict):
            raise ContentWorkflowError("Template values must be an object")
        expected = set(template["variables"])
        if set(variables) != expected:
            raise ContentWorkflowError("Template values must exactly match declared variables")
        normalized = {}
        for key, value in variables.items():
            if not isinstance(value, str) or len(value) > 20_000:
                raise ContentWorkflowError("Template values must be bounded strings")
            normalized[key] = value
        rendered = self.PLACEHOLDER.sub(lambda match: normalized[match.group(1)], template["body"])
        if len(rendered) > self.MAX_BODY:
            raise ContentWorkflowError("Rendered content exceeds body limit")
        return rendered

    def _snapshot(self, row: Any) -> dict[str, Any]:
        return {"name": row["name"], "title": row["title"], "kind": row["kind"], "audience": row["audience"],
                "body": row["body"], "metadata": json.loads(row["metadata_json"]), "template_name": row["template_name"],
                "status": row["status"], "revision": row["revision"], "digest": row["digest"],
                "created_at": row["created_at"], "updated_at": row["updated_at"]}

    def _record_version(self, db: Any, snapshot: dict[str, Any], event: str, operator: str) -> None:
        db.execute("INSERT INTO content_versions(item_name,revision,snapshot_json,digest,event,operator,created_at) VALUES(?,?,?,?,?,?,?)",
                   (snapshot["name"], snapshot["revision"], self._json(snapshot), snapshot["digest"], event, operator, snapshot["updated_at"]))
        db.execute("INSERT INTO content_events(subject_kind,subject_name,event,revision,operator,created_at) VALUES(?,?,?,?,?,?)",
                   ("item", snapshot["name"], event, snapshot["revision"], operator, snapshot["updated_at"]))

    def create(self, definition: dict[str, Any], *, operator: str = "operator") -> dict[str, Any]:
        if not isinstance(definition, dict) or set(definition) - {"name", "title", "kind", "audience", "body", "metadata", "template", "variables"}:
            raise ContentWorkflowError("Content definition fields are invalid")
        name = self._name(definition.get("name"))
        title = self._text(definition.get("title"), "title", 200)
        kind = definition.get("kind", "generic")
        if kind not in self.KINDS:
            raise ContentWorkflowError("Unsupported content kind")
        audience = self._text(definition.get("audience", "general"), "audience", 500)
        template_name = definition.get("template")
        if template_name is not None:
            template_name = self._name(template_name)
            body = self.render(template_name, definition.get("variables", {}))
            template = self.template(template_name)
            if kind != template["kind"]:
                raise ContentWorkflowError("Content kind must match its template kind")
        else:
            if "variables" in definition:
                raise ContentWorkflowError("variables require a template")
            body = self._text(definition.get("body"), "body", self.MAX_BODY)
        metadata = self._metadata(definition.get("metadata", {}))
        actor, now = self._operator(operator), utc_now()
        with self.connect() as db:
            db.execute("BEGIN IMMEDIATE")
            if db.execute("SELECT 1 FROM content_items WHERE name=?", (name,)).fetchone():
                raise ContentWorkflowError("Content item already exists")
            if db.execute("SELECT count(*) FROM content_items").fetchone()[0] >= self.MAX_ITEMS:
                raise ContentWorkflowError("Content item limit reached")
            digest = self._digest({"title": title, "kind": kind, "audience": audience, "body": body, "metadata": metadata, "template": template_name, "status": "draft"})
            db.execute("INSERT INTO content_items VALUES(?,?,?,?,?,?,?,?,?,?,?,?)",
                       (name, title, kind, audience, body, self._json(metadata), template_name, "draft", 1, digest, now, now))
            row = db.execute("SELECT * FROM content_items WHERE name=?", (name,)).fetchone()
            snapshot = self._snapshot(row)
            self._record_version(db, snapshot, "create", actor)
        return snapshot

    def get(self, name: str, *, include_archived: bool = False) -> dict[str, Any]:
        name = self._name(name)
        with self.connect() as db:
            row = db.execute("SELECT * FROM content_items WHERE name=?", (name,)).fetchone()
        if row is None or (row["status"] == "archived" and not include_archived):
            raise ContentWorkflowError("Unknown active content item")
        return self._snapshot(row)

    def search(self, query: str = "", *, limit: int = 20, include_archived: bool = False) -> list[dict[str, Any]]:
        if not isinstance(query, str) or len(query) > 200 or type(limit) is not int or not 1 <= limit <= 100:
            raise ContentWorkflowError("Invalid content search")
        lowered = query.casefold().strip()
        sql = "SELECT * FROM content_items"
        params: list[Any] = []
        clauses = []
        if not include_archived:
            clauses.append("status!='archived'")
        if lowered:
            clauses.append("(lower(name) LIKE ? OR lower(title) LIKE ? OR lower(kind) LIKE ? OR lower(audience) LIKE ?)")
            term = f"%{lowered}%"
            params.extend([term] * 4)
        if clauses:
            sql += " WHERE " + " AND ".join(clauses)
        sql += " ORDER BY updated_at DESC,name LIMIT ?"
        params.append(limit)
        with self.connect() as db:
            rows = db.execute(sql, params).fetchall()
        return [{key: value for key, value in self._snapshot(row).items() if key != "body"} | {"body_preview": row["body"][:500]} for row in rows]

    def update(self, name: str, changes: dict[str, Any], *, expected_revision: int, operator: str = "operator") -> dict[str, Any]:
        name, actor = self._name(name), self._operator(operator)
        if not isinstance(changes, dict) or not changes or set(changes) - {"title", "audience", "body", "metadata"}:
            raise ContentWorkflowError("Unsupported content changes")
        with self.connect() as db:
            db.execute("BEGIN IMMEDIATE")
            row = db.execute("SELECT * FROM content_items WHERE name=?", (name,)).fetchone()
            if row is None or row["status"] == "archived":
                raise ContentWorkflowError("Unknown active content item")
            if int(row["revision"]) != expected_revision:
                raise ContentWorkflowError(f"Content revision conflict: expected {expected_revision}, current {row['revision']}")
            if row["status"] == "approved":
                raise ContentWorkflowError("Approved content must return to draft before editing")
            values = self._snapshot(row)
            if "title" in changes:
                values["title"] = self._text(changes["title"], "title", 200)
            if "audience" in changes:
                values["audience"] = self._text(changes["audience"], "audience", 500)
            if "body" in changes:
                values["body"] = self._text(changes["body"], "body", self.MAX_BODY)
            if "metadata" in changes:
                values["metadata"] = self._metadata(changes["metadata"])
            values["revision"] = expected_revision + 1
            values["updated_at"] = utc_now()
            values["digest"] = self._digest({key: values[key] for key in ("title", "kind", "audience", "body", "metadata", "template_name", "status")})
            db.execute("UPDATE content_items SET title=?,audience=?,body=?,metadata_json=?,revision=?,digest=?,updated_at=? WHERE name=?",
                       (values["title"], values["audience"], values["body"], self._json(values["metadata"]), values["revision"], values["digest"], values["updated_at"], name))
            self._record_version(db, values, "update", actor)
        return values

    def transform(self, name: str, transform: dict[str, Any], *, expected_revision: int, operator: str = "operator") -> dict[str, Any]:
        if not isinstance(transform, dict) or "action" not in transform or set(transform) - {"action", "text", "old", "new", "count"}:
            raise ContentWorkflowError("Invalid content transform")
        action = transform["action"]
        if action not in self.TRANSFORMS:
            raise ContentWorkflowError("Unsupported content transform")
        item = self.get(name)
        body = item["body"]
        if action in {"append", "prepend"}:
            text = self._text(transform.get("text"), "body", self.MAX_BODY, allow_empty=True)
            body = body + text if action == "append" else text + body
        elif action == "trim":
            if set(transform) != {"action"}:
                raise ContentWorkflowError("trim takes no additional fields")
            body = body.strip()
        else:
            old = self._text(transform.get("old"), "body", self.MAX_BODY)
            new = self._text(transform.get("new", ""), "body", self.MAX_BODY, allow_empty=True)
            count = transform.get("count", -1)
            if type(count) is not int or count < -1 or count > 10_000:
                raise ContentWorkflowError("Replacement count is invalid")
            if old not in body:
                raise ContentWorkflowError("Replacement source text was not found")
            body = body.replace(old, new, count)
        if not body.strip() or len(body) > self.MAX_BODY:
            raise ContentWorkflowError("Transformed body violates content limits")
        return self.update(name, {"body": body}, expected_revision=expected_revision, operator=operator)

    def transition(self, name: str, status: str, *, expected_revision: int, operator: str = "operator") -> dict[str, Any]:
        name, actor = self._name(name), self._operator(operator)
        if status not in self.STATUSES:
            raise ContentWorkflowError("Unsupported content status")
        with self.connect() as db:
            db.execute("BEGIN IMMEDIATE")
            row = db.execute("SELECT * FROM content_items WHERE name=?", (name,)).fetchone()
            if row is None:
                raise ContentWorkflowError("Unknown content item")
            current = row["status"]
            if int(row["revision"]) != expected_revision:
                raise ContentWorkflowError(f"Content revision conflict: expected {expected_revision}, current {row['revision']}")
            if status not in self.TRANSITIONS[current]:
                raise ContentWorkflowError(f"Invalid content transition: {current} -> {status}")
            values = self._snapshot(row)
            values["status"] = status
            values["revision"] = expected_revision + 1
            values["updated_at"] = utc_now()
            values["digest"] = self._digest({key: values[key] for key in ("title", "kind", "audience", "body", "metadata", "template_name", "status")})
            db.execute("UPDATE content_items SET status=?,revision=?,digest=?,updated_at=? WHERE name=?",
                       (status, values["revision"], values["digest"], values["updated_at"], name))
            self._record_version(db, values, f"status:{status}", actor)
        return values

    def history(self, name: str, *, limit: int = 50) -> list[dict[str, Any]]:
        name = self._name(name)
        if type(limit) is not int or not 1 <= limit <= 100:
            raise ContentWorkflowError("History limit must be 1-100")
        with self.connect() as db:
            rows = db.execute("SELECT revision,digest,event,operator,created_at FROM content_versions WHERE item_name=? ORDER BY revision DESC LIMIT ?", (name, limit)).fetchall()
        return [dict(row) for row in rows]

    def export(self, name: str, format: str, *, expected_revision: int) -> dict[str, Any]:
        if format not in self.EXPORTS:
            raise ContentWorkflowError("Export format must be md, json or txt")
        item = self.get(name)
        if item["revision"] != expected_revision:
            raise ContentWorkflowError(f"Content revision conflict: expected {expected_revision}, current {item['revision']}")
        if format == "json":
            payload = self._json(item) + "\n"
        elif format == "md":
            payload = f"# {item['title']}\n\n{item['body']}\n"
        else:
            payload = item["body"] + ("" if item["body"].endswith("\n") else "\n")
        digest = hashlib.sha256(payload.encode("utf-8")).hexdigest()
        path = self.export_root / f"{item['name']}.r{item['revision']}.{format}"
        path.write_text(payload, encoding="utf-8")
        return {"name": item["name"], "revision": item["revision"], "format": format,
                "path": str(path.relative_to(self.export_root.parent)), "sha256": digest, "bytes": len(payload.encode("utf-8"))}

    def stats(self) -> dict[str, Any]:
        with self.connect() as db:
            items = db.execute("SELECT count(*) FROM content_items WHERE status!='archived'").fetchone()[0]
            archived = db.execute("SELECT count(*) FROM content_items WHERE status='archived'").fetchone()[0]
            templates = db.execute("SELECT count(*) FROM content_templates WHERE archived=0").fetchone()[0]
            versions = db.execute("SELECT count(*) FROM content_versions").fetchone()[0]
        return {"status": "ready", "items": items, "archived_items": archived, "templates": templates, "versions": versions}


class ContentReadTool:
    name = "content_search"
    description = "Read bounded persisted content briefs/drafts by identity or search query. This tool cannot edit, approve, archive, or export content."
    parameters = {"type": "object", "properties": {"name": {"type": "string"}, "query": {"type": "string"},
                  "limit": {"type": "integer", "minimum": 1, "maximum": 20}}, "additionalProperties": False}

    def __init__(self, service: ContentWorkflowService):
        self.service = service

    def definition(self) -> ToolDefinition:
        return ToolDefinition(self.name, self.description, self.parameters)

    def run(self, arguments: dict[str, Any]) -> Any:
        if not isinstance(arguments, dict) or set(arguments) - {"name", "query", "limit"}:
            raise ContentWorkflowError("Unsupported content search fields")
        if arguments.get("name") and arguments.get("query"):
            raise ContentWorkflowError("Use either name or query")
        if arguments.get("name"):
            return self.service.get(str(arguments["name"]))
        return {"items": self.service.search(str(arguments.get("query", "")), limit=int(arguments.get("limit", 10)))}
