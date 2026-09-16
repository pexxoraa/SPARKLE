from __future__ import annotations

from pathlib import Path
import re
import unittest


ROOT = Path(__file__).resolve().parents[1]
REQUIRED_DOCUMENTS = {
    "README.md",
    "docs/ARCHITECTURE.md",
    "docs/INSTALLATION.md",
    "docs/CONFIGURATION.md",
    "docs/AI_ENVIRONMENT.md",
    "docs/MODEL_MANAGEMENT.md",
    "docs/FOUNDATION_AUDIT.md",
    "docs/INTERACTION.md",
    "docs/MEMORY.md",
    "docs/KNOWLEDGE.md",
    "docs/DATA_FLOW.md",
    "docs/AGENTS.md",
    "docs/APPLICATION_BUILDER.md",
    "docs/AI_BUILDER.md",
    "docs/AGENT_BUILDER.md",
    "docs/VOICE.md",
    "docs/DASHBOARD.md",
    "docs/MOTION.md",
    "docs/AUTOMATION.md",
    "docs/TESTING.md",
    "docs/TROUBLESHOOTING.md",
    "docs/DEVELOPMENT.md",
    "docs/USER_GUIDE.md",
    "docs/PROJECTS.md",
    "docs/SKILLS.md",
}
MARKDOWN_LINK = re.compile(r"\[[^\]]+\]\(([^)]+)\)")


