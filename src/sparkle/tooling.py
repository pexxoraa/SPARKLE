from __future__ import annotations

import ast
import json
import math
import operator
from abc import ABC, abstractmethod
from pathlib import Path
from typing import Any

from sparkle.agents import AgentRegistry, AgentSpec
from sparkle.builders import WorkspaceManager
from sparkle.contracts import ToolDefinition
from sparkle.development import DevelopmentVerifier
from sparkle.storage import KnowledgeStore, MemoryStore


class ToolError(RuntimeError):
    pass


class Tool(ABC):
    name: str
    description: str
    parameters: dict[str, Any]

    @abstractmethod
    def run(self, arguments: dict[str, Any]) -> Any:
        raise NotImplementedError

    def definition(self) -> ToolDefinition:
        return ToolDefinition(self.name, self.description, self.parameters)


class ToolRegistry:
    def __init__(self):
        self._tools: dict[str, Tool] = {}

    def register(self, tool: Tool) -> None:
        if tool.name in self._tools:
            raise ValueError(f"Duplicate tool: {tool.name}")
        self._tools[tool.name] = tool

    def definitions(self, allowed: set[str] | None = None) -> list[ToolDefinition]:
        return [tool.definition() for name, tool in self._tools.items() if allowed is None or name in allowed]

    def execute(self, name: str, arguments: dict[str, Any], *, allowed: set[str] | None = None) -> Any:
        if allowed is not None and name not in allowed:
            raise ToolError(f"Tool is not allowed for this agent: {name}")
        try:
            tool = self._tools[name]
        except KeyError as exc:
            raise ToolError(f"Unknown tool: {name}") from exc
        return tool.run(arguments)

    def status(self) -> list[dict[str, Any]]:
        return [{"name": name, "enabled": True} for name in self._tools]

    @property
    def names(self) -> set[str]:
        return set(self._tools)


class CalculatorTool(Tool):
    name = "calculator"
    description = "Evaluate a finite arithmetic expression without executing code."
    parameters = {
        "type": "object",
        "properties": {"expression": {"type": "string"}},
        "required": ["expression"],
        "additionalProperties": False,
    }
    _binary = {
        ast.Add: operator.add, ast.Sub: operator.sub, ast.Mult: operator.mul,
        ast.Div: operator.truediv, ast.FloorDiv: operator.floordiv,
        ast.Mod: operator.mod, ast.Pow: operator.pow,
    }
    _unary = {ast.UAdd: operator.pos, ast.USub: operator.neg}

    def run(self, arguments: dict[str, Any]) -> float | int:
        expression = str(arguments.get("expression", ""))
        if not expression or len(expression) > 500:
            raise ToolError("Expression must contain 1-500 characters")
        try:
            tree = ast.parse(expression, mode="eval")
            result = self._evaluate(tree.body, depth=0)
        except (SyntaxError, ValueError, ZeroDivisionError, OverflowError) as exc:
            raise ToolError(f"Invalid arithmetic expression: {type(exc).__name__}") from exc
        if not isinstance(result, (int, float)) or not math.isfinite(float(result)):
            raise ToolError("Expression result must be finite")
        return result

    def _evaluate(self, node: ast.AST, *, depth: int) -> float | int:
        if depth > 20:
            raise ValueError("Expression is too deep")
        if isinstance(node, ast.Constant) and type(node.value) in {int, float}:
            return node.value
        if isinstance(node, ast.BinOp) and type(node.op) in self._binary:
            left = self._evaluate(node.left, depth=depth + 1)
            right = self._evaluate(node.right, depth=depth + 1)
            if isinstance(node.op, ast.Pow) and abs(float(right)) > 100:
                raise ValueError("Exponent is too large")
            return self._binary[type(node.op)](left, right)
        if isinstance(node, ast.UnaryOp) and type(node.op) in self._unary:
            return self._unary[type(node.op)](self._evaluate(node.operand, depth=depth + 1))
        raise ValueError("Unsupported expression")


class MemorySearchTool(Tool):
    name = "memory_search"
    description = "Search relevant personal memory records."
    parameters = {
        "type": "object",
        "properties": {"query": {"type": "string"}, "category": {"type": "string"}, "limit": {"type": "integer"}},
        "required": ["query"],
        "additionalProperties": False,
    }

    def __init__(self, store: MemoryStore):
        self.store = store

    def run(self, arguments: dict[str, Any]) -> Any:
        return self.store.search(
            str(arguments.get("query", "")), limit=int(arguments.get("limit", 5)),
            category=str(arguments["category"]) if arguments.get("category") else None,
        )


class MemoryWriteTool(Tool):
    name = "memory_write"
    description = "Store an explicit, durable user fact, goal, preference, decision, task, or learning record."
    parameters = {
        "type": "object",
        "properties": {
            "category": {"type": "string", "enum": sorted(MemoryStore.VALID_CATEGORIES - {"conversations"})},
            "key": {"type": "string"}, "value": {"type": "string"},
            "importance": {"type": "number", "minimum": 0, "maximum": 1},
        },
        "required": ["category", "key", "value"],
        "additionalProperties": False,
    }

    def __init__(self, store: MemoryStore):
        self.store = store

    def run(self, arguments: dict[str, Any]) -> Any:
        memory_id = self.store.remember(
            str(arguments["category"]), str(arguments["key"]), str(arguments["value"]),
            importance=float(arguments.get("importance", 0.5)), metadata={"source": "agent_tool"},
        )
        return {"stored": True, "memory_id": memory_id}


