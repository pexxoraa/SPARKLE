from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

from sparkle.agent_builder import (
    AgentBlueprintBuilder,
    AgentBlueprintStore,
    AgentResponseAssertions,
)
from sparkle.config import data_root
from sparkle.orchestrator import Orchestrator
from sparkle.storage import SQLiteStore, utc_now


class AgentEvaluationStore(SQLiteStore):
    MAX_RECORDS = 1_000

    def __init__(self, path: Path | None = None):
        super().__init__(
            path or data_root() / "data_environment" / "agent_evaluations.sqlite3"
        )
        self.initialize()

    def initialize(self) -> None:
        with self.connect() as connection:
            connection.execute("""
                CREATE TABLE IF NOT EXISTS agent_evaluations (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    blueprint_id INTEGER NOT NULL,
                    agent_name TEXT NOT NULL,
                    status TEXT NOT NULL,
                    case_count INTEGER NOT NULL,
                    passed_count INTEGER NOT NULL,
                    failed_count INTEGER NOT NULL,
                    cases_json TEXT NOT NULL,
                    providers_json TEXT NOT NULL,
                    models_json TEXT NOT NULL,
                    trace_ids_json TEXT NOT NULL,
                    created_at TEXT NOT NULL
                )
            """)

    def save(self, value: dict[str, Any]) -> int:
        cases = value.get("cases")
        providers = value.get("providers")
        models = value.get("models")
        trace_ids = value.get("trace_ids")
        for label, collection, maximum in (
            ("cases", cases, 20),
            ("providers", providers, 20),
            ("models", models, 20),
            ("trace IDs", trace_ids, 20),
        ):
            if not isinstance(collection, list) or len(collection) > maximum:
                raise ValueError(f"Agent evaluation {label} are invalid")
        encoded_cases = json.dumps(
            cases, ensure_ascii=False, separators=(",", ":"),
            sort_keys=True, allow_nan=False,
        )
        if len(encoded_cases.encode("utf-8")) > 64_000:
            raise ValueError("Agent evaluation case evidence is too large")
        encoded_providers = json.dumps(
            providers, ensure_ascii=False, separators=(",", ":"), sort_keys=True,
        )
        encoded_models = json.dumps(
            models, ensure_ascii=False, separators=(",", ":"), sort_keys=True,
        )
        encoded_traces = json.dumps(
            trace_ids, ensure_ascii=False, separators=(",", ":"), sort_keys=True,
        )
        with self.connect() as connection:
            cursor = connection.execute("""
                INSERT INTO agent_evaluations(
                    blueprint_id, agent_name, status, case_count,
                    passed_count, failed_count, cases_json, providers_json,
                    models_json, trace_ids_json, created_at
                ) VALUES(?,?,?,?,?,?,?,?,?,?,?)
            """, (
                value["blueprint_id"], value["agent_name"], value["status"],
                value["case_count"], value["passed_count"],
                value["failed_count"], encoded_cases, encoded_providers,
                encoded_models, encoded_traces, utc_now(),
            ))
            connection.execute("""
                DELETE FROM agent_evaluations WHERE id NOT IN (
                    SELECT id FROM agent_evaluations
                    ORDER BY id DESC LIMIT ?
                )
            """, (self.MAX_RECORDS,))
        return int(cursor.lastrowid)

    def list(self, *, limit: int = 50) -> list[dict[str, Any]]:
        with self.connect() as connection:
            rows = connection.execute("""
                SELECT * FROM agent_evaluations
                ORDER BY id DESC LIMIT ?
            """, (max(1, min(limit, 100)),)).fetchall()
        return [
            {
                "evaluation_id": row["id"],
                "blueprint_id": row["blueprint_id"],
                "agent_name": row["agent_name"],
                "status": row["status"],
                "case_count": row["case_count"],
                "passed_count": row["passed_count"],
                "failed_count": row["failed_count"],
                "cases": json.loads(row["cases_json"]),
                "providers": json.loads(row["providers_json"]),
                "models": json.loads(row["models_json"]),
                "trace_ids": json.loads(row["trace_ids_json"]),
                "response_contract_evaluation_executed": True,
                "semantic_evaluation_executed": False,
                "live_provider_verified": False,
                "external_deployment_executed": False,
                "created_at": row["created_at"],
            }
            for row in rows
        ]


