from __future__ import annotations

import json
import os
import tempfile
import threading
import unittest
import urllib.error
import urllib.request
from datetime import UTC, datetime, timedelta
from http.server import ThreadingHTTPServer
from pathlib import Path
from unittest.mock import patch

from sparkle.api import SparkleHandler
from sparkle.config import AppConfig
from sparkle.contracts import ModelRequest, ModelResponse, TokenUsage, ToolCall
from sparkle.model import ModelAdapter
from sparkle.providers.mock import DeterministicAdapter
from sparkle.registry import ModelRegistry
from sparkle.secrets import SecretResolver
from sparkle.security import APIAccessPolicy, APISessionManager, FixedWindowRateLimiter
from sparkle.system import SparkleSystem
from sparkle.tooling import ExternalWorkspaceTestTool


class ToolCallingAdapter(ModelAdapter):
    provider = "scripted"
    model_id = "scripted"

    def __init__(self):
        self.calls = 0

    def complete(self, request: ModelRequest) -> ModelResponse:
        self.calls += 1
        if self.calls == 1:
            content = [{"type": "tool_use", "id": "tool-1", "name": "calculator", "input": {"expression": "6*7"}}]
            return ModelResponse("", self.model_id, self.provider, "tool_use", [ToolCall("tool-1", "calculator", {"expression": "6*7"})], raw_assistant_content=content)
        self.last_messages = request.messages
        return ModelResponse("42", self.model_id, self.provider, "end_turn", usage=TokenUsage(5, 1))

    def health(self):
        return {"configured": True}


def test_config() -> AppConfig:
    return AppConfig("127.0.0.1", 0, 4, 5, 5, False, False)


