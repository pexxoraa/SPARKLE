from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

from sparkle.api import serve
from sparkle.contracts import Message, ModelRequest
from sparkle.model import ModelError
from sparkle.external_worker import ExternalWorkerError
from sparkle.secrets import SecretNotFoundError
from sparkle.system import SparkleSystem
from sparkle.tooling import ToolError


def _print(value: object) -> None:
    print(json.dumps(value, indent=2, ensure_ascii=False, default=str))


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="sparkle", description="SPARKLE personal AI system")
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("status", help="Show component and secret-presence status")
    serve_parser = sub.add_parser("serve", help="Start the API and dashboard")
    serve_parser.add_argument("--host")
    serve_parser.add_argument("--port", type=int)
    chat = sub.add_parser("chat", help="Run a text request")
    chat.add_argument("message")
    chat.add_argument("--agent")
    chat.add_argument("--multi", action="store_true")
    smoke = sub.add_parser("smoke-test", help="Verify configuration or make a safe live provider call")
    smoke.add_argument("--live", action="store_true")
    memory = sub.add_parser("remember", help="Store an explicit durable memory")
    memory.add_argument("category")
    memory.add_argument("key")
    memory.add_argument("value")
    knowledge = sub.add_parser("ingest", help="Ingest a UTF-8 text or Markdown file")
    knowledge.add_argument("path")
    knowledge.add_argument("--title")
    knowledge.add_argument(
        "--monitor-key",
        help="Track later revisions under a safe 1-64 character research key",
    )
    agent_install = sub.add_parser("agent-install", help="Install a generated agent manifest")
    agent_install.add_argument("manifest")
    agent_install.add_argument("--approve", action="store_true")
    agent_install.add_argument("--replace", action="store_true")
    agent_remove = sub.add_parser("agent-remove", help="Remove a generated agent")
    agent_remove.add_argument("name")
    agent_remove.add_argument("--approve", action="store_true")
    agent_prepare = sub.add_parser(
        "agent-prepare",
        help="Validate structured requirements and generate an agent blueprint",
    )
    agent_prepare.add_argument("requirements")
    agent_build = sub.add_parser(
        "agent-build",
        help="Generate, statically verify, and install an agent blueprint",
    )
    agent_build.add_argument("requirements")
    agent_build.add_argument("--approve", action="store_true")
    agent_evaluate = sub.add_parser(
        "agent-evaluate",
        help="Run approved response-contract fixtures for an installed blueprint",
    )
    agent_evaluate.add_argument("name")
    agent_evaluate.add_argument("--approve", action="store_true")
    ai_system_prepare = sub.add_parser(
        "ai-system-prepare",
        help="Validate structured requirements and generate an AI system blueprint",
    )
    ai_system_prepare.add_argument("requirements")
    ai_system_draft = sub.add_parser(
        "ai-system-draft",
        help="Convert approved natural-language requirements into a validated draft",
    )
    ai_system_draft.add_argument("requirements_text")
    ai_system_draft.add_argument("--approve", action="store_true")
    ai_system_build = sub.add_parser(
        "ai-system-build",
        help="Generate and materialize a statically verified AI system scaffold",
    )
    ai_system_build.add_argument("requirements")
    ai_system_build.add_argument("--approve", action="store_true")
    ai_system_plan = sub.add_parser(
        "ai-system-plan",
        help="Derive a deterministic human-reviewable implementation plan",
    )
    ai_system_plan.add_argument("requirements")
    ai_system_plan_build = sub.add_parser(
        "ai-system-plan-build",
        help="Materialize an approved AI system implementation plan",
    )
    ai_system_plan_build.add_argument("requirements")
    ai_system_plan_build.add_argument("--approve", action="store_true")
    ai_system_plan_review = sub.add_parser(
        "ai-system-plan-review",
        help="Approve a reviewed implementation plan for candidate generation",
    )
    ai_system_plan_review.add_argument("plan_id", type=int)
    ai_system_plan_review.add_argument("--approve", action="store_true")
    source_disclose = sub.add_parser(
        "ai-system-source-disclose",
        help="Create a provider disclosure for an approved implementation plan",
    )
    source_disclose.add_argument("plan_id", type=int)
    source_disclose.add_argument("requirements")
    source_disclose.add_argument("generation_task")
    source_disclosure_approve = sub.add_parser(
        "ai-system-source-disclosure-approve",
        help="Approve disclosed provider metadata before generation",
    )
    source_disclosure_approve.add_argument("disclosure_id", type=int)
    source_disclosure_approve.add_argument("--approve", action="store_true")
    source_generate = sub.add_parser(
        "ai-system-source-generate",
        help="Generate an isolated bounded source candidate",
    )
    source_generate.add_argument("plan_id", type=int)
    source_generate.add_argument("disclosure_id", type=int)
    source_generate.add_argument("requirements")
    source_generate.add_argument("--approve", action="store_true")
    source_review = sub.add_parser(
        "ai-system-source-review",
        help="Record an explicit human review decision",
    )
    source_review.add_argument("candidate_id", type=int)
    source_review.add_argument("decision", choices=("accept", "reject"))
    source_review.add_argument("notes")
    source_review.add_argument("--approve", action="store_true")
    source_verify = sub.add_parser(
        "ai-system-source-verify",
        help="Run non-executing static candidate verification",
    )
    source_verify.add_argument("candidate_id", type=int)
    source_verify.add_argument("requirements")
    source_approve = sub.add_parser(
        "ai-system-source-approve",
        help="Approve a human-reviewed statically verified candidate",
    )
    source_approve.add_argument("candidate_id", type=int)
    source_approve.add_argument("--approve", action="store_true")
    source_file = sub.add_parser(
        "ai-system-source-file",
        help="Read one declared candidate file for human review",
    )
    source_file.add_argument("candidate_id", type=int)
    source_file.add_argument("path")
    sub.add_parser(
        "ai-system-source-candidates", help="List source candidate evidence",
    )
    sub.add_parser(
        "ai-system-source-disclosures", help="List provider disclosures",
    )
    runtime_evaluate = sub.add_parser(
        "ai-system-runtime-evaluate",
        help="Submit an approved candidate evaluation to the configured worker",
    )
    runtime_evaluate.add_argument("contract")
    runtime_evaluate.add_argument("--approve", action="store_true")
    sub.add_parser(
        "ai-system-runtime-evaluations",
        help="List content-free runtime evaluation evidence",
    )
    promotion_approve = sub.add_parser(
        "ai-system-promotion-approve",
        help="Approve one evaluated candidate for controlled staging promotion",
    )
    promotion_approve.add_argument("candidate_id", type=int)
    promotion_approve.add_argument("evaluation_id")
    promotion_approve.add_argument("actor")
    promotion_approve.add_argument(
        "--source-origin", choices=("cli", "operator"), default="cli",
    )
    promotion_approve.add_argument("--approve", action="store_true")
    promote = sub.add_parser(
        "ai-system-promote",
        help="Promote exact approved candidate source into controlled staging",
    )
    promote.add_argument("contract")
    promote.add_argument("--approve", action="store_true")
    promotion_exclude = sub.add_parser(
        "ai-system-promotion-exclude",
        help="Invalidate or supersede a candidate for promotion",
    )
    promotion_exclude.add_argument("candidate_id", type=int)
    promotion_exclude.add_argument("status", choices=("invalidated", "superseded"))
    promotion_exclude.add_argument("reason")
    promotion_exclude.add_argument("actor")
    promotion_exclude.add_argument("--replacement-candidate-id", type=int)
    promotion_exclude.add_argument(
        "--source-origin", choices=("cli", "operator"), default="cli",
    )
    promotion_exclude.add_argument("--approve", action="store_true")
    sub.add_parser(
        "ai-system-promotions",
        help="List content-free controlled source-promotion evidence",
    )
    build_approve = sub.add_parser(
        "ai-system-controlled-build-approve",
        help="Approve one exact promotion for deterministic artifact building",
    )
    build_approve.add_argument("promotion_id")
    build_approve.add_argument("actor")
    build_approve.add_argument(
        "--source-origin", choices=("cli", "operator"), default="cli",
    )
    build_approve.add_argument("--approve", action="store_true")
    controlled_build = sub.add_parser(
        "ai-system-controlled-build",
        help="Build an immutable source bundle from one approved promotion",
    )
    controlled_build.add_argument("contract")
    controlled_build.add_argument("--approve", action="store_true")
    sub.add_parser(
        "ai-system-controlled-builds",
        help="List content-free controlled-build evidence",
    )
    execution_approve = sub.add_parser(
        "ai-system-execution-approve", help="Authorize one exact immutable build artifact for execution",
    )
    execution_approve.add_argument("build_id")
    execution_approve.add_argument("actor")
    execution_approve.add_argument("--timeout-seconds", type=int, default=10)
    execution_approve.add_argument("--max-output-chars", type=int, default=12000)
    execution_approve.add_argument("--source-origin", choices=("cli", "operator"), default="cli")
    execution_approve.add_argument("--approve", action="store_true")
    controlled_execution = sub.add_parser(
        "ai-system-controlled-execute", help="Execute one authorized immutable build artifact",
    )
    controlled_execution.add_argument("contract")
    controlled_execution.add_argument("--approve", action="store_true")
    execution_cancel = sub.add_parser("ai-system-execution-cancel", help="Cancel a queued controlled execution")
    execution_cancel.add_argument("execution_id")
    execution_cancel.add_argument("--approve", action="store_true")
    sub.add_parser("ai-system-controlled-executions", help="List content-free controlled-execution evidence")
    execution_status = sub.add_parser(
        "ai-system-controlled-execution-status",
        help="Inspect one controlled execution and its lifecycle",
    )
    execution_status.add_argument("execution_id")
    execution_result = sub.add_parser(
        "ai-system-controlled-execution-result",
        help="Inspect one content-free controlled-execution result",
    )
    execution_result.add_argument("execution_id")
    project_create = sub.add_parser(
        "project-create", help="Create a validated structured project record",
    )
    project_create.add_argument("manifest")
    project_update = sub.add_parser(
        "project-update", help="Update a project with optimistic version control",
    )
    project_update.add_argument("name")
    project_update.add_argument("changes")
    project_update.add_argument("--expected-version", type=int, required=True)
    projects = sub.add_parser(
        "projects", help="List or search structured project records",
    )
    projects.add_argument("--query", default="")
    projects.add_argument("--include-archived", action="store_true")
    project_archive = sub.add_parser(
        "project-archive", help="Archive a project record",
    )
    project_archive.add_argument("name")
    project_archive.add_argument("--expected-version", type=int, required=True)
    project_archive.add_argument("--approve", action="store_true")
    skill_create = sub.add_parser(
        "skill-create", help="Create a validated structured skill record",
    )
    skill_create.add_argument("manifest")
    skill_update = sub.add_parser(
        "skill-update", help="Update skill metadata with optimistic version control",
    )
    skill_update.add_argument("name")
    skill_update.add_argument("changes")
    skill_update.add_argument("--expected-version", type=int, required=True)
    skill_evidence = sub.add_parser(
        "skill-evidence", help="Add explicit evidence and recompute mastery",
    )
    skill_evidence.add_argument("manifest")
    skills = sub.add_parser(
        "skills", help="List or search structured skill mastery records",
    )
    skills.add_argument("--query", default="")
    skills.add_argument("--include-archived", action="store_true")
    skill_archive = sub.add_parser(
        "skill-archive", help="Archive a structured skill record",
    )
    skill_archive.add_argument("name")
    skill_archive.add_argument("--expected-version", type=int, required=True)
    skill_archive.add_argument("--approve", action="store_true")
    automation_run = sub.add_parser("automations-run", help="Execute due automations")
    automation_run.add_argument("--watch", action="store_true")
    automation_run.add_argument("--interval", type=float, default=60.0)
    automation_run.add_argument("--lease-seconds", type=int, default=3_600)
    scaffold = sub.add_parser("scaffold", help="Create a bounded application workspace")
    scaffold.add_argument("manifest")
    scaffold.add_argument("--approve", action="store_true")
    scaffold.add_argument("--overwrite", action="store_true")
    verify_workspace = sub.add_parser(
        "verify-workspace", help="Run bounded static checks in an application workspace",
    )
    verify_workspace.add_argument("manifest")
    verify_workspace.add_argument("--approve", action="store_true")
    test_workspace = sub.add_parser(
        "test-workspace", help="Run the fixed opt-in Python unittest command",
    )
    test_workspace.add_argument("project_name")
    test_workspace.add_argument("--approve", action="store_true")
    external_test = sub.add_parser(
        "test-workspace-external",
        help="Submit a workspace to the configured signed HTTPS test worker",
    )
    external_test.add_argument("project_name")
    external_test.add_argument("--approve", action="store_true")
    package_workspace = sub.add_parser(
        "package-workspace", help="Create a deterministic application ZIP artifact",
    )
    package_workspace.add_argument("project_name")
    package_workspace.add_argument("--approve", action="store_true")
    deployment = sub.add_parser(
        "record-deployment", help="Record an immutable unverified deployment event",
    )
    deployment.add_argument("artifact_id", type=int)
    deployment.add_argument("environment_name")
    deployment.add_argument("target_kind")
    deployment.add_argument("reported_outcome")
    deployment.add_argument("--approve", action="store_true")
    return parser


