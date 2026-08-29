from __future__ import annotations

import json
import mimetypes
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any
from urllib.parse import parse_qs, urlparse

from sparkle.model import ModelError
from sparkle.system import SparkleSystem
from sparkle.tooling import ToolError

MAX_BODY_BYTES = 1_000_000


class SparkleHandler(BaseHTTPRequestHandler):
    system: SparkleSystem
    dashboard_root = Path(__file__).with_name("dashboard")
    server_version = "SPARKLE/0.4"

    def log_message(self, format: str, *args: object) -> None:
        # Avoid request bodies, headers, query values, and secrets in logs.
        print(f"{self.address_string()} - {format % args}")

    def _headers(self, status: int, content_type: str, length: int) -> None:
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(length))
        self.send_header("Cache-Control", "no-store" if content_type.startswith("application/json") else "public, max-age=300")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("X-Frame-Options", "DENY")
        self.send_header("Referrer-Policy", "no-referrer")
        self.send_header("Content-Security-Policy", "default-src 'self'; style-src 'self'; script-src 'self'; img-src 'self' data:; connect-src 'self'")
        self.end_headers()

    def _json(self, value: Any, status: int = 200) -> None:
        body = json.dumps(value, ensure_ascii=False, separators=(",", ":"), default=str).encode("utf-8")
        self._headers(status, "application/json; charset=utf-8", len(body))
        self.wfile.write(body)

    def _read_json(self) -> dict[str, Any]:
        length = int(self.headers.get("Content-Length", "0"))
        if length <= 0 or length > MAX_BODY_BYTES:
            raise ValueError("Request body must contain 1-1000000 bytes")
        content_type = self.headers.get("Content-Type", "").split(";", 1)[0].strip()
        if content_type != "application/json":
            raise ValueError("Content-Type must be application/json")
        value = json.loads(self.rfile.read(length).decode("utf-8"))
        if not isinstance(value, dict):
            raise ValueError("JSON body must be an object")
        return value

    def _static(self, relative: str) -> None:
        target = (self.dashboard_root / relative).resolve()
        if target != self.dashboard_root.resolve() and self.dashboard_root.resolve() not in target.parents:
            self._json({"error": "not_found"}, 404)
            return
        if not target.is_file():
            self._json({"error": "not_found"}, 404)
            return
        body = target.read_bytes()
        content_type = mimetypes.guess_type(target.name)[0] or "application/octet-stream"
        self._headers(200, f"{content_type}; charset=utf-8" if content_type.startswith("text/") else content_type, len(body))
        self.wfile.write(body)

    def do_GET(self) -> None:
        parsed = urlparse(self.path)
        query = parse_qs(parsed.query)
        if parsed.path == "/":
            return self._static("index.html")
        if parsed.path.startswith("/assets/"):
            return self._static(parsed.path.removeprefix("/assets/"))
        if parsed.path == "/api/health":
            return self._json({"ok": True, "status": self.system.status()})
        if parsed.path == "/api/models":
            return self._json({"models": self.system.models.list()})
        if parsed.path == "/api/agents":
            return self._json({"agents": self.system.agents.list()})
        if parsed.path == "/api/memory":
            return self._json({"memories": self.system.memory.search(query.get("q", [""])[0], limit=int(query.get("limit", [20])[0]))})
        if parsed.path == "/api/knowledge/search":
            return self._json({"results": self.system.knowledge.search(query.get("q", [""])[0], limit=int(query.get("limit", [10])[0]))})
        if parsed.path == "/api/knowledge/sources":
            return self._json({
                "sources": self.system.knowledge.list_sources(
                    limit=int(query.get("limit", [100])[0])
                )
            })
        if parsed.path == "/api/traces":
            return self._json({"traces": self.system.traces.recent(limit=int(query.get("limit", [20])[0]))})
        if parsed.path == "/api/automations":
            return self._json({"automations": self.system.automations.list()})
        if parsed.path == "/api/automation-runs":
            return self._json({
                "runs": self.system.automations.list_runs(
                    limit=int(query.get("limit", [20])[0])
                )
            })
        if parsed.path == "/api/builds":
            return self._json({
                "builds": self.system.workspaces.list(
                    limit=int(query.get("limit", [20])[0])
                )
            })
        self._json({"error": "not_found"}, 404)

    def do_POST(self) -> None:
        try:
            data = self._read_json()
            if self.path == "/api/chat":
                text = str(data.get("message", ""))
                agent = str(data["agent"]) if data.get("agent") else None
                self.system.presence.update("working", "Reasoning", agent=agent)
                result = (
                    self.system.orchestrator.run_multi(text, agent_names=data.get("agents"), user_id=data.get("user_id"))
                    if data.get("multi_agent") else
                    self.system.orchestrator.run(text, agent_name=agent, user_id=data.get("user_id"))
                )
                self.system.presence.update("idle", "Ready", agent=result.agent, trace_id=result.trace_id)
                return self._json({"ok": True, "result": result.to_dict()})
            if self.path == "/api/models/activate":
                self.system.models.activate(str(data["model_id"]))
                return self._json({"ok": True, "active_model": self.system.models.active_id})
            if self.path == "/api/agents":
                result = self.system.tools.execute(
                    "agent_install", data, allowed={"agent_install"},
                )
                return self._json({"ok": True, "agent": result}, 201)
            if self.path == "/api/agents/remove":
                if data.get("approved") is not True:
                    raise ValueError("Agent removal requires explicit approval")
                removed = self.system.agents.remove(str(data["name"]))
                return self._json({"ok": True, "removed": removed})
            if self.path == "/api/memory":
                memory_id = self.system.memory.remember(
                    str(data["category"]), str(data["key"]), str(data["value"]),
                    importance=float(data.get("importance", 0.5)), metadata=data.get("metadata") or {},
                )
                return self._json({"ok": True, "memory_id": memory_id}, 201)
            if self.path == "/api/memory/archive":
                return self._json({
                    "ok": True, "archived": self.system.memory.archive(int(data["memory_id"])),
                })
            if self.path == "/api/memory/restore":
                return self._json({
                    "ok": True, "restored": self.system.memory.restore(int(data["memory_id"])),
                })
            if self.path == "/api/memory/delete":
                if data.get("approved") is not True:
                    raise ValueError("Memory deletion requires explicit approval")
                return self._json({
                    "ok": True, "deleted": self.system.memory.delete(int(data["memory_id"])),
                })
            if self.path == "/api/knowledge":
                source_id = self.system.knowledge.ingest_text(
                    str(data["title"]), str(data["content"]), source_uri=data.get("source_uri"),
                    media_type=str(data.get("media_type", "text/plain")), metadata=data.get("metadata") or {},
                )
                return self._json({"ok": True, "source_id": source_id}, 201)
            if self.path == "/api/knowledge/delete":
                if data.get("approved") is not True:
                    raise ValueError("Knowledge-source deletion requires explicit approval")
                return self._json({
                    "ok": True,
                    "deleted": self.system.knowledge.delete_source(int(data["source_id"])),
                })
            if self.path == "/api/automations":
                automation_id = self.system.automations.create(
                    str(data["name"]), str(data["kind"]), dict(data["action"]),
                    schedule=data.get("schedule"), condition=data.get("condition"), next_run_at=data.get("next_run_at"),
                )
                return self._json({"ok": True, "automation_id": automation_id}, 201)
            if self.path == "/api/automations/run":
                runs = self.system.automation_runner.run_due()
                return self._json({"ok": True, "runs": runs})
            if self.path == "/api/automations/enable":
                changed = self.system.automations.set_enabled(
                    int(data["automation_id"]), bool(data["enabled"]),
                )
                return self._json({"ok": True, "changed": changed})
            if self.path == "/api/automations/delete":
                if data.get("approved") is not True:
                    raise ValueError("Automation deletion requires explicit approval")
                return self._json({
                    "ok": True,
                    "deleted": self.system.automations.delete(int(data["automation_id"])),
                })
            if self.path == "/api/builds":
                result = self.system.tools.execute(
                    "workspace_scaffold", data, allowed={"workspace_scaffold"},
                )
                return self._json({"ok": True, "build": result}, 201)
            self._json({"error": "not_found"}, 404)
        except ModelError as exc:
            self.system.presence.update("error", "Model unavailable")
            self._json({"ok": False, "error": str(exc), "retryable": exc.retryable}, 503 if exc.retryable else 424)
        except FileExistsError as exc:
            self._json({"ok": False, "error": str(exc), "error_type": type(exc).__name__}, 409)
        except (ValueError, KeyError, TypeError, ToolError, json.JSONDecodeError) as exc:
            self._json({"ok": False, "error": str(exc), "error_type": type(exc).__name__}, 400)
        except Exception as exc:
            self.system.presence.update("error", "Execution failed")
            self._json({"ok": False, "error": "Internal execution failure", "error_type": type(exc).__name__}, 500)


def serve(system: SparkleSystem, host: str, port: int) -> None:
    handler = type("ConfiguredSparkleHandler", (SparkleHandler,), {"system": system})
    server = ThreadingHTTPServer((host, port), handler)
    print(f"SPARKLE dashboard: http://{host}:{port}")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()
