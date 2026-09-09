"""Credential-free integration doubles; never real NVIDIA evidence."""
import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from benchmarks.agents import run_agents
from benchmarks.live import RUNTIME_FIELDS, run_live, task_evidence
from sparkle.contracts import Message, ModelRequest
from sparkle.model import ModelError, ModelSelectionError
from sparkle.providers.nvidia import NVIDIAChatCompletionsAdapter
from sparkle.registry import ModelRegistry, ModelRouter
from sparkle.secrets import SecretResolver
from sparkle.storage import StorageConnectionError
from tests.helpers import FakeHTTPResponse
from tests.test_nvidia_adapter import config


class BenchmarkEvidenceTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.env = patch.dict(os.environ, {'SPARKLE_DATA_DIR': str(self.root / 'state')})
        self.env.start(); self.addCleanup(self.env.stop)

    def registry(self, *, key=True):
        return ModelRegistry(secrets=SecretResolver({'NVIDIA_API_KEY': 'synthetic-private-key'} if key else {}))

    def test_missing_key_is_configuration_failure_without_http(self):
        calls = []
        adapter = NVIDIAChatCompletionsAdapter(config(), SecretResolver({}), opener=lambda *a, **k: calls.append(a))
        for invoke in (adapter.complete, lambda r: list(adapter.stream(r))):
            with self.assertRaises(ModelError) as caught:
                invoke(ModelRequest(messages=[Message('user', 'hello')]))
            self.assertEqual(caught.exception.category, 'configuration_failure')
            self.assertFalse(caught.exception.retryable)
        self.assertEqual(calls, [])

    def test_no_routable_model_is_not_provider_outage(self):
        registry = self.registry(key=False)
        with self.assertRaises(ModelSelectionError) as caught:
            ModelRouter(registry).complete(ModelRequest(messages=[Message('user', 'hello')]))
        self.assertEqual(caught.exception.category, 'routing_failure')
        self.assertEqual(registry.runtime.recent(), [])

    def test_real_adapter_plumbing_keeps_usage_but_not_response_content(self):
        calls = []
        def open_response(request, timeout):
            calls.append(json.loads(request.data))
            return FakeHTTPResponse({'id': 'fixture-request', 'model': config()['model_id'],
                'choices': [{'finish_reason': 'stop', 'message': {'content': '{"answer":999,"private":"synthetic-private-key"}'}}],
                'usage': {'prompt_tokens': 7, 'completion_tokens': 4}})
        events = []
        with patch('sparkle.providers.nvidia.deadline_urlopen', side_effect=open_response):
            report = run_agents(self.root / 'tasks', registry_factory=self.registry,
                                observer=lambda r, q: events.append(task_evidence(r, q)))
        self.assertEqual(len(calls), 12)
        self.assertEqual(len(events), 12)
        self.assertEqual(report['pass_rate'], 0)
        self.assertFalse(report['live_provider_verified'])
        self.assertTrue(all(e['stage'] == 'validation' for e in events))
        for event in events:
            evidence = event['model_requests'][0]
            self.assertEqual(evidence['input_tokens'], 7)
            self.assertEqual(evidence['output_tokens'], 4)
            self.assertEqual(evidence['provider_request_id'], 'fixture-request')
            self.assertGreaterEqual(evidence['latency_ms'], 0)
        self.assertNotIn('synthetic-private-key', json.dumps(events))

    def test_timeout_evidence_preserves_failure_and_all_tasks(self):
        events = []
        with patch('sparkle.providers.nvidia.deadline_urlopen', side_effect=TimeoutError('synthetic-private-key')), \
             patch('sparkle.providers.nvidia.time.sleep'):
            # Factory disables backoff in this local HTTP double only.
            def registry():
                result = self.registry()
                adapter = result.adapter(); adapter._base_delay = 0
                return result
            report = run_agents(self.root / 'tasks', registry_factory=registry,
                                observer=lambda r, q: events.append(task_evidence(r, q)))
        self.assertEqual(len(events), 12)
        self.assertEqual(report['pass_rate'], 0)
        self.assertTrue(all(e['stage'] == 'provider_runtime' and e['error_type'] == 'timeout' for e in events))
        self.assertTrue(all(e['model_requests'][0]['attempts'] == 3 for e in events))
        self.assertNotIn('synthetic-private-key', json.dumps(events))

    def test_live_opt_in_and_missing_credentials_do_not_invoke_tasks(self):
        output = self.root / 'evidence.jsonl'
        with patch.dict(os.environ, {'SPARKLE_BENCHMARK_LIVE': '0'}):
            with self.assertRaises(ValueError): run_live(output)
        self.assertFalse(output.exists())
        with patch.dict(os.environ, {'SPARKLE_BENCHMARK_LIVE': '1'}), \
             patch('benchmarks.live.ModelRegistry', side_effect=lambda _: self.registry(key=False)), \
             patch('benchmarks.live.run_agents') as tasks:
            self.assertEqual(run_live(output), 2)
            tasks.assert_not_called()
        events = [json.loads(line) for line in output.read_text().splitlines()]
        self.assertEqual(events[-1]['error_type'], 'configuration_failure')
        self.assertEqual(output.stat().st_mode & 0o777, 0o600)
        self.assertEqual(os.environ['SPARKLE_DATA_DIR'], str(self.root / 'state'))

    def test_setup_failure_is_incomplete_and_does_not_export_exception(self):
        output = self.root / 'failed.jsonl'
        with patch.dict(os.environ, {'SPARKLE_BENCHMARK_LIVE': '1'}), \
             patch('benchmarks.live.ModelRegistry', side_effect=StorageConnectionError()):
            self.assertEqual(run_live(output), 2)
        last = json.loads(output.read_text().splitlines()[-1])
        self.assertEqual(last['event'], 'incomplete')
        self.assertEqual(last['error_type'], 'storage_unavailable')
        self.assertEqual(last['completed_tasks'], 0)

    def test_existing_evidence_and_symlink_are_never_overwritten(self):
        output = self.root / 'existing.jsonl'; output.write_text('preserve')
        link = self.root / 'link.jsonl'; link.symlink_to(output)
        with patch.dict(os.environ, {'SPARKLE_BENCHMARK_LIVE': '1'}):
            for target in (output, link):
                with self.assertRaises(FileExistsError): run_live(target)
        self.assertEqual(output.read_text(), 'preserve')

    def test_observer_is_incremental_and_cannot_change_scoring(self):
        class Interrupted(Exception): pass
        seen = []
        def observe(row, _requests):
            seen.append(row['task_id'])
            raise Interrupted('observer failure')
        with self.assertRaises(Interrupted):
            run_agents(self.root / 'tasks', observer=observe)
        self.assertEqual(len(seen), 1)
        self.assertEqual(os.environ['SPARKLE_DATA_DIR'], str(self.root / 'state'))

    def test_partial_evidence_survives_interrupt_and_redacts_echoed_key(self):
        output = self.root / 'partial.jsonl'
        def interrupted(_root, *, registry_factory, observer):
            request = dict.fromkeys(RUNTIME_FIELDS)
            request.update(provider_request_id='synthetic-private-key', status='success')
            observer({'task_id': 'fixture', 'agent': 'personal', 'failure_reason': None,
                      'execution_success': True, 'protocol_success': True, 'outcome_correct': True,
                      'validation_result': {'validation_status': 'validated'}, 'score': 1,
                      'trace_completed': True, 'tool_events': [], 'retrieval_events': {},
                      'memory_events': {'count': 0}}, [request])
            raise KeyboardInterrupt()
        with patch.dict(os.environ, {'SPARKLE_BENCHMARK_LIVE': '1'}), \
             patch('benchmarks.live.ModelRegistry', side_effect=lambda _: self.registry()), \
             patch('benchmarks.live.run_agents', side_effect=interrupted):
            self.assertEqual(run_live(output), 2)
        text = output.read_text()
        self.assertNotIn('synthetic-private-key', text)
        events = [json.loads(line) for line in text.splitlines()]
        self.assertEqual([e['event'] for e in events], ['start', 'task', 'incomplete'])
        self.assertEqual(events[-1]['completed_tasks'], 1)
        self.assertEqual(events[-1]['error_type'], 'interrupted')

    def test_http_authentication_and_malformed_response_stay_distinct(self):
        import urllib.error
        for failure, expected in ((urllib.error.HTTPError('https://example.invalid', 401, 'synthetic-private-key', {}, None), 'authentication_failure'),
                                  (None, 'malformed_response')):
            def opener(*args, **kwargs):
                if failure is not None: raise failure
                return FakeHTTPResponse({'choices': []})
            adapter = NVIDIAChatCompletionsAdapter(config(), SecretResolver({'NVIDIA_API_KEY': 'synthetic-private-key'}), opener=opener)
            with self.assertRaises(ModelError) as caught:
                adapter.complete(ModelRequest(messages=[Message('user', 'hello')]))
            self.assertEqual(caught.exception.category, expected)
            self.assertNotIn('synthetic-private-key', str(caught.exception))