class KnowledgeSearchTool(Tool):
    name = "knowledge_search"
    description = "Search the user's ingested knowledge sources."
    parameters = {
        "type": "object",
        "properties": {"query": {"type": "string"}, "limit": {"type": "integer"}},
        "required": ["query"], "additionalProperties": False,
    }

    def __init__(self, store: KnowledgeStore):
        self.store = store

    def run(self, arguments: dict[str, Any]) -> Any:
        return self.store.search(str(arguments.get("query", "")), limit=int(arguments.get("limit", 5)))


class FileReadTool(Tool):
    name = "file_read"
    description = "Read a UTF-8 text file inside the configured SPARKLE workspace."
    parameters = {
        "type": "object", "properties": {"path": {"type": "string"}},
        "required": ["path"], "additionalProperties": False,
    }

    def __init__(self, root: Path, *, max_bytes: int = 200_000):
        self.root = root.resolve()
        self.max_bytes = max_bytes

    def run(self, arguments: dict[str, Any]) -> Any:
        relative = str(arguments.get("path", ""))
        target = (self.root / relative).resolve()
        if target != self.root and self.root not in target.parents:
            raise ToolError("Path escapes the configured workspace")
        if not target.is_file():
            raise ToolError("File does not exist")
        if target.stat().st_size > self.max_bytes:
            raise ToolError("File exceeds the read limit")
        try:
            return {"path": str(target.relative_to(self.root)), "content": target.read_text(encoding="utf-8")}
        except UnicodeDecodeError as exc:
            raise ToolError("File is not UTF-8 text") from exc


class WorkspaceScaffoldTool(Tool):
    name = "workspace_scaffold"
    description = "Create a bounded application workspace from an explicit UTF-8 file manifest."
    parameters = {
        "type": "object",
        "properties": {
            "project_name": {"type": "string"},
            "files": {"type": "object", "additionalProperties": {"type": "string"}},
            "overwrite": {"type": "boolean"},
            "approved": {"type": "boolean"},
        },
        "required": ["project_name", "files", "approved"],
        "additionalProperties": False,
    }

    def __init__(self, manager: WorkspaceManager):
        self.manager = manager

    def run(self, arguments: dict[str, Any]) -> Any:
        if arguments.get("approved") is not True:
            raise ToolError("Workspace creation requires explicit approval")
        files = arguments.get("files")
        if not isinstance(files, dict):
            raise ToolError("Workspace files must be an object")
        return self.manager.scaffold(
            str(arguments.get("project_name", "")),
            files,
            overwrite=bool(arguments.get("overwrite", False)),
        )


class WorkspaceVerifyTool(Tool):
    name = "workspace_verify"
    description = "Run bounded static checks against files in a generated application workspace."
    parameters = {
        "type": "object",
        "properties": {
            "project_name": {"type": "string"},
            "checks": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "type": {
                            "type": "string",
                            "enum": sorted(DevelopmentVerifier.VALID_CHECKS),
                        },
                        "path": {"type": "string"},
                    },
                    "required": ["type", "path"],
                    "additionalProperties": False,
                },
            },
            "approved": {"type": "boolean"},
        },
        "required": ["project_name", "checks", "approved"],
        "additionalProperties": False,
    }

    def __init__(self, verifier: DevelopmentVerifier):
        self.verifier = verifier

    def run(self, arguments: dict[str, Any]) -> Any:
        if arguments.get("approved") is not True:
            raise ToolError("Workspace verification requires explicit approval")
        checks = arguments.get("checks")
        if not isinstance(checks, list):
            raise ToolError("Workspace checks must be an array")
        return self.verifier.verify(str(arguments.get("project_name", "")), checks)


class AgentInstallTool(Tool):
    name = "agent_install"
    description = "Validate, persist, and hot-load a generated SPARKLE agent specification."
    parameters = {
        "type": "object",
        "properties": {
            "name": {"type": "string"},
            "capability": {
                "type": "string",
                "enum": sorted(AgentRegistry.CAPABILITIES),
            },
            "purpose": {"type": "string"},
            "instructions": {"type": "string"},
            "tools": {"type": "array", "items": {"type": "string"}},
            "keywords": {"type": "array", "items": {"type": "string"}},
            "replace": {"type": "boolean"},
            "approved": {"type": "boolean"},
        },
        "required": [
            "name", "capability", "purpose", "instructions", "tools",
            "keywords", "approved",
        ],
        "additionalProperties": False,
    }

    def __init__(self, registry: AgentRegistry):
        self.registry = registry

    def run(self, arguments: dict[str, Any]) -> Any:
        if arguments.get("approved") is not True:
            raise ToolError("Agent installation requires explicit approval")
        tools = arguments.get("tools")
        keywords = arguments.get("keywords")
        if not isinstance(tools, list) or not all(isinstance(item, str) for item in tools):
            raise ToolError("Agent tools must be a string array")
        if not isinstance(keywords, list) or not all(isinstance(item, str) for item in keywords):
            raise ToolError("Agent keywords must be a string array")
        spec = AgentSpec(
            name=str(arguments.get("name", "")),
            capability=str(arguments.get("capability", "")),
            purpose=str(arguments.get("purpose", "")),
            instructions=str(arguments.get("instructions", "")),
            tools=frozenset(tools),
            keywords=tuple(keywords),
        )
        installed = self.registry.install(spec, replace=bool(arguments.get("replace", False)))
        return {
            "installed": True,
            "name": installed.name,
            "capability": installed.capability,
            "tools": sorted(installed.tools),
        }


def safe_tool_result(value: Any, *, max_chars: int = 30_000) -> str:
    encoded = json.dumps(value, ensure_ascii=False, separators=(",", ":"), default=str)
    return encoded if len(encoded) <= max_chars else encoded[:max_chars] + "…[truncated]"
