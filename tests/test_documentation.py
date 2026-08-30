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
            f"Current release: `{display_version}`",
            (ROOT / "README.md").read_text(encoding="utf-8"),
        )
        self.assertIn(
            f"| SPARKLE version | {display_version} |",
            (ROOT / "docs" / "BUILD_STATE.md").read_text(encoding="utf-8"),
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
        self.assertIn("PARTIAL", acceptance)
        self.assertIn("BLOCKED", acceptance)
        self.assertIn("semantic", acceptance.lower())


if __name__ == "__main__":
    unittest.main()
