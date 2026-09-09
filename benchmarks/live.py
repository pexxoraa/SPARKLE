"""Opt-in configured-provider benchmark with durable, content-free evidence."""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import tempfile
import time
from pathlib import Path

from benchmarks.agents import TASKS, run_agents
from sparkle.config import model_config_path
from sparkle.model import ModelError
from sparkle.registry import ModelRegistry
from sparkle.storage import StorageConnectionError

RUNTIME_FIELDS = (
    'request_id', 'provider', 'model', 'capability', 'selection_reason', 'fallback',
    'started_at', 'finished_at', 'latency_ms', 'status', 'attempts', 'input_tokens',
    'output_tokens', 'provider_request_id', 'error_type', 'test_harness',
)
SAFE_TOOL_NAMES = frozenset({"calculator", "memory_write", "knowledge_search", "file_read", "workspace_verify"})
SAFE_ERRORS = frozenset({
    'configuration_failure', 'routing_failure', 'authentication_failure',
    'connectivity_failure', 'provider_failure', 'timeout', 'malformed_response',
    'model_unavailable', 'rate_limited',
})


def task_evidence(row, requests):
    """Do not export model text, tool arguments/results, memory values or errors."""
    failure = row['failure_reason']
    if failure and failure.startswith('provider_'):
        error = failure.removeprefix('provider_')
        error = error if error in SAFE_ERRORS else 'other'
        stage = 'pre_provider' if error in {'configuration_failure', 'routing_failure'} else 'provider_runtime'
    elif not row['execution_success']:
        stage, error = 'execution', 'execution_failure'
    elif not row['protocol_success']:
        stage, error = 'protocol', 'malformed_agent_output'
    elif not row['outcome_correct']:
        stage, error = 'validation', row['validation_result']['validation_status']
    else:
        stage, error = 'completed', None
    return {
        'event': 'task', 'task_id': row['task_id'], 'agent': row['agent'],
        'stage': stage, 'error_type': error,
        'execution_success': row['execution_success'], 'protocol_success': row['protocol_success'],
        'outcome_correct': row['outcome_correct'],
        'validation_status': row['validation_result']['validation_status'],
        'score': row['score'], 'trace_completed': row['trace_completed'],
        'tool_events': [{'name': e['name'] if e['name'] in SAFE_TOOL_NAMES else 'other', 'failed': e['failed']} for e in row['tool_events']],
        'retrieval_events': row['retrieval_events'], 'memory_count': row['memory_events']['count'],
        # Runtime start proves an adapter call was attempted, NOT HTTP delivery.
        'model_requests': [{k: r[k] for k in RUNTIME_FIELDS} for r in reversed(requests)],
    }


def run_live(output: Path):
    """Same tasks/scoring. Returns 0 pass, 1 outcome failure, 2 blocked/incomplete."""
    if os.environ.get('SPARKLE_BENCHMARK_LIVE') != '1':
        raise ValueError('Live evaluation requires SPARKLE_BENCHMARK_LIVE=1')
    config_path = model_config_path()
    started = time.monotonic()
    completed = 0
    # Exclusive creation: do not replace prior evidence or follow an output symlink.
    fd = os.open(output, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(fd, 'w', encoding='utf-8') as handle:
        secret_values = []
        def redact(value):
            if isinstance(value, str):
                for secret in secret_values:
                    value = value.replace(secret, '[REDACTED]')
                return value
            if isinstance(value, dict):
                return {k: redact(v) for k, v in value.items()}
            if isinstance(value, list):
                return [redact(v) for v in value]
            return value
        def write(event):
            handle.write(json.dumps(redact(event), sort_keys=True) + '\n')
            handle.flush()
            os.fsync(handle.fileno())

        write({'event': 'start', 'schema': 'SPARKLE-LIVE-AGENTS/1',
               'dataset_sha256': hashlib.sha256(TASKS.read_bytes()).hexdigest(),
               'evidence_mode': 'configured_provider_attempt',
               'agent_competence_verified': False})
        previous = os.environ.get('SPARKLE_DATA_DIR')
        try:
            with tempfile.TemporaryDirectory() as directory:
                root = Path(directory)
                os.environ['SPARKLE_DATA_DIR'] = str(root / 'preflight')
                registry = ModelRegistry(config_path)
                active = registry.record(registry.active_id)
                for record in registry._records.values():
                    for reference, available in registry.secrets.status(record.config.get('secret_refs', [])).items():
                        if available:
                            secret_values.append(registry.secrets.first([reference]))
                if active.config.get('secret_refs') and not any(registry.secrets.status(active.config['secret_refs']).values()):
                    write({'event': 'blocked', 'stage': 'pre_provider', 'error_type': 'configuration_failure'})
                    return 2
                def factory():
                    # Use the same explicit config on every task, including installed runs.
                    # No injected adapter: normal policy, health and fallback are preserved.
                    return ModelRegistry(config_path)
                def observe(row, requests):
                    nonlocal completed
                    write(task_evidence(row, requests))
                    completed += 1
                report = run_agents(root / 'tasks', registry_factory=factory, observer=observe)
            write({'event': 'summary', 'task_count': report['task_count'],
                   'pass_rate': report['pass_rate'], 'validation_pass_rate': report['validation_pass_rate'],
                   'validation_counts': report['validation_counts'], 'per_agent': report['per_agent'],
                   'elapsed_seconds': time.monotonic() - started, 'cleanup_succeeded': True,
                   'agent_competence_verified': False})
            return 0 if report['pass_rate'] == 1.0 else 1
        except (Exception, KeyboardInterrupt) as exc:
            category = 'interrupted' if isinstance(exc, KeyboardInterrupt) else 'setup_or_cleanup_failure'
            if isinstance(exc, StorageConnectionError):
                category = 'storage_unavailable'
            elif isinstance(exc, ModelError):
                category = exc.category if exc.category in SAFE_ERRORS else 'other'
            write({'event': 'incomplete', 'error_type': category,
                   'completed_tasks': completed, 'elapsed_seconds': time.monotonic() - started})
            return 2
        finally:
            if previous is None:
                os.environ.pop('SPARKLE_DATA_DIR', None)
            else:
                os.environ['SPARKLE_DATA_DIR'] = previous


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    raise SystemExit(run_live(args.output))


if __name__ == '__main__':
    main()
