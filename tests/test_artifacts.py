from __future__ import annotations

import contextlib
import io
import json
import os
import tempfile
import unittest
import zipfile
from pathlib import Path
from unittest.mock import patch

from sparkle.artifacts import ArtifactManager
from sparkle.builders import WorkspaceManager
from sparkle.cli import entrypoint, main
from sparkle.tooling import ToolError, WorkspacePackageTool


class ArtifactManagerTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.apps = self.root / "applications"
        self.workspace = WorkspaceManager(
            self.apps, self.root / "builds.sqlite3",
        )
        self.manager = ArtifactManager(
            self.apps,
            self.root / "artifacts",
            self.root / "artifacts.sqlite3",
        )

    def tearDown(self):
        self.temp.cleanup()

    def scaffold(self, name: str = "packaged_app"):
        return self.workspace.scaffold(name, {
            "README.md": "# Packaged app\n",
            "src/main.py": "def answer(): return 42\n",
            "assets/data.bin": "binary-compatible-text\n",
        })

    def artifact_path(self, value):
        return self.manager.artifact_root.joinpath(*value["artifact_name"].split("/"))

    def test_deterministic_content_addressed_zip_and_manifest(self):
        self.scaffold()
        first = self.manager.package("packaged_app")
        first_bytes = self.artifact_path(first).read_bytes()
        os.chmod(self.apps / "packaged_app/src/main.py", 0o755)
        second = self.manager.package("packaged_app")
        self.assertFalse(first["reused"])
        self.assertTrue(second["reused"])
        self.assertEqual(first["artifact_id"], second["artifact_id"])
        self.assertEqual(first["artifact_sha256"], second["artifact_sha256"])
        self.assertEqual(first_bytes, self.artifact_path(second).read_bytes())
        self.assertEqual(len(self.manager.list()), 1)

        with zipfile.ZipFile(io.BytesIO(first_bytes)) as archive:
            names = archive.namelist()
            self.assertEqual(names, sorted(names))
            self.assertIn(ArtifactManager.MANIFEST_PATH, names)
            manifest = json.loads(archive.read(ArtifactManager.MANIFEST_PATH))
            self.assertEqual(manifest["protocol_version"], "SPARKLE-ARTIFACT/1")
            self.assertEqual(manifest["source_digest"], first["source_digest"])
            self.assertEqual(manifest["verification_status"], "not_attested")
            for info in archive.infolist():
                self.assertEqual(info.date_time, (1980, 1, 1, 0, 0, 0))
                self.assertEqual((info.external_attr >> 16) & 0o777, 0o644)
                self.assertEqual(info.compress_type, zipfile.ZIP_STORED)

    def test_source_change_creates_new_immutable_artifact(self):
        self.scaffold()
        first = self.manager.package("packaged_app")
        (self.apps / "packaged_app/src/main.py").write_text(
            "def answer(): return 43\n", encoding="utf-8",
        )
        second = self.manager.package("packaged_app")
        self.assertNotEqual(first["artifact_id"], second["artifact_id"])
        self.assertNotEqual(first["source_digest"], second["source_digest"])
        self.assertTrue(self.artifact_path(first).is_file())
        self.assertTrue(self.artifact_path(second).is_file())

    def test_rejects_symlink_sensitive_reserved_and_oversized_source(self):
        self.scaffold("symlink_app")
        outside = self.root / "outside.txt"
        outside.write_text("outside", encoding="utf-8")
        (self.apps / "symlink_app/link.txt").symlink_to(outside)
        with self.assertRaisesRegex(ValueError, "symlink"):
            self.manager.package("symlink_app")

        for index, name in enumerate((
            ".env", "private.key", "app_secrets.json", "bad:name.txt",
        )):
            project = f"sensitive_{index}"
            self.workspace.scaffold(project, {"main.py": "pass\n"})
            (self.apps / project / name).write_text("value", encoding="utf-8")
            with self.subTest(name=name):
                with self.assertRaisesRegex(ValueError, "sensitive"):
                    self.manager.package(project)

        self.workspace.scaffold("reserved_app", {"main.py": "pass\n"})
        (self.apps / "reserved_app" / ArtifactManager.MANIFEST_PATH).write_text(
            "{}", encoding="utf-8",
        )
        with self.assertRaisesRegex(ValueError, "reserved"):
            self.manager.package("reserved_app")

        self.workspace.scaffold("collision_app", {"Readme.txt": "one\n"})
        (self.apps / "collision_app/readme.TXT").write_text("two\n", encoding="utf-8")
        with self.assertRaisesRegex(ValueError, "collide"):
            self.manager.package("collision_app")

        self.workspace.scaffold("large_app", {"main.py": "pass\n"})
        (self.apps / "large_app/large.bin").write_bytes(
            b"x" * (ArtifactManager.MAX_FILE_BYTES + 1),
        )
        with self.assertRaisesRegex(ValueError, "exceeds"):
            self.manager.package("large_app")

    def test_tampered_immutable_artifact_is_refused(self):
        self.scaffold()
        artifact = self.manager.package("packaged_app")
        self.artifact_path(artifact).write_bytes(b"tampered")
        with self.assertRaisesRegex(RuntimeError, "integrity"):
            self.manager.package("packaged_app")

    def test_deployment_records_are_append_only_and_explicitly_unverified(self):
        self.scaffold()
        artifact = self.manager.package("packaged_app")
        first = self.manager.record_deployment(
            artifact["artifact_id"], "staging", "server", "attempted",
        )
        second = self.manager.record_deployment(
            artifact["artifact_id"], "staging", "server", "reported_success",
        )
        self.assertNotEqual(first["deployment_id"], second["deployment_id"])
        self.assertEqual(second["verification_status"], "unverified")
        self.assertFalse(second["external_action_executed"])
        self.assertEqual(self.manager.list_deployments()[0]["project_name"], "packaged_app")
        for arguments in (
            (999, "staging", "server", "planned"),
            (artifact["artifact_id"], "https://target", "server", "planned"),
            (artifact["artifact_id"], "staging", "shell", "planned"),
            (artifact["artifact_id"], "staging", "server", "verified"),
        ):
            with self.subTest(arguments=arguments):
                with self.assertRaises(ValueError):
                    self.manager.record_deployment(*arguments)

    def test_package_tool_requires_approval_and_rejects_command_fields(self):
        self.scaffold()
        tool = WorkspacePackageTool(self.manager)
        with self.assertRaises(ToolError):
            tool.run({"project_name": "packaged_app"})
        with self.assertRaisesRegex(ToolError, "Unsupported"):
            tool.run({
                "project_name": "packaged_app", "approved": True,
                "command": "arbitrary",
            })
        self.assertEqual(
            tool.run({"project_name": "packaged_app", "approved": True})["status"],
            "packaged_unverified",
        )


