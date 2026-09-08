"""Content-free diagnostics and termination across the complete retry lifecycle."""
import json
import multiprocessing
import os
import signal
import sqlite3
import tempfile
import time
import unittest
import urllib.request
from pathlib import Path
from unittest.mock import patch

from sparkle.contracts import Message, ModelRequest
from sparkle.model import ModelError
from sparkle.provider_diagnostics import emit
from sparkle.provider_http import DeadlineResponse
from sparkle.providers.nvidia import NVIDIAChatCompletionsAdapter
from sparkle.secrets import SecretResolver
from sparkle.storage import SQLiteStore
from tests.test_nvidia_adapter import config
from tests.test_provider_deadline import stalled_connection, stalled_read


def http_finished_without_done(writer, *_args):
    writer.send(('phase','http_complete'))
    writer.send(('data',b'{}'))
    time.sleep(30)


def completed_but_refuses_exit(writer, *_args):
    signal.signal(signal.SIGTERM,signal.SIG_IGN)
    writer.send(('done',None))
    time.sleep(30)


class ProviderLifecycleTests(unittest.TestCase):
    def test_no_initial_frame_has_absolute_deadline(self):
        before={p.pid for p in multiprocessing.active_children()}
        start=time.monotonic()
        with self.assertRaises(ModelError) as caught:
            with DeadlineResponse(urllib.request.Request('https://example.invalid'),.8,worker=stalled_connection) as response:
                response.read()
        self.assertEqual(caught.exception.category,'timeout')
        self.assertLess(time.monotonic()-start,2)
        self.assertIsNotNone(response.worker_exitcode)
        self.assertEqual(before,{p.pid for p in multiprocessing.active_children()})

    def test_http_complete_without_ipc_completion_times_out(self):
        with patch.dict(os.environ,{'SPARKLE_PROVIDER_DIAGNOSTICS':'1'}), patch('sparkle.provider_diagnostics._enqueue') as output:
            start=time.monotonic()
            with self.assertRaises(ModelError) as caught:
                with DeadlineResponse(urllib.request.Request('https://example.invalid'),3,worker=http_finished_without_done) as response:
                    response.read()
        events=[json.loads(c.args[0]) for c in output.call_args_list]
        self.assertTrue(any(e.get('phase')=='http_complete' for e in events))
        self.assertEqual(caught.exception.category,'timeout')
        self.assertLess(time.monotonic()-start,4)
        self.assertFalse(events[-1]['child_alive'])
        self.assertEqual(events[-1]['event'],'cleanup_end')

    @unittest.skipUnless(os.name=='posix','SIGTERM-ignore escalation is POSIX-specific')
    def test_done_but_child_ignores_termination_is_killed(self):
        before={p.pid for p in multiprocessing.active_children()}
        start=time.monotonic()
        with DeadlineResponse(urllib.request.Request('https://example.invalid'),3,worker=completed_but_refuses_exit) as response:
            self.assertEqual(response.read(),b'')
            cleanup_started=time.monotonic()
        self.assertEqual(response.worker_exitcode,-signal.SIGKILL)
        self.assertLess(time.monotonic()-cleanup_started,1.5)
        self.assertLess(time.monotonic()-start,4)
        self.assertEqual(before,{p.pid for p in multiprocessing.active_children()})

    def test_real_deadlines_repeat_only_configured_attempts(self):
        before={p.pid for p in multiprocessing.active_children()}
        def opener(request,timeout): return DeadlineResponse(request,timeout,worker=stalled_read)
        adapter=NVIDIAChatCompletionsAdapter(config(timeout_seconds=.8),SecretResolver({'NVIDIA_API_KEY':'synthetic-private-key'}),opener=opener,sleeper=lambda _:None)
        with patch.dict(os.environ,{'SPARKLE_PROVIDER_DIAGNOSTICS':'1'}), patch('sparkle.provider_diagnostics._enqueue') as output:
            start=time.monotonic()
            with self.assertRaises(ModelError) as caught:
                adapter.complete(ModelRequest(messages=[Message('user','synthetic-private-prompt')]))
        elapsed=time.monotonic()-start
        events=[json.loads(c.args[0]) for c in output.call_args_list]
        self.assertEqual(caught.exception.category,'timeout');self.assertEqual(caught.exception.attempts,2)
        self.assertGreaterEqual(elapsed,1.6);self.assertLess(elapsed,4)
        self.assertEqual([e['attempt'] for e in events if e['event']=='attempt_start'],[1,2])
        expired=[e for e in events if e['event']=='deadline_expired']
        self.assertEqual(len(expired),2)
        self.assertTrue(all(e['remaining_seconds']<=0 for e in expired))
        self.assertEqual(len([e for e in events if e['event']=='cleanup_end']),2)
        self.assertEqual(len({e['call_id'] for e in events}),1)
        self.assertNotIn('synthetic-private',json.dumps(events))
        self.assertEqual(before,{p.pid for p in multiprocessing.active_children()})

    def test_diagnostics_discard_content_and_are_opt_in(self):
        with patch.dict(os.environ,{'SPARKLE_PROVIDER_DIAGNOSTICS':'0'}), patch('sparkle.provider_diagnostics._enqueue') as output:
            emit('call_start',timeout_seconds=120)
            output.assert_not_called()
        with patch.dict(os.environ,{'SPARKLE_PROVIDER_DIAGNOSTICS':'1'}), patch('sparkle.provider_diagnostics._enqueue') as output:
            emit('call_failure',category='synthetic-private-key',prompt='synthetic-private-prompt',authorization='synthetic-private-key',timeout_seconds=120)
            result=json.loads(output.call_args.args[0])
        self.assertEqual(result['category'],'other')
        self.assertNotIn('synthetic-private',json.dumps(result))

    def test_full_diagnostics_queue_does_not_block_request(self):
        from sparkle import provider_diagnostics as diagnostics
        import queue
        full=queue.Queue(maxsize=1);full.put('occupied')
        with patch.object(diagnostics,'_QUEUE',full),patch.object(diagnostics,'_THREAD',object()):
            start=time.monotonic();diagnostics._enqueue('event')
        self.assertLess(time.monotonic()-start,.1)


class SQLiteLifecycleTests(unittest.TestCase):
    def test_successful_context_commits_and_closes(self):
        with tempfile.TemporaryDirectory() as directory:
            store=SQLiteStore(Path(directory)/'test.sqlite3')
            with store.connect() as connection:
                connection.execute('CREATE TABLE t(value)');connection.execute('INSERT INTO t VALUES(1)')
            with self.assertRaises(sqlite3.ProgrammingError):connection.execute('SELECT 1')
            with store.connect() as check:self.assertEqual(check.execute('SELECT value FROM t').fetchone()[0],1)

    def test_failed_context_rolls_back_and_closes(self):
        with tempfile.TemporaryDirectory() as directory:
            store=SQLiteStore(Path(directory)/'test.sqlite3')
            with store.connect() as connection:connection.execute('CREATE TABLE t(value)')
            with self.assertRaises(ValueError):
                with store.connect() as connection:
                    connection.execute('INSERT INTO t VALUES(1)');raise ValueError('rollback')
            with self.assertRaises(sqlite3.ProgrammingError):connection.execute('SELECT 1')
            with store.connect() as check:self.assertEqual(check.execute('SELECT COUNT(*) FROM t').fetchone()[0],0)