class DocumentationContractTests(unittest.TestCase):
    def test_master_directive_document_inventory_is_complete(self):
        missing = sorted(
            path for path in REQUIRED_DOCUMENTS if not (ROOT / path).is_file()
        )
        self.assertEqual(missing, [])

    def test_relative_markdown_links_resolve_to_repository_files(self):
        unresolved: list[str] = []
        documents = [ROOT / "README.md", *sorted((ROOT / "docs").glob("*.md"))]
        for document in documents:
            for target in MARKDOWN_LINK.findall(document.read_text(encoding="utf-8")):
                target = target.split("#", 1)[0]
                if not target or "://" in target or target.startswith("mailto:"):
                    continue
                resolved = (document.parent / target).resolve()
                try:
                    resolved.relative_to(ROOT)
                except ValueError:
                    unresolved.append(f"{document.relative_to(ROOT)} -> {target}")
                    continue
                if not resolved.exists():
                    unresolved.append(f"{document.relative_to(ROOT)} -> {target}")
        self.assertEqual(unresolved, [])

    def test_release_version_is_consistent_in_user_facing_status_documents(self):
        pyproject = (ROOT / "pyproject.toml").read_text(encoding="utf-8")
        match = re.search(r'^version = "([^"]+)"$', pyproject, re.MULTILINE)
        self.assertIsNotNone(match)
        package_version = str(match.group(1))
        display_version = re.sub(r"a(\d+)$", r"-alpha.\1", package_version)
        self.assertIn(
            f'__version__ = "{display_version}"',
            (ROOT / "src" / "sparkle" / "__init__.py").read_text(
                encoding="utf-8",
            ),
        )
        self.assertIn(
            f"Current release: `{display_version}`",
            (ROOT / "README.md").read_text(encoding="utf-8"),
        )
        self.assertIn(
            f"| SPARKLE version | {display_version} |",
            (ROOT / "docs" / "BUILD_STATE.md").read_text(encoding="utf-8"),
        )
        self.assertTrue(
            (ROOT / "docs" / "RELEASE_REPORT.md").read_text(encoding="utf-8")
            .startswith(f"# {display_version} verification report\n"),
        )
        changelog = (ROOT / "CHANGELOG.md").read_text(encoding="utf-8")
        first_release = re.search(r"^## ([^ ]+) [-—]", changelog, re.MULTILINE)
        self.assertIsNotNone(first_release)
        self.assertEqual(first_release.group(1), display_version)

        short_version = ".".join(package_version.split(".")[:2])
        source_markers = {
            "src/sparkle/api.py": f"SPARKLE/{short_version}",
            "src/sparkle/providers/minimax.py": f"SPARKLE/{short_version}",
            "src/sparkle/worker_service.py": f"SPARKLE-Worker/{short_version}",
            "src/sparkle/system.py": f'"version": "{display_version}"',
        }
        for path, marker in source_markers.items():
            with self.subTest(path=path):
                self.assertIn(
                    marker,
                    (ROOT / path).read_text(encoding="utf-8"),
                )

    def test_build_state_keeps_required_truth_fields_and_honest_limits(self):
        build_state = (ROOT / "docs" / "BUILD_STATE.md").read_text(
            encoding="utf-8",
        )
        for field in (
            "Current phase", "Current task", "Completed", "In progress",
            "Blocked", "Failed tests", "Next action",
            "Estimated directive completion",
        ):
            with self.subTest(field=field):
                self.assertIn(f"| {field} |", build_state)
        acceptance = (ROOT / "docs" / "ACCEPTANCE.md").read_text(
            encoding="utf-8",
        )
        self.assertNotIn("| PARTIAL |", acceptance)
        self.assertIn("EXTERNALLY BLOCKED", acceptance)
        self.assertIn("DEFERRED — PUBLIC DEPLOYMENT", acceptance)
        self.assertIn("semantic", acceptance.lower())

    def test_current_acceptance_ledgers_preserve_external_boundaries(self):
        audit = (ROOT / "docs" / "CURRENT_AUDIT.md").read_text(
            encoding="utf-8",
        )
        level3 = (ROOT / "docs" / "LEVEL3_STATUS.md").read_text(
            encoding="utf-8",
        )
        security = (ROOT / "docs" / "SECURITY.md").read_text(
            encoding="utf-8",
        )
        self.assertIn("Live browser host acceptance | VERIFIED", audit)
        self.assertIn("Level-3 private/local acceptance: READY", level3)
        self.assertIn("Deployment: FROZEN", level3)
        self.assertIn("DEFERRED — PUBLIC DEPLOYMENT", level3)
        self.assertIn("worker remains loopback-only", level3)
        self.assertIn("stable-host identity digest", security)
        self.assertIn("0700", security)
        self.assertIn("0600", security)

    def test_current_ledgers_match_verified_level3_and_browser_state(self):
        audit = (ROOT / "docs" / "CURRENT_AUDIT.md").read_text(encoding="utf-8")
        acceptance = (ROOT / "docs" / "ACCEPTANCE.md").read_text(encoding="utf-8")
        build_state = (ROOT / "docs" / "BUILD_STATE.md").read_text(encoding="utf-8")
        level3 = (ROOT / "docs" / "LEVEL3_STATUS.md").read_text(encoding="utf-8")
        execution = (ROOT / "docs" / "EXECUTION.md").read_text(encoding="utf-8")
        worker = (ROOT / "docs" / "WORKER.md").read_text(encoding="utf-8")
        security = (ROOT / "docs" / "SECURITY.md").read_text(encoding="utf-8")
        backlog = (ROOT / "docs" / "capability_backlog.json").read_text(encoding="utf-8")

        for current in (audit, acceptance, build_state, level3):
            self.assertIn("32643a826dc394c9a86244fa724932c797fce08a", current)
            self.assertNotIn("CI #182", current)
            self.assertNotIn("exact-head publication/CI is still pending", current)
        self.assertIn("local worker restart/recovery: VERIFIED", level3)
        self.assertIn("Level-3 private/local acceptance: READY", level3)
        self.assertIn("DEFERRED — PUBLIC DEPLOYMENT", level3)
        self.assertIn("signed cancellation through `POST /v1/jobs/cancel`", execution)
        self.assertNotIn("not claimed as implemented", execution)
        self.assertIn("`ProtectKernelLogs=no`", worker)
        self.assertIn("`ProtectKernelLogs=no`", security)
        self.assertNotIn("module/log\n  protections", security)
        self.assertNotIn('"capability": "browser_live_host_acceptance"', backlog)
        self.assertIn("Live browser host acceptance is VERIFIED", backlog)


if __name__ == "__main__":
    unittest.main()
