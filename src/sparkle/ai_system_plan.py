from __future__ import annotations

import hashlib
import json
from pathlib import Path, PurePosixPath
from typing import Any

from sparkle.ai_system_builder import AISystemBlueprint, AISystemBlueprintBuilder
from sparkle.builders import WorkspaceManager
from sparkle.config import data_root
from sparkle.storage import SQLiteStore, utc_now


class AISystemImplementationPlanStore(SQLiteStore):
    """Content-free evidence for implementation-plan materialization attempts."""

    MAX_RECORDS = 1_000

    def __init__(self, path: Path | None = None):
        super().__init__(
            path
            or data_root()
            / "data_environment"
            / "ai_system_implementation_plans.sqlite3"
        )
        self.initialize()

    def initialize(self) -> None:
        with self.connect() as connection:
            connection.execute("""
                CREATE TABLE IF NOT EXISTS ai_system_implementation_plans (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    system_name TEXT NOT NULL,
                    blueprint_sha256 TEXT NOT NULL,
                    plan_sha256 TEXT NOT NULL,
                    plan_bytes INTEGER NOT NULL,
                    status TEXT NOT NULL,
                    workspace_build_id INTEGER,
                    error_type TEXT,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                )
            """)
            columns = {
                row["name"] for row in connection.execute(
                    "PRAGMA table_info(ai_system_implementation_plans)"
                ).fetchall()
            }
            migrations = {
                "review_status": "TEXT NOT NULL DEFAULT 'human_review_required'",
                "reviewed_at": "TEXT",
            }
            for name, definition in migrations.items():
                if name not in columns:
                    connection.execute(
                        "ALTER TABLE ai_system_implementation_plans "
                        f"ADD COLUMN {name} {definition}"
                    )

    @staticmethod
    def _digest(value: Any, *, field: str) -> str:
        if (
            not isinstance(value, str)
            or len(value) != 64
            or any(character not in "0123456789abcdef" for character in value)
        ):
            raise ValueError(f"AI system implementation-plan {field} is invalid")
        return value

    def create(
        self,
        *,
        system_name: str,
        blueprint_sha256: str,
        plan_sha256: str,
        plan_bytes: int,
    ) -> int:
        if WorkspaceManager.NAME_PATTERN.fullmatch(system_name) is None:
            raise ValueError("AI system implementation-plan name is invalid")
        if (
            not isinstance(plan_bytes, int)
            or isinstance(plan_bytes, bool)
            or not 1 <= plan_bytes <= AISystemImplementationPlanner.MAX_PLAN_BYTES
        ):
            raise ValueError("AI system implementation-plan size is invalid")
        now = utc_now()
        with self.connect() as connection:
            cursor = connection.execute("""
                INSERT INTO ai_system_implementation_plans(
                    system_name, blueprint_sha256, plan_sha256, plan_bytes,
                    status, workspace_build_id, error_type, created_at, updated_at
                ) VALUES(?,?,?,?,'materializing',NULL,NULL,?,?)
            """, (
                system_name,
                self._digest(blueprint_sha256, field="blueprint digest"),
                self._digest(plan_sha256, field="plan digest"),
                plan_bytes,
                now,
                now,
            ))
            connection.execute("""
                DELETE FROM ai_system_implementation_plans WHERE id NOT IN (
                    SELECT id FROM ai_system_implementation_plans
                    ORDER BY id DESC LIMIT ?
                )
            """, (self.MAX_RECORDS,))
        return int(cursor.lastrowid)

    def finish(
        self,
        plan_id: int,
        *,
        status: str,
        workspace_build_id: int | None = None,
        error_type: str | None = None,
    ) -> None:
        if status not in {
            "materialized_static_verified",
            "materialization_failed",
        }:
            raise ValueError("Unsupported AI system implementation-plan status")
        if error_type is not None and (
            not isinstance(error_type, str) or not 1 <= len(error_type) <= 128
        ):
            raise ValueError("AI system implementation-plan error type is invalid")
        with self.connect() as connection:
            cursor = connection.execute("""
                UPDATE ai_system_implementation_plans
                SET status=?, workspace_build_id=?, error_type=?, updated_at=?
                WHERE id=? AND status='materializing'
            """, (
                status,
                workspace_build_id,
                error_type,
                utc_now(),
                plan_id,
            ))
        if cursor.rowcount != 1:
            raise RuntimeError("AI system implementation-plan transition failed")

    def list(self, *, limit: int = 50) -> list[dict[str, Any]]:
        with self.connect() as connection:
            rows = connection.execute("""
                SELECT * FROM ai_system_implementation_plans
                ORDER BY id DESC LIMIT ?
            """, (max(1, min(limit, 100)),)).fetchall()
        return [self._public(row) for row in rows]

    def get(self, plan_id: int) -> dict[str, Any]:
        if not isinstance(plan_id, int) or isinstance(plan_id, bool) or plan_id < 1:
            raise ValueError("AI system implementation-plan ID is invalid")
        with self.connect() as connection:
            row = connection.execute(
                "SELECT * FROM ai_system_implementation_plans WHERE id=?",
                (plan_id,),
            ).fetchone()
        if row is None:
            raise KeyError("AI system implementation plan does not exist")
        return self._public(row)

    def approve_for_generation(self, plan_id: int, *, approved: bool) -> dict[str, Any]:
        if approved is not True:
            raise ValueError(
                "AI system implementation-plan review requires explicit approval"
            )
        now = utc_now()
        with self.connect() as connection:
            cursor = connection.execute("""
                UPDATE ai_system_implementation_plans
                SET review_status='approved_for_generation', reviewed_at=?,
                    updated_at=?
                WHERE id=? AND status='materialized_static_verified'
                  AND review_status='human_review_required'
            """, (now, now, plan_id))
        if cursor.rowcount != 1:
            record = self.get(plan_id)
            if record["review_status"] == "approved_for_generation":
                raise ValueError("AI system implementation plan is already approved")
            raise ValueError(
                "Only a materialized implementation plan can be approved"
            )
        return self.get(plan_id)

    @staticmethod
    def _public(row: Any) -> dict[str, Any]:
        reviewed = row["review_status"] == "approved_for_generation"
        return {
            "plan_id": row["id"],
            "system_name": row["system_name"],
            "blueprint_sha256": row["blueprint_sha256"],
            "plan_sha256": row["plan_sha256"],
            "plan_bytes": row["plan_bytes"],
            "status": row["status"],
            "workspace_build_id": row["workspace_build_id"],
            "error_type": row["error_type"],
            "review_status": row["review_status"],
            "human_review_completed": reviewed,
            "approved_for_source_generation": reviewed,
            "source_generation_executed": False,
            "runtime_evaluation_executed": False,
            "external_deployment_executed": False,
            "reviewed_at": row["reviewed_at"],
            "created_at": row["created_at"],
            "updated_at": row["updated_at"],
        }


