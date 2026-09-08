from __future__ import annotations

import ast
import hashlib
import json
import os
from collections import Counter
from pathlib import Path

from sparkle.config import AppConfig
from sparkle.contracts import ModelResponse, ToolCall
from sparkle.providers.mock import DeterministicAdapter
from sparkle.model import ModelError
from sparkle.provider_diagnostics import emit
from sparkle.registry import ModelRegistry
from sparkle.result_validation import validate_result
from sparkle.system import SparkleSystem
from sparkle.tooling import ToolRegistry, CalculatorTool, MemoryWriteTool, KnowledgeSearchTool, FileReadTool, WorkspaceVerifyTool
from benchmarks.retrieval import load_corpus

TASKS = Path(__file__).with_name('tasks.json')


class ScriptedOutcomeAdapter(DeterministicAdapter):
    """Explicit protocol test double. No task judgments or expected answers are read."""
    provider = 'scripted-outcome-test-harness'
    model_id = 'scripted-tools-v1'

    def __init__(self, script):
        self.script = script
        self.requests = []

    def complete(self, request):
        self.validate_request(request)
        self.requests.append(request)
        results = [m for m in request.messages if m.role == 'tool']
        if not results:
            return ModelResponse('',self.model_id,self.provider,'tool_use',tool_calls=[
                ToolCall('benchmark-call',self.script['tool'],self.script['arguments'])])
        value=json.loads(results[-1].text_content)
        answer={}
        if isinstance(value,(float,int)):
            answer['answer']=value
        elif isinstance(value,list):
            answer['citations']=[r['source_uri'].removeprefix('benchmark:')+':'+str(r['position']) for r in value]
        elif isinstance(value,dict) and 'content' in value:
            for node in ast.parse(value['content']).body:
                if isinstance(node,ast.Assign) and any(isinstance(t,ast.Name) and t.id=='LIMIT' for t in node.targets):
                    answer['answer']=ast.literal_eval(node.value)
        return ModelResponse(json.dumps(answer),self.model_id,self.provider,'end_turn')


class RecordingTools:
    def __init__(self, delegate):
        self.delegate, self.events = delegate, []

    def definitions(self, allowed): return self.delegate.definitions(allowed)

    def execute(self,name,arguments,*,allowed):
        event={'name':name,'arguments':dict(arguments),'failed':False}
        self.events.append(event)
        try:
            result=self.delegate.execute(name,arguments,allowed=allowed)
            event['result']=result
            return result
        except Exception:
            event['failed']=True
            raise