def _load_manifest(path: str) -> dict[str, object]:
    source = Path(path).resolve()
    value = json.loads(source.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError("Manifest root must be a JSON object")
    return value


def _load_text(path: str) -> str:
    return Path(path).resolve().read_text(encoding="utf-8")


def live_smoke(system: SparkleSystem) -> int:
    adapter = system.model_router.select("general")
    health = adapter.health()
    if not health.get("configured"):
        _print({"ok": False, "stage": "credential_presence", "provider": health, "secret_value_exposed": False})
        return 2
    started = time.monotonic()
    try:
        response = adapter.complete(ModelRequest(
            messages=[Message(role="user", content="Reply with exactly SPARKLE_LIVE_OK")],
            system="This is a provider connectivity smoke test. Follow the user's exact output instruction.",
            max_output_tokens=64, thinking=False, temperature=0,
        ))
    except ModelError as exc:
        _print({
            "ok": False, "stage": "live_request", "provider": health,
            "error": str(exc), "retryable": exc.retryable, "secret_value_exposed": False,
        })
        return 1
    exact = response.text.strip() == "SPARKLE_LIVE_OK"
    _print({
        "ok": exact, "stage": "live_request", "provider": response.provider, "model": response.model,
        "finish_reason": response.finish_reason, "exact_response_match": exact,
        "provider_request_id": response.provider_request_id,
        "usage": response.usage, "duration_ms": round((time.monotonic() - started) * 1000, 2),
        "secret_value_exposed": False,
    })
    return 0 if exact else 1


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    system = SparkleSystem()
    if args.command == "status":
        _print(system.status())
        return 0
    if args.command == "serve":
        serve(system, args.host or system.config.host, args.port or system.config.port)
        return 0
    if args.command == "chat":
        result = system.orchestrator.run_multi(args.message) if args.multi else system.orchestrator.run(args.message, agent_name=args.agent)
        _print(result.to_dict())
        return 0
    if args.command == "smoke-test":
        if args.live:
            return live_smoke(system)
        _print({"ok": True, "models": system.models.list(), "live_call_executed": False})
        return 0
    if args.command == "remember":
        memory_id = system.memory.remember(args.category, args.key, args.value, metadata={"source": "cli"})
        _print({"ok": True, "memory_id": memory_id})
        return 0
    if args.command == "ingest":
        path = Path(args.path).resolve()
        source_id = system.knowledge_ingestor.ingest(
            path, title=args.title, monitor_key=args.monitor_key,
        )
        _print({"ok": True, "source_id": source_id})
        return 0
    if args.command == "agent-install":
        manifest = _load_manifest(args.manifest)
        manifest["approved"] = bool(args.approve)
        manifest["replace"] = bool(args.replace)
        result = system.tools.execute(
            "agent_install", manifest, allowed={"agent_install"},
        )
        _print({"ok": True, "agent": result})
        return 0
    if args.command == "agent-remove":
        if not args.approve:
            raise ValueError("Agent removal requires --approve")
        _print({"ok": True, "removed": system.agents.remove(args.name)})
        return 0
    if args.command == "agent-prepare":
        requirements = _load_manifest(args.requirements)
        _print({
            "ok": True,
            "blueprint": system.agent_builder.prepare(requirements).to_dict(),
        })
        return 0
    if args.command == "agent-build":
        requirements = _load_manifest(args.requirements)
        _print({
            "ok": True,
            "blueprint": system.agent_builder.build(
                requirements, approved=bool(args.approve),
            ),
        })
        return 0
    if args.command == "agent-evaluate":
        result = system.agent_evaluator.evaluate(
            args.name, approved=bool(args.approve),
        )
        _print({"ok": result["status"] == "passed", "evaluation": result})
        return 0 if result["status"] == "passed" else 1
    if args.command == "ai-system-prepare":
        requirements = _load_manifest(args.requirements)
        _print({
            "ok": True,
            "blueprint": system.ai_system_builder.prepare(requirements).to_dict(),
        })
        return 0
    if args.command == "ai-system-draft":
        result = system.ai_system_compiler.compile(
            _load_text(args.requirements_text), approved=bool(args.approve),
        )
        _print({"ok": True, "draft": result})
        return 0
    if args.command == "ai-system-build":
        requirements = _load_manifest(args.requirements)
        _print({
            "ok": True,
            "blueprint": system.ai_system_builder.build(
                requirements, approved=bool(args.approve),
            ),
        })
        return 0
    if args.command == "ai-system-plan":
        requirements = _load_manifest(args.requirements)
        _print({
            "ok": True,
            "implementation_plan": system.ai_system_planner.prepare(requirements),
        })
        return 0
    if args.command == "ai-system-plan-build":
        requirements = _load_manifest(args.requirements)
        _print({
            "ok": True,
            "implementation_plan": system.ai_system_planner.materialize(
                requirements, approved=bool(args.approve),
            ),
        })
        return 0
    if args.command == "ai-system-plan-review":
        _print({
            "ok": True,
            "implementation_plan": system.ai_system_source_candidates.review_plan(
                args.plan_id, approved=bool(args.approve),
            ),
        })
        return 0
    if args.command == "ai-system-source-disclose":
        _print({
            "ok": True,
            "provider_disclosure": (
                system.ai_system_source_candidates.prepare_disclosure(
                    args.plan_id,
                    _load_manifest(args.requirements),
                    generation_task=_load_text(args.generation_task),
                )
            ),
        })
        return 0
    if args.command == "ai-system-source-disclosure-approve":
        _print({
            "ok": True,
            "provider_disclosure": (
                system.ai_system_source_candidates.approve_disclosure(
                    args.disclosure_id, approved=bool(args.approve),
                )
            ),
        })
        return 0
    if args.command == "ai-system-source-generate":
        _print({
            "ok": True,
            "source_candidate": system.ai_system_source_candidates.generate(
                args.plan_id,
                _load_manifest(args.requirements),
                args.disclosure_id,
                approved=bool(args.approve),
            ),
        })
        return 0
    if args.command == "ai-system-source-review":
        _print({
            "ok": True,
            "source_candidate": system.ai_system_source_candidates.review(
                args.candidate_id,
                decision=args.decision,
                notes=_load_text(args.notes),
                approved=bool(args.approve),
            ),
        })
        return 0
    if args.command == "ai-system-source-verify":
        _print({
            "ok": True,
            "source_candidate": system.ai_system_source_candidates.verify(
                args.candidate_id, _load_manifest(args.requirements),
            ),
        })
        return 0
    if args.command == "ai-system-source-approve":
        _print({
            "ok": True,
            "source_candidate": system.ai_system_source_candidates.approve(
                args.candidate_id, approved=bool(args.approve),
            ),
        })
        return 0
    if args.command == "ai-system-source-file":
        _print({
            "ok": True,
            "source_file": system.ai_system_source_candidates.read_file(
                args.candidate_id, args.path,
            ),
        })
        return 0
    if args.command == "ai-system-source-candidates":
        _print({
            "ok": True,
            "protocol_version": system.ai_system_source_candidates.PROTOCOL,
            "source_candidates": system.source_candidates.list(limit=100),
        })
        return 0
    if args.command == "ai-system-source-disclosures":
        _print({
            "ok": True,
            "provider_disclosures": system.source_provider_disclosures.list(
                limit=100
            ),
        })
        return 0
    if args.command == "ai-system-runtime-evaluate":
        result = system.ai_system_runtime_evaluator.request(
            _load_manifest(args.contract), approved=bool(args.approve),
        )
        _print({"ok": result["status"] == "evaluated", "runtime_evaluation": result})
        return 0 if result["status"] == "evaluated" else 1
    if args.command == "ai-system-runtime-evaluations":
        _print({
            "ok": True,
            "protocol_version": system.ai_system_runtime_evaluator.PROTOCOL,
            "runtime_evaluations": system.runtime_evaluations.list(limit=100),
        })
        return 0
    if args.command == "ai-system-promotion-approve":
        approval = system.ai_system_source_promoter.approve(
            args.candidate_id,
            args.evaluation_id,
            actor=args.actor,
            source_origin=args.source_origin,
            approved=bool(args.approve),
        )
        _print({"ok": True, "promotion_approval": approval})
        return 0
    if args.command == "ai-system-promote":
        result = system.ai_system_source_promoter.request(
            _load_manifest(args.contract), approved=bool(args.approve),
        )
        _print({"ok": result["status"] == "promoted", "source_promotion": result})
        return 0 if result["status"] == "promoted" else 1
    if args.command == "ai-system-promotion-exclude":
        exclusion = system.ai_system_source_promoter.exclude_candidate(
            args.candidate_id,
            status=args.status,
            reason=_load_text(args.reason),
            actor=args.actor,
            source_origin=args.source_origin,
            approved=bool(args.approve),
            replacement_candidate_id=args.replacement_candidate_id,
        )
        _print({"ok": True, "promotion_exclusion": exclusion})
        return 0
    if args.command == "ai-system-promotions":
        _print({
            "ok": True,
            "protocol_version": system.ai_system_source_promoter.PROTOCOL,
            "source_promotions": system.source_promotions.list(limit=100),
            "promotion_approvals": system.source_promotions.list_approvals(limit=100),
            "promotion_eligibility": system.ai_system_source_promoter.eligibility(
                limit=100
            ),
        })
        return 0
    if args.command == "ai-system-controlled-build-approve":
        approval = system.ai_system_controlled_builder.approve(
            args.promotion_id,
            actor=args.actor,
            source_origin=args.source_origin,
            approved=bool(args.approve),
        )
        _print({"ok": True, "controlled_build_approval": approval})
        return 0
    if args.command == "ai-system-controlled-build":
        result = system.ai_system_controlled_builder.request(
            _load_manifest(args.contract), approved=bool(args.approve),
        )
        _print({"ok": result["status"] == "built", "controlled_build": result})
        return 0 if result["status"] == "built" else 1
    if args.command == "ai-system-controlled-builds":
        _print({
            "ok": True,
            "protocol_version": system.ai_system_controlled_builder.PROTOCOL,
            "controlled_builds": system.controlled_builds.list(limit=100),
            "controlled_build_approvals": (
                system.controlled_builds.list_approvals(limit=100)
            ),
            "controlled_build_eligibility": (
                system.ai_system_controlled_builder.eligibility(limit=100)
            ),
        })
        return 0
    if args.command == "ai-system-execution-approve":
        authorization = system.ai_system_controlled_executor.approve(
            args.build_id, actor=args.actor, source_origin=args.source_origin,
            approved=bool(args.approve), timeout_seconds=args.timeout_seconds,
            max_output_chars=args.max_output_chars,
        )
        _print({"ok": True, "controlled_execution_authorization": authorization})
        return 0
    if args.command == "ai-system-controlled-execute":
        result = system.ai_system_controlled_executor.request(
            _load_manifest(args.contract), approved=bool(args.approve),
        )
        _print({"ok": result["status"] == "verified", "controlled_execution": result})
        return 0 if result["status"] == "verified" else 1
    if args.command == "ai-system-execution-cancel":
        result = system.ai_system_controlled_executor.cancel(
            args.execution_id, approved=bool(args.approve),
        )
        _print({"ok": result["status"] == "cancelled", "controlled_execution": result})
        return 0
    if args.command == "ai-system-controlled-executions":
        _print({
            "ok": True, "protocol_version": system.ai_system_controlled_executor.PROTOCOL,
            "controlled_executions": system.controlled_executions.list(limit=100),
            "controlled_execution_authorizations": system.controlled_executions.list_authorizations(limit=100),
            "execution_is_deployment": False,
        })
        return 0
    if args.command == "ai-system-controlled-execution-status":
        _print({
            "ok": True,
            "controlled_execution": system.ai_system_controlled_executor.inspect(
                args.execution_id,
            ),
        })
        return 0
    if args.command == "ai-system-controlled-execution-result":
        _print({
            "ok": True,
            "controlled_execution_result": system.ai_system_controlled_executor.result(
                args.execution_id,
            ),
        })
        return 0
    if args.command == "project-create":
        project = system.projects.create(_load_manifest(args.manifest))
        _print({"ok": True, "project": project})
        return 0
    if args.command == "project-update":
        project = system.projects.update(
            args.name, _load_manifest(args.changes),
            expected_version=args.expected_version,
        )
        _print({"ok": True, "project": project})
        return 0
    if args.command == "projects":
        records = (
            system.projects.search(args.query, limit=100)
            if args.query else
            system.projects.list(
                limit=100, include_archived=bool(args.include_archived),
            )
        )
        _print({
            "ok": True,
            "protocol_version": system.projects.PROTOCOL,
            "projects": records,
        })
        return 0
    if args.command == "project-archive":
        if not args.approve:
            raise ValueError("Project archival requires explicit approval")
        project = system.projects.archive(
            args.name, expected_version=args.expected_version,
        )
        _print({"ok": True, "project": project})
        return 0
    if args.command == "skill-create":
        skill = system.skills.create(_load_manifest(args.manifest))
        _print({"ok": True, "skill": skill})
        return 0
    if args.command == "skill-update":
        skill = system.skills.update(
            args.name, _load_manifest(args.changes),
            expected_version=args.expected_version,
        )
        _print({"ok": True, "skill": skill})
        return 0
    if args.command == "skill-evidence":
        result = system.skills.add_evidence(_load_manifest(args.manifest))
        _print({"ok": True, **result})
        return 0
    if args.command == "skills":
        records = (
            system.skills.search(args.query, limit=100)
            if args.query else
            system.skills.list(
                limit=100, include_archived=bool(args.include_archived),
            )
        )
        _print({
            "ok": True,
            "protocol_version": system.skills.PROTOCOL,
            "skills": records,
        })
        return 0
    if args.command == "skill-archive":
        if not args.approve:
            raise ValueError("Skill archival requires explicit approval")
        skill = system.skills.archive(
            args.name, expected_version=args.expected_version,
        )
        _print({"ok": True, "skill": skill})
        return 0
    if args.command == "automations-run":
        if not args.watch:
            _print({
                "ok": True,
                "runs": system.automation_runner.run_due(
                    lease_seconds=args.lease_seconds,
                ),
            })
            return 0
        from sparkle.automation_service import AutomationService, run_with_signals

        service = AutomationService(
            system.automations,
            system.automation_runner,
            interval_seconds=args.interval,
            lease_seconds=args.lease_seconds,
        )
        _print({"ok": True, "service_run": run_with_signals(service)})
        return 0
    if args.command == "scaffold":
        manifest = _load_manifest(args.manifest)
        manifest["approved"] = bool(args.approve)
        manifest["overwrite"] = bool(args.overwrite)
        result = system.tools.execute(
            "workspace_scaffold", manifest, allowed={"workspace_scaffold"},
        )
        _print({"ok": True, "build": result})
        return 0
    if args.command == "verify-workspace":
        manifest = _load_manifest(args.manifest)
        manifest["approved"] = bool(args.approve)
        result = system.tools.execute(
            "workspace_verify", manifest, allowed={"workspace_verify"},
        )
        _print({"ok": result["status"] == "passed", "verification": result})
        return 0 if result["status"] == "passed" else 1
    if args.command == "test-workspace":
        result = system.tools.execute(
            "workspace_test",
            {"project_name": args.project_name, "approved": bool(args.approve)},
            allowed={"workspace_test"},
        )
        _print({"ok": result["status"] == "passed", "test_run": result})
        return 0 if result["status"] == "passed" else 1
    if args.command == "test-workspace-external":
        result = system.external_worker_tool.run({
            "project_name": args.project_name,
            "approved": bool(args.approve),
        })
        _print({"ok": result["status"] == "passed", "external_test_run": result})
        return 0 if result["status"] == "passed" else 1
    if args.command == "package-workspace":
        result = system.tools.execute(
            "workspace_package",
            {"project_name": args.project_name, "approved": bool(args.approve)},
            allowed={"workspace_package"},
        )
        _print({"ok": True, "artifact": result})
        return 0
    if args.command == "record-deployment":
        if not args.approve:
            raise ValueError("Deployment recording requires --approve")
        result = system.artifacts.record_deployment(
            args.artifact_id,
            args.environment_name,
            args.target_kind,
            args.reported_outcome,
        )
        _print({"ok": True, "deployment": result})
        return 0
    return 2


def entrypoint(argv: list[str] | None = None) -> int:
    try:
        return main(argv)
    except (
        ModelError,
        ExternalWorkerError,
        SecretNotFoundError,
        ValueError,
        KeyError,
        TypeError,
        ToolError,
        FileExistsError,
    ) as exc:
        print(str(exc), file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(entrypoint())
