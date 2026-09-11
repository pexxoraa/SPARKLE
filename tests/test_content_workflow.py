from __future__ import annotations

import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from sparkle.config import AppConfig
from sparkle.content_workflow import ContentReadTool, ContentWorkflowError, ContentWorkflowService
from sparkle.providers.mock import DeterministicAdapter
from sparkle.registry import ModelRegistry
from sparkle.system import SparkleSystem


class ContentWorkflowTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        root = Path(self.temp.name)
        self.service = ContentWorkflowService(root / "content.sqlite3", root / "exports")

    def template(self):
        return {
            "name": "video_script", "title": "Video script", "kind": "script",
            "body": "Hook: {{hook}}\nBody: {{body}}", "variables": ["hook", "body"],
        }

    def test_template_render_create_transform_and_versioned_workflow(self):
        saved = self.service.save_template(self.template(), operator="test")
        self.assertEqual(saved["revision"], 1)
        item = self.service.create({
            "name": "launch_script", "title": "Launch", "kind": "script",
            "audience": "builders", "template": "video_script",
            "variables": {"hook": "Start here", "body": "Ship the feature"},
            "metadata": {"channel": "video"},
        }, operator="test")
        self.assertEqual(item["status"], "draft")
        self.assertIn("Start here", item["body"])
        transformed = self.service.transform(
            "launch_script", {"action": "replace", "old": "Ship the feature", "new": "Ship the verified feature"},
            expected_revision=1, operator="test",
        )
        self.assertEqual(transformed["revision"], 2)
        review = self.service.transition("launch_script", "review", expected_revision=2, operator="test")
        approved = self.service.transition("launch_script", "approved", expected_revision=3, operator="test")
        self.assertEqual(approved["status"], "approved")
        with self.assertRaisesRegex(ContentWorkflowError, "return to draft"):
            self.service.update("launch_script", {"body": "no"}, expected_revision=4, operator="test")
        draft = self.service.transition("launch_script", "draft", expected_revision=4, operator="test")
        self.assertEqual(draft["revision"], 5)
        self.assertEqual([row["revision"] for row in self.service.history("launch_script")], [5, 4, 3, 2, 1])

    def test_revision_conflicts_template_validation_and_export(self):
        self.service.save_template(self.template(), operator="test")
        with self.assertRaisesRegex(ContentWorkflowError, "revision conflict"):
            self.service.save_template(self.template(), expected_revision=0, operator="test")
        broken = self.template() | {"variables": ["hook"]}
        with self.assertRaisesRegex(ContentWorkflowError, "placeholders"):
            self.service.save_template(broken | {"name": "broken_template"}, operator="test")
        item = self.service.create({
            "name": "plain_post", "title": "Post", "kind": "post", "audience": "users", "body": "Hello",
        }, operator="test")
        exported = self.service.export("plain_post", "md", expected_revision=item["revision"])
        path = Path(self.temp.name) / "exports" / "plain_post.r1.md"
        self.assertTrue(path.is_file())
        self.assertEqual(path.read_text(encoding="utf-8"), "# Post\n\nHello\n")
        self.assertEqual(exported["bytes"], len(path.read_bytes()))

    def test_read_tool_cannot_mutate_and_search_is_bounded(self):
        self.service.create({
            "name": "research_brief", "title": "Research brief", "kind": "brief",
            "audience": "team", "body": "Evidence first",
        }, operator="test")
        tool = ContentReadTool(self.service)
        found = tool.run({"query": "research", "limit": 5})
        self.assertEqual(found["items"][0]["name"], "research_brief")
        fetched = tool.run({"name": "research_brief"})
        self.assertEqual(fetched["body"], "Evidence first")
        with self.assertRaises(ContentWorkflowError):
            tool.run({"name": "research_brief", "status": "approved"})
        self.assertEqual(self.service.get("research_brief")["revision"], 1)

    def test_runtime_registers_content_service_and_agent_permission(self):
        with patch.dict(os.environ, {"SPARKLE_DATA_DIR": self.temp.name}, clear=False):
            registry = ModelRegistry()
            registry.inject(registry.active_id, DeterministicAdapter())
            system = SparkleSystem(
                config=AppConfig("127.0.0.1", 0, 4, 5, 5, False, False),
                model_registry=registry,
            )
            self.assertIn("content_search", system.tools.names)
            self.assertIn("content_search", system.agents.get("content").tools)
            system.content_workflows.create({
                "name": "runtime_brief", "title": "Runtime", "kind": "brief",
                "audience": "operators", "body": "Persistent content",
            }, operator="test")
            result = system.tools.execute(
                "content_search", {"name": "runtime_brief"}, allowed=system.agents.get("content").tools,
            )
            self.assertEqual(result["title"], "Runtime")
            self.assertEqual(system.status()["content_workflows"]["items"], 1)


if __name__ == "__main__":
    unittest.main()
