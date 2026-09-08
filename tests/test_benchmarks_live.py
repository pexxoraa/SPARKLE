"""Optional live evaluation. Explicit opt-in may incur provider costs.

SPARKLE_BENCHMARK_LIVE=1 PYTHONPATH=src python -m unittest tests.test_benchmarks_live -v
Results are operator evidence; ordinary CI never sets this marker.
"""
import os
import tempfile
import unittest
from pathlib import Path

from benchmarks.agents import run_agents
from sparkle.registry import ModelRegistry


@unittest.skipUnless(os.environ.get('SPARKLE_BENCHMARK_LIVE') == '1', 'Live provider evaluation requires explicit opt-in and credentials')
class LiveAgentBenchmark(unittest.TestCase):
    def test_configured_provider_outcomes(self):
        registry=ModelRegistry()
        adapter=registry.adapter(registry.active_id)
        self.assertNotIn(adapter.provider, {'deterministic','scripted-outcome-test-harness'})
        with tempfile.TemporaryDirectory() as directory:
            report=run_agents(Path(directory),adapter_factory=lambda:adapter)
        # Strict acceptance; transport success alone cannot satisfy this test.
        self.assertEqual(report['pass_rate'],1.0, report['failure_categories'])
