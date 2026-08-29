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