def run_agents(root, *, adapter_factory=None):
    """Inject a real adapter explicitly for separate live evaluation; default is scripted.

    Fixtures and task state are synthetic. Never run over a user's application data.
    """
    fixture=json.loads(TASKS.read_text())
    rows=[]
    previous=os.environ.get('SPARKLE_DATA_DIR')
    try:
        for task_number, task in enumerate(fixture['tasks'], 1):
            emit('task_start', task_number=task_number)
            state=root/task['task_id']; state.mkdir(parents=True)
            os.environ['SPARKLE_DATA_DIR']=str(state)
            adapter=adapter_factory() if adapter_factory else ScriptedOutcomeAdapter(task['script'])
            registry=ModelRegistry(); registry.inject(registry.active_id,adapter)
            system=SparkleSystem(config=AppConfig('127.0.0.1',0,4,5,5,False,False),model_registry=registry)
            _,identities=load_corpus(system.knowledge)
            workspace=state/'fixture-workspace'; workspace.mkdir()
            sample=workspace/'sample.py'; sample.write_text('LIMIT = 12\n')
            before=hashlib.sha256(sample.read_bytes()).hexdigest()
            system.workspaces.scaffold('benchmark_code',{'broken.py':'def incomplete(:\n'})
            (state/'outside.txt').write_text('HARMLESS OUTSIDE FIXTURE')
            tools=ToolRegistry()
            for tool in (CalculatorTool(),MemoryWriteTool(system.memory),KnowledgeSearchTool(system.knowledge),FileReadTool(workspace),WorkspaceVerifyTool(system.development)):
                tools.register(tool)
            recorder=RecordingTools(tools);system.orchestrator.tools=recorder
            execution_success=False;protocol_success=False;actual={};failure=None
            try:
                result=system.orchestrator.run(task['input'],agent_name=task['agent'])
                execution_success=True
                parsed=json.loads(result.text)
                protocol_success=isinstance(parsed,dict)
                actual=parsed if protocol_success else {}
            except ModelError as exc:
                failure="provider_" + exc.category
            except Exception as exc:
                failure=type(exc).__name__  # no potentially sensitive provider error text
            memory=system.memory.recent(limit=20)
            retrieved=[identities[r['chunk_id']] for e in recorder.events if e['name']=='knowledge_search'
                       for r in e.get('result',[]) if isinstance(r,dict) and r.get('chunk_id') in identities]
            verifications=system.development.list()
            observations={
                'verification_count':len(verifications),
                'verification_failed':verifications[0]['failed'] if verifications else None,
                'calls':[{'name':e['name'],'arguments':e['arguments']} for e in recorder.events],
                'memory_count':len(memory),'memory_value':memory[0]['value'] if memory else None,
                'tool_failed':any(e['failed'] for e in recorder.events), 'retrieved':retrieved,
                'file_unchanged':sample.exists() and hashlib.sha256(sample.read_bytes()).hexdigest()==before,
            }
            # Agent assertions cannot overwrite state/tool observations.
            for key in ('answer','citations'):
                if key in actual: observations[key]=actual[key]
            if 'citations' in actual:
                citations=actual['citations']
                observations['citations_grounded']=(isinstance(citations,list)
                    and all(isinstance(c,str) and c in retrieved for c in citations))
            validation=validate_result(task['expected_outcome'],observations)
            context=system.context.build(task['input']).render()
            context_ids=[identities[r['chunk_id']] for r in json.loads(context)['knowledge']] if context else []
            passed=execution_success and protocol_success and validation['validation_status']=='validated'
            rows.append({'task_id':task['task_id'],'agent':task['agent'],'input':task['input'],
                         'expected_outcome':task['expected_outcome'],'actual_outcome':actual,'validation_observations':observations,
                         'execution_success':execution_success,'protocol_success':protocol_success,
                         'outcome_correct':passed,'validation_result':validation,'score':validation['score'],
                         'tool_events':[{'name':e['name'],'arguments':e['arguments'],'failed':e['failed']} for e in recorder.events],
                         'retrieval_events':{'tool_chunks':retrieved,'context_chunks':context_ids},
                         'memory_events':{'count':len(memory),'value':observations['memory_value']},
                         'failure_reason':failure or (None if passed else validation['validation_status']),
                         'trace_completed':system.traces.recent()[0]['status']=='success'})
            emit('task_end', task_number=task_number, outcome_correct=passed)
    finally:
        if previous is None: os.environ.pop('SPARKLE_DATA_DIR',None)
        else: os.environ['SPARKLE_DATA_DIR']=previous
    counts=Counter(r['validation_result']['validation_status'] for r in rows)
    # Negative controls ensure execution/claims alone never imply validity.
    controls={
        'wrong_known_answer':validate_result([{'kind':'number','key':'answer','expected':42}],{'answer':41,'success':True}),
        'missing_evidence':validate_result([{'kind':'equals','key':'artifact_verified','expected':True}],{'success':True}),
        'subjective_quality':validate_result([{'kind':'semantic_quality','key':'answer','expected':True}],{'answer':'Excellent work'}),
    }
    return {'dataset_version':fixture['version'],'dataset_sha256':hashlib.sha256(TASKS.read_bytes()).hexdigest(),
            'evidence_mode':'explicit_adapter' if adapter_factory else 'SCRIPTED TEST HARNESS; NOT AGENT INTELLIGENCE',
            'live_provider_verified':False,'task_count':len(rows),'pass_rate':sum(r['outcome_correct'] for r in rows)/len(rows),
            'validation_pass_rate':counts['validated']/len(rows),'validation_counts':{k:counts[k] for k in ('validated','rejected','inconclusive')},
            'failure_categories':dict(Counter(r['failure_reason'] for r in rows if r['failure_reason'])),
            'per_agent':{a:{'tasks':len(rs:=[r for r in rows if r['agent']==a]),'passed':sum(r['outcome_correct'] for r in rs)} for a in sorted({r['agent'] for r in rows})},
            'tasks':rows,'negative_controls':controls}
