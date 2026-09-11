"""Output protocol regressions with explicit synthetic responses, never live evidence."""
import json
import tempfile
import unittest
from pathlib import Path

from benchmarks.agents import run_agents, ScriptedOutcomeAdapter, TASKS
from benchmarks.live import task_evidence
from benchmarks.protocol import response_shape, RESPONSE_CONTRACT
from sparkle.contracts import ModelResponse, ToolCall
from sparkle.providers.mock import DeterministicAdapter
from sparkle.providers.nvidia import NVIDIAChatCompletionsAdapter
from tests.test_nvidia_adapter import config


class TextAdapter(DeterministicAdapter):
    text = '{}'
    finish = 'stop'
    def complete(self, request):
        assert any(RESPONSE_CONTRACT == m.text_content for m in request.messages)
        return ModelResponse(self.text, self.model_id, self.provider, self.finish)


class BenchmarkProtocolTests(unittest.TestCase):
    def evaluate(self, text, finish='stop'):
        events = []
        class Adapter(TextAdapter): pass
        Adapter.text, Adapter.finish = text, finish
        with tempfile.TemporaryDirectory() as directory:
            report = run_agents(Path(directory), adapter_factory=Adapter,
                                observer=lambda r, q: events.append(task_evidence(r, q)))
        return report, events

    def assert_protocol_failure(self, text, category, finish='stop'):
        report, events = self.evaluate(text, finish)
        self.assertEqual(report['pass_rate'], 0)
        self.assertTrue(all(e['stage'] == 'protocol' for e in events))
        for event in events:
            diagnostic = event['diagnostics']
            self.assertTrue(event['execution_success'])
            self.assertFalse(event['protocol_success'])
            self.assertTrue(diagnostic['json_parsing_attempted'])
            self.assertEqual(diagnostic['final_response']['format_category'], category)
        return events

    def test_valid_structured_answer_keeps_independent_rejection(self):
        report, events = self.evaluate('{"answer":999}')
        self.assertEqual(report['pass_rate'], 0)
        self.assertTrue(all(e['protocol_success'] and e['stage'] == 'validation' for e in events))
        self.assertTrue(all(e['validation_checks'] for e in events))
        budget = events[0]
        self.assertEqual(next(c for c in budget['validation_checks'] if c['key'] == 'answer')['status'], 'rejected')

    def test_native_tool_call_followed_by_structured_answer(self):
        fixture = json.loads(TASKS.read_text())
        scripts = iter(fixture['tasks'])
        events = []
        with tempfile.TemporaryDirectory() as directory:
            report = run_agents(Path(directory), adapter_factory=lambda: ScriptedOutcomeAdapter(next(scripts)['script']),
                                observer=lambda r, q: events.append(task_evidence(r, q)))
        self.assertEqual(report['pass_rate'], 1)
        for event in events:
            responses = event['diagnostics']['model_responses']
            self.assertEqual(len(responses), 2)
            self.assertTrue(responses[0]['tool_calls_present'])
            self.assertFalse(responses[1]['tool_calls_present'])
            self.assertEqual(responses[1]['format_category'], 'json_object')

    def test_markdown_json_is_not_automatically_extracted(self):
        self.assert_protocol_failure('```json\n{"answer":110}\n```', 'markdown_fence')

    def test_malformed_json(self):
        events = self.assert_protocol_failure('{"answer":', 'malformed_or_extra_json')
        self.assertTrue(events[0]['diagnostics']['json_parsing_failed'])
        self.assertIsInstance(events[0]['diagnostics']['final_response']['json_parse_error']['position'], int)

        class EarlyFailure(TextAdapter):
            def complete(self, request):
                raise json.JSONDecodeError('synthetic private error', '', 0)
        early = []
        with tempfile.TemporaryDirectory() as directory:
            run_agents(Path(directory), adapter_factory=EarlyFailure,
                       observer=lambda r, q: early.append(task_evidence(r, q)))
        self.assertTrue(all(e['stage'] == 'execution' for e in early))
        self.assertTrue(all(not e['diagnostics']['json_parsing_attempted'] for e in early))
        self.assertTrue(all(not e['diagnostics']['json_parsing_failed'] for e in early))
        self.assertTrue(all(e['diagnostics']['runtime_exception_type'] == 'JSONDecodeError' for e in early))
        self.assertNotIn('synthetic private error', json.dumps(early))

    def test_empty_response(self):
        self.assert_protocol_failure('', 'empty')

    def test_truncated_response_even_when_json_is_parseable(self):
        events = self.assert_protocol_failure('{"answer":110}', 'json_object', 'length')
        self.assertFalse(events[0]['diagnostics']['json_parsing_failed'])
        self.assertTrue(events[0]['diagnostics']['final_response']['truncated'])

    def test_natural_language_response(self):
        self.assert_protocol_failure('The answer is 110.', 'natural_language_or_unclassified')

    def test_reasoning_and_json_are_not_silently_discarded(self):
        events = self.assert_protocol_failure('<think>private thought</think>{"answer":110}', 'reasoning_markup')
        encoded = json.dumps(events)
        self.assertNotIn('private thought', encoded)
        self.assertNotIn('<think>', encoded)

    def test_valid_non_object_json_is_schema_mismatch(self):
        self.assert_protocol_failure('[110]', 'json_non_object')

    def test_extra_text_around_json_is_not_accepted(self):
        self.assert_protocol_failure('Result: {"answer":110}', 'text_with_json_marker')

    def test_repeated_tools_get_specific_runtime_code(self):
        class Loop(TextAdapter):
            def complete(self, request):
                return ModelResponse('', self.model_id, self.provider, 'tool_use',
                    tool_calls=[ToolCall('repeat', 'calculator', {'expression': '1+1'})])
        events = []
        with tempfile.TemporaryDirectory() as directory:
            report = run_agents(Path(directory), adapter_factory=Loop,
                                observer=lambda r, q: events.append(task_evidence(r, q)))
        self.assertEqual(report['failure_categories'], {'orchestrator_tool_round_limit': 12})
        for event in events:
            self.assertEqual(event['stage'], 'orchestrator')
            self.assertEqual(event['diagnostics']['runtime_code'], 'tool_round_limit')
            # Duplicate-call no-progress detection forces a tools-disabled recovery
            # before exhausting every ordinary round. This adapter ignores that
            # contract, so the orchestrator still fails closed with the same code.
            self.assertEqual(len(event['diagnostics']['model_responses']), 4)
            self.assertFalse(event['diagnostics']['json_parsing_attempted'])

    def test_nvidia_reasoning_separate_from_content_and_tool_normalization(self):
        response = NVIDIAChatCompletionsAdapter._parse_response({
            'model': config()['model_id'], 'choices': [{'finish_reason': 'tool_calls',
            'message': {'content': None, 'reasoning_content': 'synthetic private reasoning',
                        'tool_calls': [{'id': 'call', 'function': {'name': 'calculator', 'arguments': '{"expression":"1+1"}'}}]}}]})
        self.assertEqual(response.text, '')
        self.assertEqual(response.tool_calls[0].arguments, {'expression': '1+1'})
        self.assertTrue(response.raw_assistant_content[0]['reasoning_field_present'])
        self.assertEqual(response.raw_assistant_content[0]['content_type'], 'null')
        self.assertNotIn('synthetic private reasoning', json.dumps(response.raw_assistant_content))

    def test_hash_determinism_without_content_or_finish_reason_leakage(self):
        shape = response_shape('synthetic secret output', 'synthetic secret finish')
        self.assertEqual(shape, response_shape('synthetic secret output', 'synthetic secret finish'))
        self.assertEqual(len(shape['response_sha256']), 64)
        self.assertEqual(shape['finish_reason'], 'other')
        self.assertNotIn('synthetic secret', json.dumps(shape))