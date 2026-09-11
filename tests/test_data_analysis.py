from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from sparkle.data_analysis import DataAnalysisError, DataAnalysisService, DataAnalysisTool


class DataAnalysisTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.service = DataAnalysisService(Path(self.temp.name) / "analysis.sqlite3")

    def test_csv_ingestion_infers_scalars_and_revision_conflicts(self):
        record = self.service.ingest(
            "sales_data",
            "region,units,price,active\nwest,2,5,true\neast,4,3,false\n",
            source_format="csv",
            operator="test",
        )
        self.assertEqual(record["row_count"], 2)
        self.assertEqual(record["sample"][0]["units"], 2)
        self.assertEqual(record["sample"][0]["price"], 5)
        self.assertIs(record["sample"][0]["active"], True)
        with self.assertRaisesRegex(DataAnalysisError, "revision conflict"):
            self.service.ingest(
                "sales_data", "x\n1\n", source_format="csv",
                expected_revision=0, operator="test",
            )

    def test_json_analysis_transform_summary_group_chart_and_history(self):
        source = json.dumps([
            {"region": "west", "units": 2, "price": 5},
            {"region": "east", "units": 4, "price": 3},
            {"region": "west", "units": 1, "price": 10},
        ])
        self.service.ingest("sales_json", source, source_format="json", operator="test")
        recipe = {
            "operations": [
                {"op": "compute", "output": "revenue", "left": "units", "operator": "multiply", "right_column": "price"},
                {"op": "filter", "column": "region", "operator": "eq", "value": "west"},
            ],
            "group": {"by": ["region"], "metrics": [{"column": "revenue", "op": "sum", "as": "revenue_sum"}]},
            "chart": {"kind": "bar", "x": "region", "y": "revenue"},
        }
        first = self.service.analyze("sales_json", recipe, operator="test")
        second = self.service.analyze("sales_json", recipe, operator="test")
        self.assertEqual(first["recipe_digest"], second["recipe_digest"])
        self.assertEqual(first["group"], [{"region": "west", "revenue_sum": 20.0}])
        self.assertEqual(first["summary"]["revenue"]["numeric"]["sum"], 20.0)
        self.assertEqual(first["chart"]["kind"], "bar")
        self.assertEqual(len(self.service.history("sales_json")), 2)

    def test_tool_is_read_only_and_archive_blocks_analysis(self):
        self.service.ingest("tiny_data", '[{"x":1},{"x":2}]', source_format="json", operator="test")
        tool = DataAnalysisTool(self.service)
        result = tool.run({"dataset": "tiny_data", "recipe": {"operations": [{"op": "limit", "count": 1}]}})
        self.assertNotIn("analysis_id", result)
        self.assertEqual(self.service.history("tiny_data"), [])
        archived = self.service.archive("tiny_data", expected_revision=1, operator="test")
        self.assertTrue(archived["archived"])
        with self.assertRaisesRegex(DataAnalysisError, "Unknown active dataset"):
            tool.run({"dataset": "tiny_data", "recipe": {}})

    def test_bounds_and_invalid_compute_fail_closed(self):
        with self.assertRaises(DataAnalysisError):
            self.service.ingest("Bad Name", '[{"x":1}]', source_format="json")
        self.service.ingest("safe_data", '[{"x":1}]', source_format="json")
        with self.assertRaisesRegex(DataAnalysisError, "division by zero"):
            self.service.analyze("safe_data", {
                "operations": [{"op": "compute", "output": "z", "left": "x", "operator": "divide", "right_value": 0}]
            })


if __name__ == "__main__":
    unittest.main()
