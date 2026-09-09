"""Optional live evaluation. Explicit opt-in may incur provider costs.

SPARKLE_BENCHMARK_LIVE=1 PYTHONPATH=src python -m unittest tests.test_benchmarks_live -v
Results are operator evidence; ordinary CI never sets this marker.
"""
import os
import unittest
from pathlib import Path

from benchmarks.live import run_live


@unittest.skipUnless(os.environ.get('SPARKLE_BENCHMARK_LIVE') == '1', 'Live provider evaluation requires explicit opt-in and credentials')
class LiveAgentBenchmark(unittest.TestCase):
    def test_configured_provider_outcomes(self):
        output = Path(os.environ.get('SPARKLE_BENCHMARK_OUTPUT', 'live-agent-evidence.jsonl'))
        # Strict acceptance remains unchanged: every task must independently pass.
        self.assertEqual(run_live(output), 0, 'See content-free benchmark evidence at the configured output path')
