"""Real orchestrator/state tests with explicitly scripted model batches."""
from dataclasses import replace
import itertools
import json
from unittest.mock import patch

from sparkle.config import AppConfig
from sparkle.contracts import ModelResponse, ToolCall
from sparkle.providers.mock import DeterministicAdapter
from tests.test_orchestrator_api import SystemCase, test_config


class Batches(DeterministicAdapter):
    def __init__(self, batches): self.batches, self.calls = iter(batches), 0
    def complete(self, request):
        self.calls += 1
        calls = next(self.batches)
        return ModelResponse('done' if not calls else '', self.model_id, self.provider,
                             'stop' if not calls else 'tool_use', tool_calls=calls)


def calculation(count):
    return [ToolCall(str(i), 'calculator', {'expression': '1+1'}) for i in range(count)]


class OrchestrationBoundTests(SystemCase):
    def inject(self, batches):
        adapter = Batches(batches)
        self.registry.inject(self.registry.active_id, adapter)
        return adapter

    def test_research_citation_integrity_tool_runs_through_orchestrator(self):
        self.system.knowledge.ingest_text('Fixture', 'Research fixture evidence.')
        row=self.system.tools.execute('knowledge_search',{'query':'fixture'})[0]
        citation={'source_id':row['source_id'],'chunk_id':row['chunk_id'],
                  'digest':row['citation_digest'],'quote':'fixture evidence'}
        self.inject([[ToolCall('citation','knowledge_verify',{'citations':[citation]})],[]])
        with patch.object(self.system.tools, 'execute', wraps=self.system.tools.execute) as execute:
            result=self.system.orchestrator.run('Verify this stored research citation',agent_name='research')
        self.assertEqual(len(result.tool_calls_executed),1)
        execute.assert_called_once()
        self.assertEqual(execute.call_args.args[0],'knowledge_verify')
        self.assertEqual(self.system.tools.execute('knowledge_verify',{'citations':[citation]})['claim_truth'],'INCONCLUSIVE')

    def test_model_memory_write_is_pending_and_trace_links_proposal(self):
        self.inject([[ToolCall('memory', 'memory_write', {'category':'goals','key':'fixture','value':'Practice daily'})], []])
        self.system.orchestrator.run('Remember a goal', agent_name='personal')
        self.assertEqual(self.system.memory.export(), [])
        proposals = self.system.memory_review.list()
        self.assertEqual(len(proposals), 1)
        trace = self.system.traces.recent()[0]
        self.assertEqual(trace['execution_metadata']['memory_proposal_ids'], [proposals[0]['id']])
        self.assertNotIn('Practice daily', json.dumps(trace['execution_metadata']))

    def test_exact_tool_call_replay_returns_cached_result_without_repeating_side_effect(self):
        call = ToolCall('same-call', 'memory_write', {'category':'goals','key':'fixture','value':'Practice daily'})
        self.inject([[call], [call], []])
        with patch.object(self.system.tools, 'execute', wraps=self.system.tools.execute) as execute:
            result = self.system.orchestrator.run('Remember a goal', agent_name='personal')
        self.assertEqual(execute.call_count, 1)
        self.assertEqual(result.tool_calls_executed, ['memory_write', 'memory_write'])
        self.assertEqual(len(self.system.memory_review.list()), 1)
        trace = self.system.traces.recent()[0]
        self.assertEqual(trace['execution_metadata']['tool_call_replays'], 1)
        self.assertEqual(trace['execution_metadata']['tool_calls_reserved'], 2)

    def test_tool_call_id_reuse_with_different_arguments_fails_closed(self):
        first = ToolCall('same-call', 'calculator', {'expression':'1+1'})
        second = ToolCall('same-call', 'calculator', {'expression':'2+2'})
        self.inject([[first], [second]])
        with patch.object(self.system.tools, 'execute', wraps=self.system.tools.execute) as execute:
            with self.assertRaises(RuntimeError) as caught:
                self.system.orchestrator.run('Calculate', agent_name='personal')
        self.assertEqual(caught.exception.orchestration_code, 'tool_call_replay_mismatch')
        self.assertEqual(execute.call_count, 1)

    def test_workflow_wall_clock_budget_is_shared_and_fails_closed(self):
        self.system.orchestrator.max_workflow_seconds = 1
        self.inject([[]])
        ticks = itertools.count()
        with patch('sparkle.orchestrator.time.monotonic', side_effect=lambda: next(ticks) * 0.6):
            with self.assertRaises(RuntimeError) as caught:
                self.system.orchestrator.run('Calculate', agent_name='personal')
        self.assertEqual(caught.exception.orchestration_code, 'workflow_deadline')
        trace = self.system.traces.recent()[0]
        self.assertEqual(trace['status'], 'failure')
        self.assertEqual(trace['execution_metadata']['workflow_seconds_limit'], 1)

    def test_oversized_batch_has_no_partial_memory_writes(self):
        self.inject([[ToolCall(str(i), 'memory_write', {'category': 'goals', 'key': str(i), 'value': 'fixture'}) for i in range(17)]])
        with self.assertRaises(RuntimeError) as caught:
            self.system.orchestrator.run('Store explicit goals', agent_name='personal')
        self.assertEqual(caught.exception.orchestration_code, 'tool_call_limit')
        self.assertEqual(self.system.memory.recent(), [])
        trace = self.system.traces.recent()[0]
        self.assertEqual(trace['status'], 'failure')
        self.assertEqual(trace['execution_metadata']['tool_calls_reserved'], 0)

    def test_exact_budget_succeeds_and_is_fresh_on_next_request(self):
        self.inject([calculation(16), [], calculation(16), []])
        for _ in range(2):
            result = self.system.orchestrator.run('Calculate', agent_name='personal')
            self.assertEqual(len(result.tool_calls_executed), 16)
            self.assertEqual(self.system.traces.recent()[0]['execution_metadata']['tool_calls_reserved'], 16)

    def test_cumulative_round_budget_does_not_execute_oversized_next_batch(self):
        self.inject([calculation(10), calculation(7)])
        with patch.object(self.system.tools, 'execute', wraps=self.system.tools.execute) as execute:
            with self.assertRaises(RuntimeError) as caught:
                self.system.orchestrator.run('Calculate', agent_name='personal')
        self.assertEqual(caught.exception.orchestration_code, 'tool_call_limit')
        self.assertEqual(execute.call_count, 10)

    def test_failed_tool_attempts_also_consume_budget(self):
        self.system.orchestrator.max_tool_calls = 1
        self.inject([[ToolCall('bad', 'calculator', {'expression': '__import__("os")'})], calculation(1)])
        with patch.object(self.system.tools, 'execute', wraps=self.system.tools.execute) as execute:
            with self.assertRaises(RuntimeError) as caught:
                self.system.orchestrator.run('Verify refusal', agent_name='personal')
        self.assertEqual(execute.call_count, 1)
        self.assertEqual(caught.exception.orchestration_code, 'tool_call_limit')

    def test_budget_shared_across_specialists_and_synthesis(self):
        # An over-budget tool batch is still a model response, so it increments
        # adapter.calls. Budget reservation happens after that response and before
        # any tool in the batch executes, preserving the no-partial-execution guard.
        # Case 1: personal returns 10 tools then completes; learning returns 7 tools,
        # which cannot fit in the 6 remaining slots => 3 model calls, 10 tool runs.
        # Case 2: personal and learning each return/execute 8 tools then complete;
        # synthesis returns one more tool with no budget left => 5 calls, 16 runs.
        for batches, expected_calls, expected_executes in (
            ([calculation(10), [], calculation(7)], 3, 10),
            ([calculation(8), [], calculation(8), [], calculation(1)], 5, 16),
        ):
            with self.subTest(expected_calls=expected_calls):
                adapter = self.inject(batches)
                with patch.object(self.system.tools, 'execute', wraps=self.system.tools.execute) as execute:
                    with self.assertRaises(RuntimeError) as caught:
                        self.system.orchestrator.run_multi('Calculate', agent_names=['personal', 'learning'])
                self.assertEqual(caught.exception.orchestration_code, 'tool_call_limit')
                self.assertEqual(adapter.calls, expected_calls)
                self.assertEqual(execute.call_count, expected_executes)

    def test_invalid_specialist_lists_fail_before_any_model_call(self):
        for names in ([], ['personal']*5, ['personal', 'personal'], 'personal', [None]):
            adapter = self.inject([])
            with self.assertRaises(ValueError):
                self.system.orchestrator.run_multi('Calculate', agent_names=names)
            self.assertEqual(adapter.calls, 0)

    def test_configuration_bounds_and_legacy_defaults(self):
        for name, invalid in (('max_tool_calls', (0, 129, True, 1.5)),
                              ('max_tool_rounds', (-1, 17, True)),
                              ('max_specialists', (0, 17, '4'))):
            for value in invalid:
                with self.assertRaises(ValueError): replace(test_config(), **{name: value})
        self.assertEqual(test_config().max_tool_calls, 16)
        from pathlib import Path
        path = Path(self.temp.name) / 'config.json'
        raw = json.loads(Path('application/config.json').read_text())
        raw['orchestrator'] = {'max_tool_rounds': 2}
        path.write_text(json.dumps(raw))
        loaded = AppConfig.load(path)
        self.assertEqual((loaded.max_tool_rounds, loaded.max_tool_calls, loaded.max_specialists), (2, 16, 4))