class AgentResponseEvaluator:
    PROTOCOL = "SPARKLE-AGENT-EVALUATION/1"

    def __init__(
        self,
        builder: AgentBlueprintBuilder,
        blueprints: AgentBlueprintStore,
        orchestrator: Orchestrator,
        store: AgentEvaluationStore,
    ):
        self.builder = builder
        self.blueprints = blueprints
        self.orchestrator = orchestrator
        self.store = store

    @staticmethod
    def _checks(
        response: str, assertions: AgentResponseAssertions,
    ) -> list[dict[str, object]]:
        folded = response.casefold()
        checks: list[dict[str, object]] = []
        if assertions.contains_all:
            checks.append({
                "check": "contains_all",
                "passed": all(item.casefold() in folded for item in assertions.contains_all),
            })
        if assertions.contains_any:
            checks.append({
                "check": "contains_any",
                "passed": any(item.casefold() in folded for item in assertions.contains_any),
            })
        if assertions.excludes_all:
            checks.append({
                "check": "excludes_all",
                "passed": all(item.casefold() not in folded for item in assertions.excludes_all),
            })
        if assertions.min_chars is not None:
            checks.append({
                "check": "min_chars",
                "passed": len(response) >= assertions.min_chars,
            })
        if assertions.max_chars is not None:
            checks.append({
                "check": "max_chars",
                "passed": len(response) <= assertions.max_chars,
            })
        return checks

    def evaluate(self, agent_name: str, *, approved: bool) -> dict[str, Any]:
        if approved is not True:
            raise ValueError("Agent response evaluation requires explicit approval")
        if not isinstance(agent_name, str):
            raise ValueError("Agent response evaluation name must be a string")
        blueprint_id, requirements = self.blueprints.latest_requirements(agent_name)
        blueprint = self.builder.validate_installed(requirements)
        if any(case.assertions is None for case in blueprint.evaluations):
            raise ValueError(
                "Every Agent Blueprint evaluation requires response assertions"
            )

        cases: list[dict[str, Any]] = []
        providers: set[str] = set()
        models: set[str] = set()
        trace_ids: list[str] = []
        for case in blueprint.evaluations:
            try:
                result = self.orchestrator.run(
                    case.prompt,
                    agent_name=blueprint.manifest.name,
                    input_source="agent_evaluation",
                    execution_profile="evaluation",
                )
                assertions = case.assertions
                if assertions is None:  # guarded above; keeps type narrowing explicit
                    raise RuntimeError("Agent evaluation assertions are unavailable")
                checks = self._checks(result.text, assertions)
                passed = bool(checks) and all(
                    bool(check["passed"]) for check in checks
                )
                providers.add(result.provider[:128])
                models.add(result.model[:128])
                trace_ids.append(result.trace_id)
                cases.append({
                    "name": case.name,
                    "passed": passed,
                    "checks": checks,
                    "response_sha256": hashlib.sha256(
                        result.text.encode("utf-8")
                    ).hexdigest(),
                    "response_chars": len(result.text),
                    "trace_id": result.trace_id,
                    "provider": result.provider[:128],
                    "model": result.model[:128],
                    "error_type": None,
                })
            except Exception as exc:
                cases.append({
                    "name": case.name,
                    "passed": False,
                    "checks": [],
                    "response_sha256": None,
                    "response_chars": 0,
                    "trace_id": None,
                    "provider": None,
                    "model": None,
                    "error_type": type(exc).__name__,
                })

        passed_count = sum(1 for case in cases if case["passed"])
        value = {
            "protocol_version": self.PROTOCOL,
            "blueprint_id": blueprint_id,
            "agent_name": blueprint.manifest.name,
            "status": "passed" if passed_count == len(cases) else "failed",
            "case_count": len(cases),
            "passed_count": passed_count,
            "failed_count": len(cases) - passed_count,
            "cases": cases,
            "providers": sorted(providers),
            "models": sorted(models),
            "trace_ids": trace_ids,
            "response_contract_evaluation_executed": True,
            "semantic_evaluation_executed": False,
            "live_provider_verified": False,
            "external_deployment_executed": False,
        }
        value["evaluation_id"] = self.store.save(value)
        return value
