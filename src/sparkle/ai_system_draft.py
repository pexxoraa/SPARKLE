from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

from sparkle.ai_system_builder import AISystemBlueprintBuilder
from sparkle.config import data_root
from sparkle.orchestrator import Orchestrator
from sparkle.storage import SQLiteStore, utc_now


class AISystemDraftStore(SQLiteStore):
    """Bounded, content-free evidence for natural-language draft attempts."""

    MAX_RECORDS = 1_000

    def __init__(self, path: Path | None = None):
        super().__init__(
            path or data_root() / "data_environment" / "ai_system_drafts.sqlite3"
        )
        self.initialize()

    def initialize(self) -> None:
        with self.connect() as connection:
            connection.execute("""
                CREATE TABLE IF NOT EXISTS ai_system_drafts (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    status TEXT NOT NULL,
                    request_bytes INTEGER NOT NULL,
                    response_sha256 TEXT,
                    response_chars INTEGER NOT NULL,
                    provider TEXT,
                    model TEXT,
                    trace_id TEXT,
                    error_type TEXT,
                    created_at TEXT NOT NULL
                )
            """)

    def save(self, value: dict[str, Any]) -> int:
        status = value.get("status")
        if status not in {"draft_static_verified", "draft_failed"}:
            raise ValueError("AI system draft status is invalid")
        request_bytes = value.get("request_bytes")
        response_chars = value.get("response_chars")
        if (
            not isinstance(request_bytes, int)
            or isinstance(request_bytes, bool)
            or not 1 <= request_bytes <= AISystemRequirementsCompiler.MAX_INPUT_BYTES
            or not isinstance(response_chars, int)
            or isinstance(response_chars, bool)
            or not 0 <= response_chars <= AISystemRequirementsCompiler.MAX_RESPONSE_CHARS
        ):
            raise ValueError("AI system draft evidence bounds are invalid")
        response_sha256 = value.get("response_sha256")
        if response_sha256 is not None and (
            not isinstance(response_sha256, str)
            or len(response_sha256) != 64
            or any(character not in "0123456789abcdef" for character in response_sha256)
        ):
            raise ValueError("AI system draft response digest is invalid")
        bounded: dict[str, str | None] = {}
        for field, maximum in (
            ("provider", 128), ("model", 128), ("trace_id", 128),
            ("error_type", 128),
        ):
            item = value.get(field)
            if item is not None and (
                not isinstance(item, str) or not item or len(item) > maximum
            ):
                raise ValueError(f"AI system draft {field} is invalid")
            bounded[field] = item
        with self.connect() as connection:
            cursor = connection.execute("""
                INSERT INTO ai_system_drafts(
                    status, request_bytes, response_sha256, response_chars,
                    provider, model, trace_id, error_type, created_at
                ) VALUES(?,?,?,?,?,?,?,?,?)
            """, (
                status, request_bytes, response_sha256, response_chars,
                bounded["provider"], bounded["model"], bounded["trace_id"],
                bounded["error_type"], utc_now(),
            ))
            connection.execute("""
                DELETE FROM ai_system_drafts WHERE id NOT IN (
                    SELECT id FROM ai_system_drafts ORDER BY id DESC LIMIT ?
                )
            """, (self.MAX_RECORDS,))
        return int(cursor.lastrowid)

    def list(self, *, limit: int = 50) -> list[dict[str, Any]]:
        with self.connect() as connection:
            rows = connection.execute("""
                SELECT * FROM ai_system_drafts ORDER BY id DESC LIMIT ?
            """, (max(1, min(limit, 100)),)).fetchall()
        return [
            {
                "draft_id": row["id"],
                "status": row["status"],
                "request_bytes": row["request_bytes"],
                "response_sha256": row["response_sha256"],
                "response_chars": row["response_chars"],
                "provider": row["provider"],
                "model": row["model"],
                "trace_id": row["trace_id"],
                "error_type": row["error_type"],
                "natural_language_conversion_attempted": True,
                "semantic_correctness_verified": False,
                "live_provider_verified": False,
                "external_deployment_executed": False,
                "created_at": row["created_at"],
            }
            for row in rows
        ]


