from __future__ import annotations

import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from sparkle.config import AppConfig
from sparkle.presence import MotionAdapter, MotionCommand, MotionResult, PresenceEngine, PresenceStore
from sparkle.providers.mock import DeterministicAdapter
from sparkle.registry import ModelRegistry
from sparkle.system import SparkleSystem


class DeterministicMotion(MotionAdapter):
    def capabilities(self): return {"wave"}
    def execute(self, command): return MotionResult(True, f"executed:{command.kind}")


class ExtensionIntegrationTests(unittest.TestCase):
    def test_presence_persists_and_motion_requires_adapter_and_approval(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "presence.sqlite3"
            first = PresenceEngine(PresenceStore(path), DeterministicMotion())
            first.update("working", "Inspecting repository", agent="software_engineering", trace_id="SPK-TRACE")
            second = PresenceEngine(PresenceStore(path), DeterministicMotion())
            status = second.status()
            self.assertEqual(status["mode"], "working")
            self.assertTrue(status["persistent"])
            self.assertEqual(status["motion_capabilities"], ["wave"])
            with self.assertRaises(ValueError):
                second.execute_motion(MotionCommand("wave", {}), approved=False)
            result = second.execute_motion(MotionCommand("wave", {}), approved=True, actor="test")
            self.assertTrue(result["completed"])
            self.assertFalse(result["hardware_verified"])

    def test_system_registers_research_and_engineering_read_tools(self):
        with tempfile.TemporaryDirectory() as directory, patch.dict(os.environ,{"SPARKLE_DATA_DIR":directory},clear=False):
            registry=ModelRegistry(); registry.inject(registry.active_id,DeterministicAdapter())
            system=SparkleSystem(config=AppConfig("127.0.0.1",0,4,5,5,False,False),model_registry=registry)
            self.assertIn("research_workspace",system.tools.names)
            self.assertIn("engineering_inspect",system.tools.names)
            self.assertIn("research_workspace",system.agents.get("research").tools)
            self.assertIn("engineering_inspect",system.agents.get("coding").tools)
            self.assertEqual(system.status()["research"]["status"],"ready")
            self.assertEqual(system.status()["engineering"]["status"],"ready")
            self.assertTrue(system.status()["presence"]["persistent"])


if __name__=="__main__": unittest.main()