class ArtifactCLITests(unittest.TestCase):
    def test_scaffold_package_and_record_unverified_deployment(self):
        with tempfile.TemporaryDirectory() as directory:
            manifest = Path(directory) / "app.json"
            manifest.write_text(json.dumps({
                "project_name": "cli_package",
                "files": {"main.py": "print('ready')\n"},
            }), encoding="utf-8")
            with patch.dict(os.environ, {"SPARKLE_DATA_DIR": directory}, clear=False):
                with contextlib.redirect_stdout(io.StringIO()):
                    self.assertEqual(main(["scaffold", str(manifest), "--approve"]), 0)
                package_output = io.StringIO()
                with contextlib.redirect_stdout(package_output):
                    self.assertEqual(main([
                        "package-workspace", "cli_package", "--approve",
                    ]), 0)
                artifact_id = json.loads(package_output.getvalue())["artifact"][
                    "artifact_id"
                ]
                deployment_output = io.StringIO()
                with contextlib.redirect_stdout(deployment_output):
                    self.assertEqual(main([
                        "record-deployment", str(artifact_id), "staging", "server",
                        "reported_success", "--approve",
                    ]), 0)
            deployment = json.loads(deployment_output.getvalue())["deployment"]
            self.assertEqual(deployment["verification_status"], "unverified")
            self.assertFalse(deployment["external_action_executed"])

    def test_cli_approval_failures_have_no_traceback(self):
        with tempfile.TemporaryDirectory() as directory:
            error = io.StringIO()
            with (
                patch.dict(os.environ, {"SPARKLE_DATA_DIR": directory}, clear=False),
                contextlib.redirect_stderr(error),
            ):
                self.assertEqual(entrypoint([
                    "package-workspace", "missing_app",
                ]), 1)
            self.assertIn("explicit approval", error.getvalue())
            self.assertNotIn("Traceback", error.getvalue())


if __name__ == "__main__":
    unittest.main()
