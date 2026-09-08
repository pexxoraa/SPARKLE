"""Killable HTTP transport with a wall deadline, independent of socket progress.

This subprocess handles trusted provider I/O only; it is not an execution sandbox.
Credentials travel in private process IPC, never command arguments or files.
"""
from __future__ import annotations

import base64
import json
import select
import socket
import struct
import math
import multiprocessing
import time
import urllib.error
import urllib.request

from sparkle.model import ModelError
from sparkle.provider_diagnostics import emit

MAX_RESPONSE_BYTES = 16 * 1024 * 1024
MAX_FRAME_BYTES = 128 * 1024


class _MessageWriter:
    """Bounded JSON frames over private IPC; no blocking parent pickle receive."""
    def __init__(self, channel):
        self.channel = channel

    def send(self, message):
        kind, value = message
        if kind == 'data':
            value = base64.b64encode(value).decode('ascii')
        payload = json.dumps([kind, value], separators=(',', ':')).encode('utf-8')
        if len(payload) > MAX_FRAME_BYTES:
            raise ValueError('Provider IPC frame too large')
        self.channel.sendall(struct.pack('!I', len(payload)) + payload)

    def close(self):
        self.channel.close()



def _http_worker(connection, url, data, headers, method, timeout):
    try:
        connection.send(('phase', 'opening'))
        request = urllib.request.Request(url, data=data, headers=headers, method=method)
        with urllib.request.urlopen(request, timeout=timeout) as response:
            connection.send(('phase', 'body'))
            streaming = headers.get('Accept') == 'text/event-stream'
            total = 0
            while True:
                chunk = response.readline(65536) if streaming else response.read(65536)
                if not chunk:
                    break
                total += len(chunk)
                if total > MAX_RESPONSE_BYTES:
                    connection.send(('error', 'malformed_response'))
                    return
                connection.send(('data', chunk))
            connection.send(('phase', 'http_complete'))
            connection.send(('done', None))
    except urllib.error.HTTPError as exc:
        # Never read an error body: it can stall or echo a credential.
        connection.send(('http_error', exc.code))
        exc.close()
    except TimeoutError:
        connection.send(('error', 'timeout'))
    except urllib.error.URLError as exc:
        connection.send(('error', 'timeout' if isinstance(exc.reason, TimeoutError) else 'connectivity_failure'))
    except Exception:
        connection.send(('error', 'connectivity_failure'))
    finally:
        connection.close()


class DeadlineResponse:
    def __init__(self, request, timeout, *, worker=_http_worker):
        if not math.isfinite(timeout) or timeout <= 0:
            raise ValueError('HTTP timeout must be finite and positive')
        self.request, self.timeout, self.worker = request, timeout, worker
        self.process = None

    def __enter__(self):
        self.started = time.monotonic()
        self.deadline = self.started + self.timeout
        self.next_diagnostic = self.started + 5
        context = multiprocessing.get_context('spawn')
        self.reader, channel = socket.socketpair()
        self.reader.setblocking(False)
        writer = _MessageWriter(channel)
        self.buffer = bytearray()
        self.process = context.Process(target=self.worker, args=(
            writer, self.request.full_url, self.request.data,
            dict(self.request.header_items()), self.request.get_method(), self.timeout,
        ), daemon=True)
        try:
            self.process.start()
            self.worker_pid = self.process.pid
            emit('transport_start', worker_pid=self.worker_pid, timeout_seconds=self.timeout,
                 deadline_monotonic=self.deadline)
        except Exception:
            self.reader.close()
            raise ModelError('Provider transport could not start', category='connectivity_failure') from None
        finally:
            writer.close()
        return self

    def _receive(self):
        while True:
            now = time.monotonic()
            remaining = self.deadline - now
            if now >= self.next_diagnostic:
                emit('transport_wait', worker_pid=self.worker_pid, elapsed_seconds=now-self.started,
                     remaining_seconds=remaining, deadline_monotonic=self.deadline,
                     child_alive=self.process.is_alive())
                self.next_diagnostic = now + 5
            if remaining <= 0:
                emit('deadline_expired', worker_pid=self.worker_pid, elapsed_seconds=now-self.started,
                     remaining_seconds=remaining, deadline_monotonic=self.deadline)
                raise ModelError('Provider request deadline exceeded', category='timeout', retryable=True)
            if len(self.buffer) >= 4:
                size = struct.unpack('!I', self.buffer[:4])[0]
                if size > MAX_FRAME_BYTES:
                    raise ModelError('Provider IPC frame too large', category='malformed_response')
                if len(self.buffer) >= size + 4:
                    payload = bytes(self.buffer[4:size + 4])
                    del self.buffer[:size + 4]
                    try:
                        kind, value = json.loads(payload)
                        if kind == 'data':
                            value = base64.b64decode(value, validate=True)
                        elif kind not in {'done', 'http_error', 'error', 'phase'}:
                            raise ValueError('Unknown IPC message')
                    except (ValueError, TypeError):
                        raise ModelError('Invalid provider IPC frame', category='malformed_response') from None
                    return kind, value
            # Readiness is not a complete frame. Every partial receive returns to
            # the SAME deadline; no blocking recv() follows a readiness check.
            ready, _, _ = select.select([self.reader], [], [], min(remaining, 0.1))
            if not ready:
                continue
            try:
                chunk = self.reader.recv(65536)
            except BlockingIOError:
                continue
            if not chunk:
                raise ModelError('Provider transport ended without completion', category='connectivity_failure', retryable=True)
            self.buffer.extend(chunk)

    def __iter__(self):
        total = 0
        while True:
            kind, value = self._receive()
            if kind == 'phase':
                emit('worker_phase', phase=value, worker_pid=self.worker_pid,
                     elapsed_seconds=time.monotonic()-self.started)
                continue
            if kind == 'done':
                return
            if kind == 'http_error':
                raise urllib.error.HTTPError(self.request.full_url, value, 'Provider HTTP failure', {}, None)
            if kind == 'error':
                if value not in {'timeout', 'connectivity_failure', 'malformed_response'}:
                    value = 'malformed_response'
                raise ModelError('Provider transport failed', category=value, retryable=value in {'timeout', 'connectivity_failure'})
            total += len(value)
            if total > MAX_RESPONSE_BYTES:
                raise ModelError('Provider response too large', category='malformed_response')
            yield value

    def read(self):
        return b''.join(self)

    def __exit__(self, *_args):
        emit('cleanup_start', worker_pid=self.worker_pid, elapsed_seconds=time.monotonic()-self.started)
        # Cleanup is bounded too; no abandoned I/O threads or retry processes.
        self.process.join(0.1)
        if self.process.is_alive():
            self.process.terminate()
            self.process.join(0.2)
        if self.process.is_alive():
            self.process.kill()
            self.process.join(0.2)
        self.worker_exitcode = self.process.exitcode
        self.reader.close()
        if self.process.is_alive():
            raise ModelError('Provider transport cleanup failed', category='connectivity_failure')
        self.process.close()
        emit('cleanup_end', worker_pid=self.worker_pid, worker_exitcode=self.worker_exitcode,
             elapsed_seconds=time.monotonic()-self.started, child_alive=False)


def deadline_urlopen(request, timeout):
    return DeadlineResponse(request, timeout)
