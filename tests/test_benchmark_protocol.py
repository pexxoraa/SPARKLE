from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from benchmarks.agents import run_agents
from benchmarks.live import task_evidence
from benchmarks.protocol import response_shape
from sparkle.contracts import ModelResponse, ToolCall
from sparkle.providers.mock import DeterministicAdapter as TextAdapter
from sparkle.providers.nvidia import NVIDIAChatCompletionsAdapter
from sparkle.config import config


class BenchmarkProtocolTests(unittest.TestCase):
    def assert_protocol_failure(self, text, category, finish='stop'):
        class Adapter(TextAdapter):
            def complete(self, request):
                return ModelResponse(text, self.model_id, self.provider, finish)
        events=[]
        with tempfile.TemporaryDirectory() as directory:
            report=run_agents(Path(directory), adapter_factory=Adapter,
                              observer=lambda r,q:events.append(task_evidence(r,q)))
        self.assertEqual(report['validation_counts']['REJECTED'],12)
        self.assertTrue(all(e['diagnostics']['final_response']['format_category']==category for e in events))
        return events

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
            # Duplicate-call no-progress detection recovers before exhausting all
            # ordinary tool rounds, then fails closed because this synthetic adapter
            # ignores the final tools-disabled request and asks for a tool again.
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

    def test_markdown_json_is_not_automatically_extracted(self):
        self.assert_protocol_failure('```json\n{"answer":110}\n```', 'markdown_fence')

    def test_malformed_json(self):
        events=self.assert_protocol_failure('{"answer":110', 'malformed_or_extra_json')
        self.assertTrue(events[0]['diagnostics']['json_parsing_failed'])

    def test_native_tool_call_followed_by_structured_answer(self):
        class Adapter(TextAdapter):
            def __init__(self): self.calls=0
            def complete(self, request):
                self.calls += 1
                if self.calls % 2:
                    return ModelResponse('', self.model_id, self.provider, 'tool_use',
                        tool_calls=[ToolCall(f'call-{self.calls}', 'calculator', {'expression':'55+55'})])
                return ModelResponse('{"answer":110}', self.model_id, self.provider, 'stop')
        events=[]
        with tempfile.TemporaryDirectory() as directory:
            run_agents(Path(directory), adapter_factory=Adapter,
                       observer=lambda r,q:events.append(task_evidence(r,q)))
        self.assertTrue(any(e['diagnostics']['tool_call_count'] for e in events))

    def test_valid_structured_answer_keeps_independent_rejection(self):
        events=self.assert_protocol_failure('{"answer":110}', 'json_object')
        self.assertTrue(all(e['validation_status']=='REJECTED' for e in events))