class AISystemRequirementsCompiler:
    """Convert bounded natural language into a strictly validated draft."""

    PROTOCOL = "SPARKLE-AI-SYSTEM-DRAFT/1"
    MAX_INPUT_BYTES = 20_000
    MAX_RESPONSE_CHARS = 64_000

    def __init__(
        self,
        builder: AISystemBlueprintBuilder,
        orchestrator: Orchestrator,
        store: AISystemDraftStore,
    ):
        self.builder = builder
        self.orchestrator = orchestrator
        self.store = store

    @staticmethod
    def _unique_object(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
        result: dict[str, Any] = {}
        for key, value in pairs:
            if key in result:
                raise ValueError(f"Generated AI system JSON contains duplicate key: {key}")
            result[key] = value
        return result

    def _prompt(self, requirements_text: str) -> str:
        contract = self.builder.requirements_contract()
        return (
            "Convert the user's bounded natural-language request into exactly one "
            "JSON object for SPARKLE-AI-SYSTEM-BLUEPRINT/1. Return JSON only: no "
            "Markdown, commentary, code fences, provider names, credentials, or "
            "extra fields. Use only values allowed by this contract. Every tool "
            "must be available to at least one selected agent. Deployment is a "
            "plan, never a claim of execution.\n\nContract:\n"
            + json.dumps(contract, ensure_ascii=False, separators=(",", ":"), sort_keys=True)
            + "\n\nUser requirements:\n"
            + requirements_text
        )

    def compile(self, requirements_text: str, *, approved: bool) -> dict[str, Any]:
        if approved is not True:
            raise ValueError(
                "AI system natural-language conversion requires explicit approval"
            )
        if not isinstance(requirements_text, str):
            raise ValueError("AI system natural-language requirements must be text")
        normalized = requirements_text.strip()
        request_bytes = len(normalized.encode("utf-8"))
        if not 20 <= request_bytes <= self.MAX_INPUT_BYTES:
            raise ValueError(
                "AI system natural-language requirements must contain 20-20000 bytes"
            )

        result = None
        response_text = ""
        try:
            result = self.orchestrator.run(
                self._prompt(normalized),
                agent_name="application_builder",
                input_source="ai_system_draft",
                execution_profile="evaluation",
            )
            response_text = result.text
            if len(response_text) > self.MAX_RESPONSE_CHARS:
                raise ValueError("Generated AI system requirements exceed 64000 characters")
            try:
                requirements = json.loads(
                    response_text, object_pairs_hook=self._unique_object,
                )
            except json.JSONDecodeError as exc:
                raise ValueError("Generated AI system requirements are not exact JSON") from exc
            if not isinstance(requirements, dict):
                raise ValueError("Generated AI system requirements must be a JSON object")
            blueprint = self.builder.prepare(requirements).to_dict()
            evidence = {
                "status": "draft_static_verified",
                "request_bytes": request_bytes,
                "response_sha256": hashlib.sha256(
                    response_text.encode("utf-8")
                ).hexdigest(),
                "response_chars": len(response_text),
                "provider": result.provider[:128],
                "model": result.model[:128],
                "trace_id": result.trace_id[:128],
                "error_type": None,
            }
            draft_id = self.store.save(evidence)
        except Exception as exc:
            self.store.save({
                "status": "draft_failed",
                "request_bytes": request_bytes,
                "response_sha256": (
                    hashlib.sha256(response_text.encode("utf-8")).hexdigest()
                    if response_text else None
                ),
                "response_chars": len(response_text),
                "provider": result.provider[:128] if result is not None else None,
                "model": result.model[:128] if result is not None else None,
                "trace_id": result.trace_id[:128] if result is not None else None,
                "error_type": type(exc).__name__[:128],
            })
            raise

        return {
            "protocol_version": self.PROTOCOL,
            "draft_id": draft_id,
            "status": "draft_static_verified",
            "requirements": requirements,
            "blueprint": blueprint,
            "provider": result.provider,
            "model": result.model,
            "trace_id": result.trace_id,
            "model_call_executed": True,
            "natural_language_conversion_executed": True,
            "schema_validation_executed": True,
            "semantic_correctness_verified": False,
            "live_provider_verified": False,
            "runtime_evaluation_executed": False,
            "external_deployment_executed": False,
        }