class SystemCase(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.env_patch = patch.dict(os.environ, {"SPARKLE_DATA_DIR": self.temp.name}, clear=False)
        self.env_patch.start()
        self.registry = ModelRegistry()
        self.registry.inject(self.registry.active_id, DeterministicAdapter())
        self.system = SparkleSystem(config=test_config(), model_registry=self.registry)

    def tearDown(self):
        self.env_patch.stop()
        self.temp.cleanup()


class OrchestratorTests(SystemCase):
    def test_single_agent_end_to_end_and_trace(self):
        result = self.system.orchestrator.run("Teach me inverse kinematics")
        self.assertEqual(result.agent, "learning")
        self.assertIn("SPARKLE processed", result.text)
        trace = self.system.traces.recent()[0]
        self.assertEqual(trace["status"], "success")
        self.assertEqual(trace["agent"], "learning")

    def test_tool_loop(self):
        adapter = ToolCallingAdapter()
        self.registry.inject(self.registry.active_id, adapter)
        result = self.system.orchestrator.run("Calculate 6 times 7", agent_name="personal")
        self.assertEqual(result.text, "42")
        self.assertEqual(result.tool_calls_executed, ["calculator"])
        self.assertEqual(adapter.last_messages[-1].content, "42")

    def test_multi_agent_synthesis(self):
        result = self.system.orchestrator.run_multi("Research robot arms and build an application dashboard", agent_names=["research", "application_builder"])
        self.assertEqual(result.agent, "personal")
        self.assertGreaterEqual(len(self.system.traces.recent()), 3)


class APITests(SystemCase):
    def setUp(self):
        super().setUp()
        handler = type("TestHandler", (SparkleHandler,), {"system": self.system, "log_message": lambda *args: None})
        self.server = ThreadingHTTPServer(("127.0.0.1", 0), handler)
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()
        self.base = f"http://127.0.0.1:{self.server.server_port}"

    def tearDown(self):
        self.server.shutdown()
        self.server.server_close()
        self.thread.join(timeout=2)
        super().tearDown()

    def request(
        self,
        path: str,
        value: dict | None = None,
        *,
        headers: dict[str, str] | None = None,
        method: str | None = None,
    ):
        data = json.dumps(value).encode() if value is not None else None
        request_headers = {"Content-Type": "application/json"} if data else {}
        request_headers.update(headers or {})
        request = urllib.request.Request(
            self.base + path,
            data=data,
            headers=request_headers,
            method=method or ("POST" if data else "GET"),
        )
        try:
            with urllib.request.urlopen(request, timeout=3) as response:
                return response.status, response.headers, response.read()
        except urllib.error.HTTPError as exc:
            return exc.code, exc.headers, exc.read()

    def test_request_log_strips_query_values(self):
        handler = SparkleHandler.__new__(SparkleHandler)
        handler.client_address = ("127.0.0.1", 12345)
        handler.command = "GET"
        handler.path = "/api/health?secret_query=private-value"
        handler.request_version = "HTTP/1.1"
        with patch("builtins.print") as printed:
            handler.log_request(200, 10)
        log_line = str(printed.call_args)
        self.assertIn("/api/health", log_line)
        self.assertNotIn("secret_query", log_line)
        self.assertNotIn("private-value", log_line)
        handler.path = "/api/private-route-value"
        with patch("builtins.print") as printed:
            handler.log_request(404, 10)
        self.assertEqual(
            SparkleHandler._safe_log_path(handler.path), "/api/[unknown]",
        )
        self.assertNotIn("private-route-value", str(printed.call_args))

    def test_health_and_security_headers(self):
        status, headers, body = self.request("/api/health")
        self.assertEqual(status, 200)
        self.assertEqual(headers["X-Content-Type-Options"], "nosniff")
        self.assertEqual(headers["X-RateLimit-Limit"], "120")
        self.assertEqual(headers["X-RateLimit-Remaining"], "119")
        self.assertTrue(json.loads(body)["ok"])

    def test_external_worker_route_is_operator_approved(self):
        class StubClient:
            def run(self, project_name):
                return {
                    "project_name": project_name, "status": "passed",
                    "response_verified": True, "isolation_verified": False,
                }

        self.system.external_worker_tool = ExternalWorkspaceTestTool(StubClient())
        self.assertNotIn("external_workspace_test", self.system.tools.names)
        worker_status = self.system.status()["builders"]["external_worker"]
        self.assertFalse(worker_status["agent_tool_registered"])
        self.assertFalse(worker_status["live_worker_verified"])
        self.assertFalse(worker_status["isolation_verified"])
        self.assertEqual(self.request(
            "/api/builds/test-external", {"project_name": "worker_app"},
        )[0], 400)
        status, _, body = self.request(
            "/api/builds/test-external",
            {"project_name": "worker_app", "approved": True},
        )
        self.assertEqual(status, 201)
        result = json.loads(body)
        self.assertTrue(result["ok"])
        self.assertFalse(result["external_test_run"]["isolation_verified"])

    def test_rate_limit_precedes_authentication_and_is_audited(self):
        self.system.api_rate_limiter = FixedWindowRateLimiter(2, 60)
        self.assertEqual(self.request("/api/health")[0], 200)
        self.assertEqual(self.request("/api/health")[0], 200)
        status, headers, body = self.request("/api/health")
        self.assertEqual(status, 429)
        self.assertEqual(headers["X-RateLimit-Remaining"], "0")
        self.assertGreaterEqual(int(headers["Retry-After"]), 1)
        self.assertEqual(json.loads(body)["error"], "rate_limited")
        self.assertEqual(self.system.api_audit.recent()[0]["outcome"], "rate_limited")

    def test_origin_and_preflight_policy(self):
        status, headers, _ = self.request(
            "/api/health", headers={"Origin": self.base},
        )
        self.assertEqual(status, 200)
        self.assertEqual(headers["Access-Control-Allow-Origin"], self.base)
        self.assertEqual(self.request(
            "/api/health", headers={"Origin": "https://evil.example"},
        )[0], 403)
        preflight = self.request(
            "/api/chat",
            headers={
                "Origin": self.base,
                "Access-Control-Request-Method": "POST",
            },
            method="OPTIONS",
        )
        self.assertEqual(preflight[0], 204)
        self.assertEqual(preflight[1]["Access-Control-Allow-Origin"], self.base)
        self.assertNotEqual(preflight[1]["Access-Control-Allow-Origin"], "*")
        self.assertIn(
            "X-SPARKLE-CSRF", preflight[1]["Access-Control-Allow-Headers"],
        )

    def test_required_bearer_auth_rejects_without_mutation(self):
        self.system.api_access = APIAccessPolicy(
            SecretResolver({"SPARKLE_API_TOKEN": "unit-test-token"}),
            required=True,
        )
        status, headers, body = self.request("/api/health")
        self.assertEqual(status, 401)
        self.assertEqual(headers["WWW-Authenticate"], 'Bearer realm="SPARKLE"')
        self.assertNotIn(b"unit-test-token", body)
        self.assertEqual(self.request(
            "/api/memory",
            {"category": "goals", "key": "blocked", "value": "must not store"},
        )[0], 401)
        self.assertEqual(self.system.memory.recent(), [])
        self.assertEqual(self.request(
            "/api/health", headers={"Authorization": "Bearer wrong"},
        )[0], 401)
        authenticated = self.request(
            "/api/health",
            headers={"Authorization": "Bearer unit-test-token"},
        )
        self.assertEqual(authenticated[0], 200)
        self.assertNotIn(b"unit-test-token", authenticated[2])

    def test_dashboard_session_login_csrf_reload_and_logout(self):
        token = "unit-test-dashboard-token"
        self.system.api_access = APIAccessPolicy(
            SecretResolver({"SPARKLE_API_TOKEN": token}), required=True,
        )
        self.system.api_sessions = APISessionManager(
            enabled=True, ttl_seconds=300, max_active=4,
        )

        anonymous = self.request("/api/session")
        self.assertEqual(anonymous[0], 200)
        self.assertFalse(json.loads(anonymous[2])["authenticated"])
        self.assertEqual(self.request(
            "/api/session/login",
            headers={"Authorization": "Bearer wrong"},
            method="POST",
        )[0], 401)
        self.assertEqual(self.system.api_sessions.status()["active_sessions"], 0)

        login_status, login_headers, login_body = self.request(
            "/api/session/login",
            headers={"Authorization": f"Bearer {token}"},
            method="POST",
        )
        self.assertEqual(login_status, 200)
        cookie_header = login_headers["Set-Cookie"]
        self.assertIn("HttpOnly", cookie_header)
        self.assertIn("SameSite=Strict", cookie_header)
        cookie = cookie_header.split(";", 1)[0]
        session_id = cookie.split("=", 1)[1]
        login = json.loads(login_body)
        csrf = login["csrf_token"]
        self.assertNotEqual(csrf, session_id)
        self.assertNotIn(token.encode(), login_body)
        self.assertNotIn(session_id.encode(), login_body)

        restored = json.loads(self.request(
            "/api/session", headers={"Cookie": cookie},
        )[2])
        self.assertTrue(restored["authenticated"])
        self.assertEqual(restored["authentication_mode"], "session")
        self.assertEqual(restored["csrf_token"], csrf)
        health = self.request(
            "/api/health", headers={"Cookie": cookie},
        )
        self.assertEqual(health[0], 200)
        self.assertNotIn(session_id.encode(), health[2])
        self.assertNotIn(csrf.encode(), health[2])

        memory = {"category": "goals", "key": "secure", "value": "session"}
        self.assertEqual(self.request(
            "/api/memory", memory, headers={"Cookie": cookie},
        )[0], 401)
        self.assertEqual(self.request(
            "/api/memory", memory,
            headers={"Cookie": cookie, "X-SPARKLE-CSRF": "wrong"},
        )[0], 401)
        self.assertEqual(self.request(
            "/api/memory", memory,
            headers={"Cookie": cookie, "X-SPARKLE-CSRF": csrf},
        )[0], 201)

        logout_status, logout_headers, _ = self.request(
            "/api/session/logout",
            headers={"Cookie": cookie, "X-SPARKLE-CSRF": csrf},
            method="POST",
        )
        self.assertEqual(logout_status, 200)
        self.assertIn("Max-Age=0", logout_headers["Set-Cookie"])
        self.assertEqual(self.request(
            "/api/health", headers={"Cookie": cookie},
        )[0], 401)
        audit = json.dumps(self.system.api_audit.recent(limit=100))
        self.assertNotIn(token, audit)
        self.assertNotIn(session_id, audit)
        self.assertNotIn(csrf, audit)

    def test_api_audit_drops_query_credentials_headers_and_client_identity(self):
        token = "unit-test-token-private"
        self.system.api_access = APIAccessPolicy(
            SecretResolver({"SPARKLE_API_TOKEN": token}), required=True,
        )
        status, _, _ = self.request(
            "/api/health?secret_query=private-value",
            headers={
                "Authorization": f"Bearer {token}",
                "Origin": self.base,
            },
        )
        self.assertEqual(status, 200)
        record = self.system.api_audit.recent()[0]
        self.assertEqual(record["path"], "/api/health")
        encoded = json.dumps(record)
        self.assertNotIn(token, encoded)
        self.assertNotIn("private-value", encoded)
        self.assertNotIn(self.base, encoded)
        self.assertNotIn("127.0.0.1", encoded)
        audit_response = self.request(
            "/api/audit", headers={"Authorization": f"Bearer {token}"},
        )
        self.assertEqual(audit_response[0], 200)
        self.assertEqual(json.loads(audit_response[2])["audit"][0]["path"], "/api/health")

    def test_chat_endpoint(self):
        status, _, body = self.request("/api/chat", {"message": "Teach Python"})
        result = json.loads(body)["result"]
        self.assertEqual(status, 200)
        self.assertEqual(result["agent"], "learning")
        self.assertRegex(result["trace_id"], r"SPK-\d{4}-\d{6}")

    def test_memory_and_knowledge_endpoints(self):
        memory_body = json.loads(self.request(
            "/api/memory", {"category": "goals", "key": "robotics", "value": "Learn ROS 2"},
        )[2])
        knowledge_body = json.loads(self.request(
            "/api/knowledge", {"title": "ROS", "content": "ROS 2 uses nodes and topics."},
        )[2])
        memories = json.loads(self.request("/api/memory?q=ROS")[2])["memories"]
        knowledge = json.loads(self.request("/api/knowledge/search?q=nodes")[2])["results"]
        self.assertEqual(memories[0]["key"], "robotics")
        self.assertEqual(knowledge[0]["title"], "ROS")
        memory_id = memory_body["memory_id"]
        source_id = knowledge_body["source_id"]
        self.assertTrue(json.loads(self.request(
            "/api/memory/archive", {"memory_id": memory_id},
        )[2])["archived"])
        self.assertTrue(json.loads(self.request(
            "/api/memory/restore", {"memory_id": memory_id},
        )[2])["restored"])
        self.assertEqual(self.request(
            "/api/memory/delete", {"memory_id": memory_id},
        )[0], 400)
        self.assertTrue(json.loads(self.request(
            "/api/memory/delete", {"memory_id": memory_id, "approved": True},
        )[2])["deleted"])
        sources = json.loads(self.request("/api/knowledge/sources")[2])["sources"]
        self.assertEqual(sources[0]["source_id"], source_id)
        self.assertEqual(self.request(
            "/api/knowledge/delete", {"source_id": source_id},
        )[0], 400)
        self.assertTrue(json.loads(self.request(
            "/api/knowledge/delete", {"source_id": source_id, "approved": True},
        )[2])["deleted"])

    def test_dashboard_serves(self):
        status, _, body = self.request("/")
        self.assertEqual(status, 200)
        self.assertIn(b"SPARKLE", body)
        self.assertIn(b'<form id="loginForm" class="auth-card" autocomplete="off">', body)
        _, _, script = self.request("/assets/app.js")
        self.assertIn(b"X-SPARKLE-CSRF", script)
        self.assertIn(b"credentials: 'same-origin'", script)
        self.assertNotIn(b"localStorage", script)
        self.assertNotIn(b"sessionStorage", script)
        self.assertIn(b"/api/artifacts?limit=50", script)
        self.assertIn(b"/api/proactive", script)
        self.assertIn(b"/api/notifications", script)
        self.assertIn(b"/api/projects?limit=50", script)
        self.assertIn(b'notificationList', body)
        self.assertIn(b'projectList', body)
        self.assertIn(b"Artifacts & deployment", body)
        self.assertIn(b"Evidence-backed proactive alerts", body)

    def test_dashboard_notification_delivery_list_and_read_api(self):
        invalid = self.request("/api/notifications", {
            "channel": "email", "title": "Invalid", "body": "Not stored",
        })
        self.assertEqual(invalid[0], 400)
        self.assertEqual(self.system.notifications.stats()["total"], 0)

        status, _, body = self.request("/api/notifications", {
            "channel": "dashboard",
            "title": "Robotics review",
            "body": "Review the safe controls milestone",
            "severity": "warning",
            "dedupe_key": "robotics.controls",
        })
        self.assertEqual(status, 201)
        delivered = json.loads(body)["notification"]
        self.assertEqual(delivered["source"], "manual")
        status, _, body = self.request("/api/notifications?unread=true")
        self.assertEqual(status, 200)
        response = json.loads(body)
        self.assertEqual(response["protocol_version"], "SPARKLE-NOTIFICATION/1")
        self.assertEqual(len(response["notifications"]), 1)
        self.assertEqual(self.request("/api/notifications/read", {
            "notification_id": True,
        })[0], 400)
        marked = json.loads(self.request("/api/notifications/read", {
            "notification_id": delivered["notification_id"],
        })[2])
        self.assertTrue(marked["changed"])
        unread = json.loads(
            self.request("/api/notifications?unread=true")[2]
        )["notifications"]
        self.assertEqual(unread, [])

    def test_proactive_endpoint_exposes_metadata_evidence_only(self):
        self.system.memory.remember(
            "skills",
            "robotics",
            "Do not expose this private note",
            metadata={
                "evidence_count": 5,
                "accuracy": 0.5,
                "target_accuracy": 0.8,
                "attempts": 10,
            },
        )
        status, _, body = self.request("/api/proactive")
        self.assertEqual(status, 200)
        value = json.loads(body)
        self.assertEqual(value["protocol_version"], "SPARKLE-PROACTIVE/1")
        self.assertEqual(value["alerts"][0]["type"], "weak_learning")
        self.assertNotIn("Do not expose", body.decode())
        self.assertEqual(self.system.api_audit.recent()[0]["path"], "/api/proactive")

    def test_proactive_endpoint_exposes_safe_schedule_conflict_evidence(self):
        now = datetime.now(UTC)
        first_id = self.system.memory.remember(
            "tasks", "robot_lab", "Never expose private lab details",
            metadata={
                "starts_at": (now + timedelta(hours=1)).isoformat(),
                "ends_at": (now + timedelta(hours=3)).isoformat(),
            },
        )
        second_id = self.system.memory.remember(
            "exams", "controls_exam", "Never expose private exam details",
            metadata={
                "starts_at": (now + timedelta(hours=2)).isoformat(),
                "ends_at": (now + timedelta(hours=4)).isoformat(),
            },
        )
        status, _, body = self.request("/api/proactive")
        self.assertEqual(status, 200)
        alerts = json.loads(body)["alerts"]
        conflict = next(
            item for item in alerts if item["type"] == "schedule_conflict"
        )
        self.assertEqual(conflict["source_memory_id"], first_id)
        self.assertEqual(
            conflict["evidence"]["conflicting_memory_id"], second_id,
        )
        self.assertNotIn("Never expose", body.decode())

    def test_knowledge_revisions_flow_to_safe_research_change_alert(self):
        invalid_status, _, invalid_body = self.request("/api/knowledge", {
            "title": "Invalid monitor",
            "content": "Must not be stored",
            "metadata": {
                "research_monitor": True, "monitor_key": "INVALID KEY",
            },
        })
        self.assertEqual(invalid_status, 400)
        self.assertNotIn("Must not be stored", invalid_body.decode())
        self.assertEqual(self.system.knowledge.stats()["sources"], 0)
        metadata = {
            "research_monitor": True, "monitor_key": "robotics.papers",
        }
        first = json.loads(self.request("/api/knowledge", {
            "title": "Private robotics paper",
            "content": "Never expose original research text",
            "source_uri": "https://private.example/research",
            "metadata": metadata,
        })[2])["source_id"]
        second = json.loads(self.request("/api/knowledge", {
            "title": "Private robotics paper",
            "content": "Never expose revised research text",
            "source_uri": "https://private.example/research",
            "metadata": metadata,
        })[2])["source_id"]
        status, _, body = self.request("/api/proactive")
        self.assertEqual(status, 200)
        alert = next(
            item for item in json.loads(body)["alerts"]
            if item["type"] == "research_change"
        )
        self.assertEqual(alert["source_kind"], "knowledge")
        self.assertEqual(alert["source_id"], second)
        self.assertEqual(alert["evidence"]["previous_source_id"], first)
        self.assertEqual(alert["evidence"]["current_source_id"], second)
        for private in (
            "Never expose", "private.example", "Private robotics paper",
        ):
            self.assertNotIn(private, body.decode())

    def test_generated_agent_build_and_automation_endpoints(self):
        agent = {
            "name": "robotics_research", "capability": "reasoning",
            "purpose": "Research robotics with evidence and engineering constraints.",
            "instructions": "Cross-check evidence and produce testable engineering recommendations.",
            "tools": ["calculator"], "keywords": ["robotics research"],
            "approved": True,
        }
        unapproved_agent = dict(agent)
        unapproved_agent["approved"] = False
        self.assertEqual(self.request("/api/agents", unapproved_agent)[0], 400)
        self.assertEqual(self.request("/api/agents", agent)[0], 201)
        agents = json.loads(self.request("/api/agents")[2])["agents"]
        generated = next(item for item in agents if item["name"] == "robotics_research")
        self.assertEqual(generated["source"], "generated")

        build = {
            "project_name": "robot_console",
            "files": {
                "README.md": "# Robot console\n",
                "main.py": "print('ready')\n",
                "tests/test_ready.py": (
                    "import unittest\n\n"
                    "class ReadyTests(unittest.TestCase):\n"
                    "    def test_ready(self):\n"
                    "        self.assertTrue(True)\n"
                ),
            },
            "approved": True,
        }
        unapproved_build = dict(build)
        unapproved_build["approved"] = False
        self.assertEqual(self.request("/api/builds", unapproved_build)[0], 400)
        self.assertEqual(self.request("/api/builds", build)[0], 201)
        self.assertEqual(self.request("/api/builds", build)[0], 409)
        self.assertEqual(
            json.loads(self.request("/api/builds")[2])["builds"][0]["project_name"],
            "robot_console",
        )
        verification = {
            "project_name": "robot_console",
            "checks": [{"type": "python_compile", "path": "main.py"}],
            "approved": True,
        }
        unapproved_verification = dict(verification)
        unapproved_verification["approved"] = False
        self.assertEqual(
            self.request("/api/builds/verify", unapproved_verification)[0], 400,
        )
        verified = json.loads(self.request("/api/builds/verify", verification)[2])
        self.assertEqual(verified["verification"]["status"], "passed")
        self.assertEqual(
            json.loads(self.request("/api/verifications")[2])["verifications"][0]["passed"],
            1,
        )

        self.assertEqual(self.request(
            "/api/builds/test", {"project_name": "robot_console", "approved": True},
        )[0], 400)
        self.system.workspace_tests.enabled = True
        self.system.workspace_tests.parent_environment = {}
        self.assertEqual(self.request(
            "/api/builds/test",
            {"project_name": "robot_console", "approved": True, "command": "custom"},
        )[0], 400)
        tested = json.loads(self.request(
            "/api/builds/test", {"project_name": "robot_console", "approved": True},
        )[2])
        self.assertEqual(tested["test_run"]["status"], "passed")
        self.assertEqual(
            json.loads(self.request("/api/test-runs")[2])["test_runs"][0]["status"],
            "passed",
        )

        self.assertEqual(self.request(
            "/api/builds/package",
            {"project_name": "robot_console", "approved": False},
        )[0], 400)
        packaged = json.loads(self.request(
            "/api/builds/package",
            {"project_name": "robot_console", "approved": True},
        )[2])["artifact"]
        self.assertEqual(packaged["status"], "packaged_unverified")
        self.assertEqual(
            json.loads(self.request("/api/artifacts")[2])["artifacts"][0][
                "artifact_sha256"
            ],
            packaged["artifact_sha256"],
        )
        deployment = {
            "artifact_id": packaged["artifact_id"],
            "environment_name": "staging",
            "target_kind": "server",
            "reported_outcome": "reported_success",
            "approved": True,
        }
        unapproved_deployment = dict(deployment)
        unapproved_deployment["approved"] = False
        self.assertEqual(
            self.request("/api/deployments", unapproved_deployment)[0], 400,
        )
        recorded = json.loads(self.request("/api/deployments", deployment)[2])[
            "deployment"
        ]
        self.assertEqual(recorded["verification_status"], "unverified")
        self.assertFalse(recorded["external_action_executed"])
        self.assertEqual(
            json.loads(self.request("/api/deployments")[2])["deployments"][0][
                "reported_outcome"
            ],
            "reported_success",
        )

        now = datetime.now(UTC)
        automation = {
            "name": "API focus review", "kind": "once",
            "action": {"type": "agent", "prompt": "Review my focus", "agent": "personal"},
            "next_run_at": (now - timedelta(minutes=1)).isoformat(),
        }
        self.assertEqual(self.request("/api/automations", automation)[0], 201)
        run = json.loads(self.request("/api/automations/run", {})[2])["runs"][0]
        self.assertEqual(run["status"], "success")
        self.assertEqual(
            json.loads(self.request("/api/automation-runs")[2])["runs"][0]["status"],
            "success",
        )

    def test_agent_blueprint_prepare_approval_build_and_list_endpoints(self):
        requirements = {
            "name": "robotics_research",
            "capability": "reasoning",
            "purpose": "Research robotics systems with evidence and engineering constraints.",
            "tools": ["calculator"],
            "keywords": ["robotics research", "robot arm"],
            "workflow": [
                "Collect relevant robotics evidence.",
                "Cross-check sources and state uncertainty.",
            ],
            "guardrails": ["Never fabricate sources or completed tests."],
            "evaluations": [{
                "name": "robot_arm_evidence",
                "prompt": "Perform robotics research for a robot arm.",
                "assertions": {
                    "contains_all": ["SPARKLE processed", "robot arm"],
                    "excludes_all": ["fabricated completion"],
                    "max_chars": 500,
                },
            }],
        }
        status, _, body = self.request(
            "/api/agents/prepare", {"requirements": requirements},
        )
        self.assertEqual(status, 200)
        prepared = json.loads(body)["blueprint"]
        self.assertEqual(prepared["status"], "prepared_static_verified")
        self.assertFalse(prepared["semantic_evaluation_executed"])
        self.assertFalse(prepared["external_deployment_executed"])
        self.assertNotIn(
            "robotics_research",
            {item["name"] for item in json.loads(
                self.request("/api/agents")[2]
            )["agents"]},
        )

        self.assertEqual(self.request(
            "/api/agents/build",
            {"requirements": requirements, "approved": False},
        )[0], 400)
        self.assertEqual(
            json.loads(self.request("/api/agent-blueprints")[2])["blueprints"],
            [],
        )

        status, _, body = self.request(
            "/api/agents/build",
            {"requirements": requirements, "approved": True},
        )
        self.assertEqual(status, 201)
        installed = json.loads(body)["blueprint"]
        self.assertEqual(installed["status"], "installed_static_verified")
        blueprints = json.loads(
            self.request("/api/agent-blueprints")[2]
        )["blueprints"]
        self.assertEqual(blueprints[0]["agent_name"], "robotics_research")
        agents = json.loads(self.request("/api/agents")[2])["agents"]
        self.assertEqual(
            next(item for item in agents if item["name"] == "robotics_research")["source"],
            "generated",
        )
        self.assertEqual(self.request(
            "/api/agents/evaluate",
            {"name": "robotics_research", "approved": False},
        )[0], 400)
        status, _, body = self.request(
            "/api/agents/evaluate",
            {"name": "robotics_research", "approved": True},
        )
        self.assertEqual(status, 200)
        self.assertEqual(json.loads(body)["evaluation"]["status"], "passed")
        status, _, evidence_body = self.request("/api/agent-evaluations")
        self.assertEqual(status, 200)
        self.assertEqual(
            json.loads(evidence_body)["evaluations"][0]["status"], "passed",
        )
        self.assertNotIn("Perform robotics research", evidence_body.decode())
        self.assertNotIn("SPARKLE processed", evidence_body.decode())

    def test_ai_system_prepare_approval_build_and_list_endpoints(self):
        requirements = {
            "name": "robotics_ai",
            "purpose": "Research robotics evidence and produce bounded analytical outputs.",
            "model_requirements": [{
                "capability": "reasoning", "modalities": ["text"],
            }],
            "agents": ["research", "data_analysis"],
            "tools": ["calculator", "knowledge_search"],
            "data_environments": [
                "knowledge_environment", "data_environment", "trace_environment",
            ],
            "interfaces": ["text", "api", "dashboard"],
            "workflow": [
                "Collect bounded evidence from approved sources.",
                "Analyze evidence with the selected specialist agents.",
                "Return a traceable result and preserve evaluation evidence.",
            ],
            "evaluations": [{
                "name": "robotics_integration",
                "kind": "integration",
                "criterion": "The system preserves source and trace boundaries.",
            }],
            "deployment": {
                "environment_name": "staging", "target_kind": "server",
            },
        }
        status, _, body = self.request(
            "/api/ai-systems/prepare", {"requirements": requirements},
        )
        self.assertEqual(status, 200)
        prepared = json.loads(body)["blueprint"]
        self.assertEqual(
            prepared["protocol_version"], "SPARKLE-AI-SYSTEM-BLUEPRINT/1",
        )
        self.assertFalse(prepared["model_calls_executed"])
        self.assertFalse(prepared["runtime_evaluation_executed"])
        self.assertFalse(prepared["external_deployment_executed"])
        self.assertEqual(
            json.loads(self.request("/api/ai-system-blueprints")[2])["blueprints"],
            [],
        )

        self.assertEqual(self.request(
            "/api/ai-systems/build",
            {"requirements": requirements, "approved": False},
        )[0], 400)
        status, _, body = self.request(
            "/api/ai-systems/build",
            {"requirements": requirements, "approved": True},
        )
        self.assertEqual(status, 201)
        built = json.loads(body)["blueprint"]
        self.assertEqual(built["status"], "materialized_static_verified")
        status, _, evidence_body = self.request("/api/ai-system-blueprints")
        self.assertEqual(status, 200)
        records = json.loads(evidence_body)["blueprints"]
        self.assertEqual(records[0]["system_name"], "robotics_ai")
        self.assertEqual(records[0]["status"], "materialized_static_verified")

    def test_structured_project_lifecycle_and_evidence_endpoints(self):
        project = {
            "name": "sparkle_core",
            "title": "SPARKLE core platform",
            "description": "Build and verify the provider-neutral personal AI platform.",
            "status": "implementation",
            "priority": "critical",
            "deadline": "2026-09-30T12:30:00Z",
            "dependencies": [],
            "risks": ["External provider verification is unavailable."],
            "milestones": [{
                "name": "Structured project tracking",
                "status": "in_progress",
                "due_at": "2026-09-05T12:00:00Z",
            }],
            "blockers": [],
            "next_action": "Complete the structured project-state integration.",
            "progress": 90,
        }
        status, _, body = self.request("/api/projects", project)
        self.assertEqual(status, 201)
        created = json.loads(body)["project"]
        self.assertEqual(created["version"], 1)
        self.assertEqual(
            json.loads(self.request("/api/projects?limit=50")[2])["projects"][0]["name"],
            "sparkle_core",
        )
        stale = {
            "name": "sparkle_core",
            "changes": {"progress": 91},
            "expected_version": 5,
        }
        self.assertEqual(self.request("/api/projects/update", stale)[0], 400)
        update = {
            "name": "sparkle_core",
            "changes": {
                "progress": 95,
                "next_action": "Run the complete project regression suite.",
            },
            "expected_version": 1,
        }
        status, _, body = self.request("/api/projects/update", update)
        self.assertEqual(status, 200)
        self.assertEqual(json.loads(body)["project"]["version"], 2)
        events = json.loads(self.request(
            "/api/project-events?name=sparkle_core",
        )[2])["events"]
        self.assertEqual(events[0]["changed_fields"], ["next_action", "progress"])
        self.assertNotIn("Run the complete", json.dumps(events))
        archive = {
            "name": "sparkle_core", "expected_version": 2, "approved": False,
        }
        self.assertEqual(self.request("/api/projects/archive", archive)[0], 400)
        archive["approved"] = True
        self.assertEqual(self.request("/api/projects/archive", archive)[0], 200)
        self.assertEqual(
            json.loads(self.request("/api/projects")[2])["projects"], [],
        )
        archived = json.loads(self.request(
            "/api/projects?include_archived=true",
        )[2])["projects"]
        self.assertTrue(archived[0]["archived"])
