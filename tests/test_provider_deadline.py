from contextlib import closing
"""Credential-free transport fault injection; no real HTTP calls."""
import json
import multiprocessing
import tempfile
import time
import unittest
import urllib.error
import urllib.request
from pathlib import Path
from unittest.mock import patch

from benchmarks.agents import run_agents
from sparkle.contracts import Message, ModelRequest
from sparkle.model import ModelError
from sparkle.provider_http import DeadlineResponse, _http_worker
from sparkle.providers.nvidia import NVIDIAChatCompletionsAdapter
from sparkle.secrets import SecretResolver
from tests.helpers import FakeHTTPResponse
from tests.test_nvidia_adapter import config


def stalled_connection(pipe, *_args):
    time.sleep(30)


def stalled_read(pipe, *_args):
    pipe.send(('data', b'partial'))
    time.sleep(30)


def trickling_read(pipe, *_args):
    while True:
        pipe.send(('data', b'x'))
        time.sleep(.02)


def completed_response(pipe, *_args):
    pipe.send(('data', b'{"ok":true}'))
    pipe.send(('done', None))
    pipe.close()


class TimeoutAdapter(NVIDIAChatCompletionsAdapter):
    def __init__(self):
        super().__init__(config(), SecretResolver({'NVIDIA_API_KEY': 'synthetic-secret'}),
                         opener=self.fail, sleeper=lambda _: None)

    @staticmethod
    def fail(*_args, **_kwargs):
        raise TimeoutError('synthetic-secret')


class ProviderDeadlineTests(unittest.TestCase):
    def test_successful_response_is_delivered_and_cleaned_up(self):
        with DeadlineResponse(urllib.request.Request('https://example.invalid'), 3, worker=completed_response) as response:
            self.assertEqual(response.read(), b'{"ok":true}')

    def test_connection_wall_deadline_and_cleanup(self):
        self.assert_deadline(stalled_connection)

    def test_read_wall_deadline_and_cleanup(self):
        self.assert_deadline(stalled_read)

    def test_trickle_does_not_reset_wall_deadline(self):
        self.assert_deadline(trickling_read)

    def assert_deadline(self, worker):
        before={p.pid for p in multiprocessing.active_children()}
        started=time.monotonic()
        with self.assertRaises(ModelError) as raised:
            with DeadlineResponse(urllib.request.Request('https://example.invalid'), .8, worker=worker) as response:
                response.read()
        self.assertEqual(raised.exception.category, 'timeout')
        self.assertLess(time.monotonic()-started, 4)
        self.assertEqual(before, {p.pid for p in multiprocessing.active_children()})

    def test_socket_timeout_applies_to_open_and_read_and_is_safe(self):
        class Pipe:
            def __init__(self): self.messages=[]
            def send(self, value): self.messages.append(value)
            def close(self): pass
        class ReadTimeout(FakeHTTPResponse):
            def read(self, *_args): raise TimeoutError('synthetic-secret')
        for failure in ('connect', 'read'):
            pipe=Pipe()
            with patch('sparkle.provider_http.urllib.request.urlopen') as opener:
                if failure=='connect': opener.side_effect=TimeoutError('synthetic-secret')
                else: opener.return_value=ReadTimeout()
                _http_worker(pipe, 'https://example.invalid', b'{}', {}, 'POST', 1.25)
                self.assertEqual(opener.call_args.kwargs['timeout'], 1.25)
            self.assertEqual(pipe.messages[-1], ('error', 'timeout'))
            self.assertEqual(pipe.messages[0], ('phase', 'opening'))

    def test_timeout_retry_limit_and_backoff_preserved(self):
        calls=[]; delays=[]
        def opener(*args, **kwargs):
            calls.append(kwargs['timeout'])
            raise TimeoutError('synthetic-secret')
        adapter=NVIDIAChatCompletionsAdapter(config(),SecretResolver({'NVIDIA_API_KEY':'synthetic-secret'}),opener=opener,sleeper=delays.append)
        with self.assertRaises(ModelError) as raised:
            adapter.complete(ModelRequest(messages=[Message('user','test')]))
        self.assertEqual(calls,[3,3])
        self.assertEqual(len(delays),1)
        self.assertEqual(raised.exception.attempts,2)
        self.assertEqual(raised.exception.category,'timeout')
        self.assertNotIn('synthetic-secret',str(raised.exception))

    def test_wrapped_timeout_and_stream_timeout_normalized(self):
        def opener(*args, **kwargs):
            raise urllib.error.URLError(TimeoutError('synthetic-secret'))
        adapter=NVIDIAChatCompletionsAdapter(config(),SecretResolver({'NVIDIA_API_KEY':'synthetic-secret'}),opener=opener,sleeper=lambda _:None)
        for method in ('complete','stream'):
            with self.assertRaises(ModelError) as raised:
                result=getattr(adapter,method)(ModelRequest(messages=[Message('user','test')]))
                if method=='stream': list(result)
            self.assertEqual(raised.exception.category,'timeout')
            self.assertNotIn('synthetic-secret',str(raised.exception))

    def test_http_error_body_is_never_read(self):
        class HostileError(urllib.error.HTTPError):
            def read(self): raise AssertionError('error body must not be read')
        for status, category in ((401,'authentication_failure'),(500,'provider_failure')):
            def opener(*args,**kwargs): raise HostileError('https://example.invalid',status,'synthetic-secret',{},None)
            adapter=NVIDIAChatCompletionsAdapter(config(),SecretResolver({'NVIDIA_API_KEY':'synthetic-secret'}),opener=opener,sleeper=lambda _:None)
            with self.assertRaises(ModelError) as raised:
                adapter.complete(ModelRequest(messages=[Message('user','test')]))
            self.assertEqual(raised.exception.category,category)
            self.assertNotIn('synthetic-secret',str(raised.exception))

    def test_benchmark_continues_and_runtime_records_provider_timeout(self):
        import sqlite3
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory)
            report=run_agents(root,adapter_factory=TimeoutAdapter)
            self.assertEqual(report['task_count'],12)
            self.assertEqual(report['failure_categories'],{'provider_timeout':12})
            self.assertEqual(report['pass_rate'],0)
            self.assertTrue(all(not r['execution_success'] for r in report['tasks']))
            self.assertNotIn('synthetic-secret',json.dumps(report))
            databases=list(root.rglob('model_runtime.sqlite3'))
            self.assertEqual(len(databases),12)
            for database in databases:
                with closing(sqlite3.connect(database)) as db, db:
                    row=db.execute('SELECT status,error_type,attempts FROM model_requests').fetchone()
                    self.assertEqual(row,('failure','timeout',2))
