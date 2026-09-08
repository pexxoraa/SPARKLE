"""Loopback HTTP and partial IPC regressions; never contacts an external provider."""
import contextlib
import multiprocessing
import struct
import threading
import time
import unittest
import urllib.request
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

from sparkle.model import ModelError
from sparkle.provider_http import DeadlineResponse


def partial_frame(writer, *_args):
    # Announce a complete message, deliver only one byte, never finish it.
    writer.channel.sendall(struct.pack('!I', 100) + b'[')
    time.sleep(30)


def delayed_done(writer, *_args):
    payload=b'["done",null]'
    writer.channel.sendall(struct.pack('!I', len(payload)) + payload[:1])
    time.sleep(2)
    writer.channel.sendall(payload[1:])


@contextlib.contextmanager
def local_server(mode):
    stop=threading.Event()
    reached=threading.Event()
    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *_args): pass
        def do_GET(self):
            reached.set()
            try:
                if mode=='headers':
                    stop.wait(10)
                    return
                self.send_response(200)
                self.send_header('Content-Length', '2' if mode=='success' else '1000000')
                self.end_headers()
                if mode=='success':
                    self.wfile.write(b'OK')
                    return
                self.wfile.write(b'x'); self.wfile.flush()
                if mode=='trickle':
                    while not stop.wait(.03):
                        self.wfile.write(b'x'); self.wfile.flush()
                else:
                    stop.wait(10)
            except (BrokenPipeError, ConnectionResetError):
                pass
    server=ThreadingHTTPServer(('127.0.0.1',0),Handler)
    server.daemon_threads=True
    thread=threading.Thread(target=lambda:server.serve_forever(poll_interval=.05),daemon=True)
    thread.start()
    try:
        yield 'http://127.0.0.1:%d/' % server.server_port, reached
    finally:
        stop.set();server.shutdown();server.server_close();thread.join(1)


class ProviderHTTPStallTests(unittest.TestCase):
    def assert_terminated(self, response, before):
        self.assertIsNotNone(response.worker_exitcode)
        self.assertNotIn(response.worker_pid,{p.pid for p in multiprocessing.active_children()})
        self.assertEqual(before,{p.pid for p in multiprocessing.active_children()})
        self.assertEqual(response.reader.fileno(),-1)

    def test_real_transport_success(self):
        with local_server('success') as (url,reached):
            before={p.pid for p in multiprocessing.active_children()}
            with DeadlineResponse(urllib.request.Request(url),3) as response:
                self.assertEqual(response.read(),b'OK')
            self.assertTrue(reached.is_set())
            self.assert_terminated(response,before)

    def assert_stall(self,mode):
        with local_server(mode) as (url,reached):
            before={p.pid for p in multiprocessing.active_children()}
            started=time.monotonic()
            with self.assertRaises(ModelError) as failure:
                with DeadlineResponse(urllib.request.Request(url),1.5) as response:
                    response.read()
            self.assertEqual(failure.exception.category,'timeout')
            self.assertTrue(reached.is_set(), 'Fixture must reach the actual HTTP server')
            self.assertLess(time.monotonic()-started,3)
            self.assert_terminated(response,before)

    def test_slow_headers(self): self.assert_stall('headers')
    def test_slow_response_body(self): self.assert_stall('body')
    def test_trickling_body(self): self.assert_stall('trickle')
    def test_incomplete_body_never_completes(self): self.assert_stall('incomplete')

    def test_partial_ipc_frame_cannot_block_past_deadline(self):
        self.assert_partial(partial_frame)

    def test_late_completion_cannot_turn_timeout_into_success(self):
        self.assert_partial(delayed_done)

    def assert_partial(self,worker):
        before={p.pid for p in multiprocessing.active_children()}
        started=time.monotonic()
        with self.assertRaises(ModelError) as failure:
            with DeadlineResponse(urllib.request.Request('https://example.invalid'),.8,worker=worker) as response:
                response.read()
        self.assertEqual(failure.exception.category,'timeout')
        self.assertLess(time.monotonic()-started,1.8)
        self.assertGreater(len(response.buffer), 0, 'Partial frame must actually arrive')
        self.assertNotEqual(response.worker_exitcode, 0)
        self.assert_terminated(response,before)
