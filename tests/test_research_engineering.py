from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from sparkle.engineering import EngineeringReadTool, EngineeringWorkflowError, RepositoryEngineeringService
from sparkle.knowledge_evidence import citation_digest
from sparkle.research import ResearchReadTool, ResearchService, ResearchWorkflowError
from sparkle.storage import KnowledgeStore


class ResearchWorkflowTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(); self.addCleanup(self.temp.cleanup)
        root = Path(self.temp.name)
        self.knowledge = KnowledgeStore(root / "knowledge.sqlite3")
        self.research = ResearchService(self.knowledge, root / "research.sqlite3")

    def test_plan_evidence_claim_report_lifecycle(self):
        self.knowledge.ingest_text("Source", "Exact evidence about the implementation.", source_uri="fixture://source")
        row = self.knowledge.search("implementation", limit=1)[0]
        project = self.research.create({
            "name":"implementation_research","title":"Implementation research",
            "objective":"Determine what is supported by stored evidence.",
            "questions":["What does the source establish?"],
        }, actor="test")
        self.assertEqual(project["status"], "planning")
        self.research.transition("implementation_research","collecting",expected_revision=1,actor="test")
        evidence = self.research.add_evidence("implementation_research", {
            "source_id":row["source_id"],"chunk_id":row["chunk_id"],
            "digest":citation_digest(row),"quote":"Exact evidence about the implementation."
        }, source_quality="high", quality_rationale="Operator-owned local source", actor="test")
        self.assertEqual(evidence["citation_integrity"], "VERIFIED")
        self.assertEqual(evidence["claim_truth"], "INCONCLUSIVE")
        self.research.transition("implementation_research","synthesizing",expected_revision=2,actor="test")
        claim = self.research.add_claim("implementation_research", {
            "kind":"fact","statement":"The stored source contains the quoted implementation evidence.",
            "evidence_ids":[evidence["id"]],"uncertainty":"low","notes":"This is a stored-text claim, not external truth."
        }, actor="test")
        self.assertEqual(claim["evidence_ids"], [evidence["id"]])
        complete = self.research.transition("implementation_research","complete",expected_revision=3,actor="test")
        self.assertEqual(complete["status"], "complete")
        report = self.research.report("implementation_research")
        self.assertFalse(report["claim_truth_established"])
        self.assertIn(evidence["id"], report["report"])
        tool = ResearchReadTool(self.research)
        self.assertEqual(tool.run({"project":"implementation_research"})["status"], "complete")

    def test_rejected_citation_and_unsupported_fact_fail_closed(self):
        self.knowledge.ingest_text("Source", "Stored content.", source_uri="fixture://source")
        row = self.knowledge.search("Stored", limit=1)[0]
        self.research.create({"name":"safe_research","title":"Safe research","objective":"Keep evidence bounded.","questions":["What is stored?"]})
        self.research.transition("safe_research","collecting",expected_revision=1)
        with self.assertRaisesRegex(ResearchWorkflowError,"integrity was rejected"):
            self.research.add_evidence("safe_research",{"source_id":row["source_id"],"chunk_id":row["chunk_id"],"digest":"0"*64,"quote":"Stored content."})
        self.research.transition("safe_research","synthesizing",expected_revision=2)
        with self.assertRaisesRegex(ResearchWorkflowError,"Factual claims require"):
            self.research.add_claim("safe_research",{"kind":"fact","statement":"Unsupported fact","evidence_ids":[],"uncertainty":"high","notes":"No evidence available"})


class EngineeringWorkflowTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(); self.addCleanup(self.temp.cleanup)
        root = Path(self.temp.name); self.repo = root / "repo"; self.repo.mkdir()
        (self.repo / "app.py").write_text("print('ok')\n", encoding="utf-8")
        (self.repo / "config.json").write_text('{"enabled":true}\n', encoding="utf-8")
        self.service = RepositoryEngineeringService(self.repo, root / "engineering.sqlite3")

    def test_snapshot_file_identity_workflow_and_readiness(self):
        snapshot = self.service.snapshot()
        self.assertEqual(snapshot["file_count"], 2)
        inspected = self.service.inspect_file("app.py")
        self.assertEqual(len(inspected["sha256"]), 64)
        item = self.service.create_work_item({
            "name":"safe_change","title":"Safe change","objective":"Implement a bounded repository change.",
            "requirements":["Preserve behavior"],"design":["Use a narrow diff"],"files":["app.py"],
            "risks":["Regression"],"tests":["Compile app.py"],"debt":["None identified"],"priority":"P1",
        }, actor="test")
        self.assertEqual(item["state"], "planned")
        self.service.transition("safe_change","in_progress",expected_revision=1,actor="test")
        self.service.transition("safe_change","ready_for_review",expected_revision=2,actor="test")
        completed = self.service.transition("safe_change","complete",expected_revision=3,release_notes="Implemented and checked.",actor="test")
        self.assertEqual(completed["state"], "complete")
        readiness = self.service.readiness("safe_change")
        self.assertTrue(readiness["ready"])
        self.assertFalse(readiness["execution_verified"])
        tool = EngineeringReadTool(self.service)
        self.assertEqual(tool.run({"operation":"work_item","name":"safe_change"})["state"], "complete")

    def test_paths_and_completion_fail_closed(self):
        with self.assertRaises(EngineeringWorkflowError): self.service.inspect_file("../outside")
        self.service.create_work_item({
            "name":"unfinished","title":"Unfinished","objective":"Track unfinished work.",
            "requirements":["Requirement"],"design":["Design"],"files":["app.py"],
            "risks":["Risk"],"tests":["Test"],"debt":[],"priority":"P2",
        })
        self.service.transition("unfinished","in_progress",expected_revision=1)
        self.service.transition("unfinished","ready_for_review",expected_revision=2)
        with self.assertRaisesRegex(EngineeringWorkflowError,"release notes"):
            self.service.transition("unfinished","complete",expected_revision=3)


if __name__ == "__main__": unittest.main()
