"""Killable HTTP transport with a wall deadline, independent of socket progress.

This subprocess handles trusted provider I/O only; it is not an execution sandbox.
Credentials travel in private process IPC, never command arguments or files.
"""
from __future__ import annotations

import math
import multiprocessing
import time
import urllib.error
import urllib.request

from sparkle.model import ModelError

MAX_RESPONSE_BYTES = 16 * 1024 * 1024


def _http_worker(connection, url, data, headers, method, timeout):
    try:
        request = urllib.request.Request(url, data=data, headers=headers, method=method)
        with urllib.request.urlopen(request, timeout=timeout) as response:
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
        self.deadline = time.monotonic() + self.timeout
        context = multiprocessing.get_context('spawn')
        self.reader, writer = context.Pipe(duplex=False)
        self.process = context.Process(target=self.worker, args=(
            writer, self.request.full_url, self.request.data,
            dict(self.request.header_items()), self.request.get_method(), self.timeout,
        ), daemon=True)
        try:
            self.process.start()
        except Exception:
            self.reader.close()
            raise ModelError('Provider transport could not start', category='connectivity_failure') from None
        finally:
            writer.close()
        return self

    def __iter__(self):
        while True:
            remaining = self.deadline - time.monotonic()
            if remaining <= 0 or not self.reader.poll(remaining):
                raise ModelError('Provider request deadline exceeded', category='timeout', retryable=True)
            try:
                kind, value = self.reader.recv()
            except EOFError:
                raise ModelError('Provider transport ended without completion', category='connectivity_failure', retryable=True) from None
            if kind == 'done':
                return
            if kind == 'http_error':
                raise urllib.error.HTTPError(self.request.full_url, value, 'Provider HTTP failure', {}, None)
            if kind == 'error':
                raise ModelError('Provider transport failed', category=value, retryable=value in {'timeout', 'connectivity_failure'})
            yield value

    def read(self):
        return b''.join(self)

    def __exit__(self, *_args):
        # Cleanup is bounded too; no abandoned I/O threads or retry processes.
        self.process.join(0.1)
        if self.process.is_alive():
            self.process.terminate()
            self.process.join(0.2)
        if self.process.is_alive():
            self.process.kill()
            self.process.join(0.2)
        self.process.close()
        self.reader.close()


def deadline_urlopen(request, timeout):
    return DeadlineResponse(request, timeout)