class AISystemImplementationPlanner:
    """Derive a deterministic, reviewable plan without generating source code."""

    PROTOCOL = "SPARKLE-AI-SYSTEM-IMPLEMENTATION-PLAN/1"
    MAX_PLAN_BYTES = 128_000
    PLAN_FILENAME = "SPARKLE_IMPLEMENTATION_PLAN.json"

    def __init__(
        self,
        builder: AISystemBlueprintBuilder,
        workspaces: WorkspaceManager,
        store: AISystemImplementationPlanStore,
    ):
        self.builder = builder
        self.workspaces = workspaces
        self.store = store

    @staticmethod
    def _canonical(value: dict[str, Any]) -> bytes:
        return (
            json.dumps(
                value,
                ensure_ascii=False,
                separators=(",", ":"),
                sort_keys=True,
                allow_nan=False,
            )
            + "\n"
        ).encode("utf-8")

    @staticmethod
    def _evaluation_paths(blueprint: AISystemBlueprint) -> dict[str, str]:
        normalized = {
            evaluation.name: evaluation.name.replace("-", "_")
            for evaluation in blueprint.evaluations
        }
        counts = {
            value: sum(1 for candidate in normalized.values() if candidate == value)
            for value in set(normalized.values())
        }
        return {
            name: (
                f"tests/test_{value}.py"
                if counts[value] == 1
                else "tests/test_"
                + value
                + "_"
                + hashlib.sha256(name.encode("utf-8")).hexdigest()[:8]
                + ".py"
            )
            for name, value in normalized.items()
        }

    @classmethod
    def _proposed_files(cls, blueprint: AISystemBlueprint) -> list[dict[str, str]]:
        package = f"src/{blueprint.name.replace('-', '_')}"
        evaluation_paths = cls._evaluation_paths(blueprint)
        files = [
            {
                "path": f"{package}/__init__.py",
                "kind": "python_module",
                "responsibility": "Expose the composed AI system public boundary.",
            },
            {
                "path": f"{package}/contracts.py",
                "kind": "python_module",
                "responsibility": (
                    "Define provider-neutral request, result, and evaluation contracts."
                ),
            },
            {
                "path": f"{package}/system.py",
                "kind": "python_module",
                "responsibility": (
                    "Compose declared model capabilities, agents, tools, and data boundaries."
                ),
            },
        ]
        files.extend({
            "path": f"{package}/interfaces/{interface}.py",
            "kind": "interface_adapter",
            "responsibility": (
                f"Implement the provider-neutral {interface} interface boundary."
            ),
        } for interface in sorted(blueprint.interfaces))
        files.extend({
            "path": evaluation_paths[evaluation.name],
            "kind": "evaluation",
            "responsibility": (
                f"Implement the declared {evaluation.kind} acceptance contract."
            ),
        } for evaluation in sorted(blueprint.evaluations, key=lambda item: item.name))
        return files

    @classmethod
    def _validate_plan(cls, plan: dict[str, Any]) -> None:
        encoded = cls._canonical(plan)
        if len(encoded) > cls.MAX_PLAN_BYTES:
            raise ValueError("AI system implementation plan exceeds 128000 bytes")
        files = plan.get("proposed_source_files")
        if not isinstance(files, list) or not 4 <= len(files) <= 50:
            raise ValueError("AI system implementation plan file count is invalid")
        paths: list[str] = []
        for item in files:
            if not isinstance(item, dict) or set(item) != {
                "path", "kind", "responsibility",
            }:
                raise ValueError("AI system implementation plan file is invalid")
            path = item["path"]
            if not isinstance(path, str):
                raise ValueError("AI system implementation plan path is invalid")
            parsed = PurePosixPath(path)
            if (
                parsed.is_absolute()
                or any(part in {"", ".", ".."} for part in parsed.parts)
                or "\\" in path
                or "\0" in path
                or len(path) > 240
            ):
                raise ValueError("AI system implementation plan path is invalid")
            paths.append(path)
        if len(paths) != len(set(paths)):
            raise ValueError("AI system implementation plan paths must be unique")

    def prepare(self, requirements: dict[str, Any]) -> dict[str, Any]:
        blueprint = self.builder.prepare(requirements)
        blueprint_value = blueprint.to_dict()
        blueprint_sha256 = hashlib.sha256(
            self._canonical(blueprint_value)
        ).hexdigest()
        proposed_files = self._proposed_files(blueprint)
        evaluation_paths_by_name = self._evaluation_paths(blueprint)
        interface_paths = [
            item["path"]
            for item in proposed_files
            if item["kind"] == "interface_adapter"
        ]
        evaluation_paths = [
            item["path"]
            for item in proposed_files
            if item["kind"] == "evaluation"
        ]
        plan: dict[str, Any] = {
            "protocol_version": self.PROTOCOL,
            "system_name": blueprint.name,
            "blueprint_protocol_version": blueprint.protocol_version,
            "blueprint_sha256": blueprint_sha256,
            "architecture_inputs": {
                "model_requirements": [
                    {
                        "capability": route.capability,
                        "modalities": list(route.modalities),
                    }
                    for route in blueprint.model_routes
                ],
                "agents": list(blueprint.agents),
                "tools": list(blueprint.tools),
                "data_environments": list(blueprint.data_environments),
                "interfaces": list(blueprint.interfaces),
            },
            "proposed_source_files": proposed_files,
            "work_items": [
                {
                    "id": "contract_review",
                    "depends_on": [],
                    "outputs": [],
                    "acceptance": list(blueprint.static_checks),
                },
                {
                    "id": "core_composition",
                    "depends_on": ["contract_review"],
                    "outputs": [item["path"] for item in proposed_files[:3]],
                    "acceptance": [
                        "provider_neutral_model_routing",
                        "agent_tool_allowlists",
                        "data_environment_separation",
                    ],
                },
                {
                    "id": "interface_adapters",
                    "depends_on": ["core_composition"],
                    "outputs": interface_paths,
                    "acceptance": ["declared_interfaces_covered"],
                },
                {
                    "id": "evaluation_harness",
                    "depends_on": ["core_composition", "interface_adapters"],
                    "outputs": evaluation_paths,
                    "acceptance": ["declared_evaluations_covered"],
                },
                {
                    "id": "release_review",
                    "depends_on": ["evaluation_harness"],
                    "outputs": [],
                    "acceptance": [
                        "human_source_review",
                        "static_verification_passed",
                        "fixed_tests_passed",
                        "deployment_adapter_verified",
                    ],
                },
            ],
            "evaluation_plan": [
                {
                    **evaluation.to_dict(),
                    "proposed_test_path": evaluation_paths_by_name[evaluation.name],
                    "status": "planned_unverified",
                }
                for evaluation in sorted(
                    blueprint.evaluations, key=lambda item: item.name,
                )
            ],
            "deployment_review": {
                **blueprint.deployment,
                "required_prior_work_item": "release_review",
                "external_action_executed": False,
            },
            "static_checks": [
                "blueprint_revalidated",
                "provider_neutral_routes",
                "proposed_paths_confined",
                "proposed_paths_unique",
                "declared_interfaces_covered",
                "declared_evaluations_covered",
                "work_item_dependencies_acyclic",
            ],
            "status": "prepared_static_verified",
            "plan_digest_scope": "canonical_plan_without_plan_sha256",
            "human_review_required": True,
            "human_review_completed": False,
            "generated_source_files": [],
            "source_generation_executed": False,
            "runtime_evaluation_executed": False,
            "external_deployment_executed": False,
        }
        self._validate_plan(plan)
        plan["plan_sha256"] = hashlib.sha256(self._canonical(plan)).hexdigest()
        return plan

    def materialize(
        self,
        requirements: dict[str, Any],
        *,
        approved: bool,
    ) -> dict[str, Any]:
        if approved is not True:
            raise ValueError(
                "AI system implementation-plan materialization requires explicit approval"
            )
        plan = self.prepare(requirements)
        manifest = self._canonical(plan)
        plan_id = self.store.create(
            system_name=plan["system_name"],
            blueprint_sha256=plan["blueprint_sha256"],
            plan_sha256=plan["plan_sha256"],
            plan_bytes=len(manifest),
        )
        try:
            build = self.workspaces.scaffold(
                plan["system_name"],
                {self.PLAN_FILENAME: manifest.decode("utf-8")},
                overwrite=False,
            )
        except Exception as exc:
            self.store.finish(
                plan_id,
                status="materialization_failed",
                error_type=type(exc).__name__[:128],
            )
            raise
        self.store.finish(
            plan_id,
            status="materialized_static_verified",
            workspace_build_id=build["build_id"],
        )
        return {
            **plan,
            "plan_id": plan_id,
            "workspace_build_id": build["build_id"],
            "workspace": build["workspace"],
            "files": build["files"],
            "status": "materialized_static_verified",
            "plan_materialization_approved": True,
        }
