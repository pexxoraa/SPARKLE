"""Synthetic HTTP fixtures exercise smoke classification; never live evidence."""
import json
import unittest
from types import SimpleNamespace
from unittest.mock import patch

from sparkle.cli import live_smoke
from sparkle.contracts import Message, ModelRequest
from sparkle.model import ModelError
from sparkle.providers.nvidia import NVIDIAChatCompletionsAdapter
from sparkle.secrets import SecretResolver
from tests.helpers import FakeHTTPResponse
from tests.test_nvidia_adapter import config


class LiveSmokeTests(unittest.TestCase):
    def run_smoke(self, *, content='', reason='length', response_changes=None,
                  decision_changes=None, configured=True, error=None, usage=True):
        envelope = {
            'id': 'synthetic-request', 'model': config()['model_id'],
            'choices': [{'finish_reason': reason, 'message': {
                'content': content, 'reasoning_content': 'synthetic private reasoning'}}],
        }
        if usage:
            envelope['usage'] = {'prompt_tokens': 20, 'completion_tokens': 64}
        envelope.update(response_changes or {})
        captured = {}

        def opener(request, timeout):
            captured.update(json.loads(request.data))
            if error:
                raise error
            return FakeHTTPResponse(envelope)

        adapter = NVIDIAChatCompletionsAdapter(
            config(), SecretResolver({'NVIDIA_API_KEY': 'synthetic-secret'} if configured else {}),
            opener=opener,
        )
        decision = dict(provider='nvidia', model=adapter.model_id,
                        test_harness=False, fallback=False)
        decision.update(decision_changes or {})
        system = SimpleNamespace(model_router=SimpleNamespace(
            select=lambda _: adapter,
            complete=lambda request, *a, **kw: (SimpleNamespace(**decision), adapter.complete(request)),
        ))
        with patch('sparkle.cli._print') as output:
            code = live_smoke(system)
        result = output.call_args.args[0]
        self.assertNotIn('synthetic-secret', json.dumps(result))
        self.assertNotIn('synthetic private reasoning', json.dumps(result))
        return code, result, captured

    def test_length_limited_reasoning_response_is_connectivity_not_compliance(self):
        code, result, payload = self.run_smoke()
        self.assertEqual(code, 0)
        self.assertTrue(result['live_provider_connectivity'])
        self.assertFalse(result['exact_response_match'])
        self.assertFalse(result['exact_output_compliance'])
        self.assertTrue(result['output_truncated'])
        self.assertEqual(result['finish_reason'], 'length')
        self.assertEqual(result['provider_request_id'], 'synthetic-request')
        self.assertEqual(result['usage']['output_tokens'], 64)
        self.assertGreaterEqual(result['duration_ms'], 0)
        self.assertFalse(result['secret_value_exposed'])
        self.assertEqual(payload['chat_template_kwargs'], {'enable_thinking': False})
        self.assertNotIn('reasoning_budget', payload)
        self.assertEqual(payload['max_tokens'], 64)

    def test_exact_completed_output_passes_both_checks(self):
        code, result, _ = self.run_smoke(content=' SPARKLE_LIVE_OK\n', reason='stop')
        self.assertEqual(code, 0)
        self.assertTrue(result['exact_output_compliance'])
        self.assertTrue(result['exact_response_match'])

    def test_extra_content_does_not_become_exact_compliance(self):
        code, result, _ = self.run_smoke(content='Here is SPARKLE_LIVE_OK', reason='stop')
        self.assertEqual(code, 0)
        self.assertFalse(result['exact_response_match'])

    def test_invalid_envelopes_fail_even_with_exact_text(self):
        for change in ({'id': None}, {'model': 'wrong-model'}, {'choices': []}):
            with self.subTest(change=change):
                code, result, _ = self.run_smoke(content='SPARKLE_LIVE_OK', reason='stop', response_changes=change)
                self.assertEqual(code, 1)
                self.assertFalse(result['ok'])
        code, result, _ = self.run_smoke(reason='unknown')
        self.assertEqual(code, 1)

    def test_test_harness_fallback_and_wrong_provider_rejected(self):
        for change in ({'test_harness': True}, {'fallback': True}, {'provider': 'wrong'}):
            with self.subTest(change=change):
                code, result, _ = self.run_smoke(decision_changes=change)
                self.assertEqual(code, 1)
                self.assertFalse(result['live_provider_connectivity'])

    def test_missing_credentials_do_not_call_transport(self):
        code, result, payload = self.run_smoke(configured=False)
        self.assertEqual(code, 2)
        self.assertEqual(result['stage'], 'credential_presence')
        self.assertEqual(payload, {})

    def test_provider_failure_is_nonzero_and_content_free(self):
        code, result, _ = self.run_smoke(error=ModelError('synthetic-secret', category='authentication_failure'))
        self.assertEqual(code, 1)
        self.assertEqual(result['error_type'], 'authentication_failure')
        self.assertFalse(result['live_provider_connectivity'])

    def test_missing_usage_is_unknown_not_fabricated(self):
        code, result, _ = self.run_smoke(content='SPARKLE_LIVE_OK', reason='stop', usage=False)
        self.assertEqual(code, 0)
        self.assertIsNone(result['usage'])
        self.assertFalse(result['usage_reported'])

    def test_reasoning_never_becomes_final_answer(self):
        response = NVIDIAChatCompletionsAdapter._parse_response({
            'choices': [{'finish_reason': 'length', 'message': {
                'content': None, 'reasoning_content': 'SPARKLE_LIVE_OK'}}],
        })
        self.assertEqual(response.text, '')

    def test_disabled_thinking_also_serialized_for_streaming(self):
        captured = {}
        def opener(request, timeout):
            captured.update(json.loads(request.data))
            return FakeHTTPResponse(lines=['data: [DONE]'])
        adapter = NVIDIAChatCompletionsAdapter(config(), SecretResolver({'NVIDIA_API_KEY': 'synthetic-secret'}), opener=opener)
        self.assertEqual(list(adapter.stream(ModelRequest(messages=[Message('user', 'hello')], thinking=False))), [])
        self.assertEqual(captured['chat_template_kwargs'], {'enable_thinking': False})
