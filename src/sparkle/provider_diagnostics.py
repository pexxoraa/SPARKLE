"""Opt-in, content-free timing events. Diagnostic output cannot block requests."""
import contextvars
import functools
import json
import math
import os
import queue
import threading
import time
import uuid

_CALL = contextvars.ContextVar('provider_diagnostic_call', default=None)
_QUEUE = queue.Queue(maxsize=256)
_LOCK = threading.Lock()
_THREAD = None
EVENTS = frozenset({'call_start','call_end','call_failure','attempt_start','attempt_failure',
                   'retry_wait','transport_start','worker_phase','transport_wait',
                   'deadline_expired','cleanup_start','cleanup_end','task_start','task_end'})
CATEGORIES = frozenset({'timeout','authentication_failure','provider_failure','connectivity_failure',
                        'malformed_response','model_unavailable','rate_limited','interrupted','other'})
NUMBERS = frozenset({'attempt','attempts','timeout_seconds','delay_seconds','deadline_monotonic',
                     'elapsed_seconds','remaining_seconds','worker_pid','worker_exitcode','task_number'})


def _drain():
    while True:
        line = _QUEUE.get()
        try:
            os.write(2, (line + '\n').encode('utf-8'))
        except Exception:
            pass
        finally:
            _QUEUE.task_done()


def _enqueue(line):
    global _THREAD
    with _LOCK:
        if _THREAD is None:
            _THREAD = threading.Thread(target=_drain, daemon=True, name='provider-diagnostics')
            _THREAD.start()
    try:
        _QUEUE.put_nowait(line)
    except queue.Full:
        pass  # Diagnostic loss is preferable to blocking provider cleanup.


def emit(event, **fields):
    if os.environ.get('SPARKLE_PROVIDER_DIAGNOSTICS') != '1' or event not in EVENTS:
        return
    record = {'event': event, 'monotonic': time.monotonic(), 'pid': os.getpid()}
    call_id = _CALL.get()
    if call_id is not None:
        record['call_id'] = call_id
    for key, value in fields.items():
        if key in NUMBERS and type(value) in (int, float) and math.isfinite(value):
            record[key] = value
        elif key in {'child_alive','outcome_correct'} and type(value) is bool:
            record[key] = value
        elif key == 'phase' and value in ('opening','body','http_complete'):
            record[key] = value
        elif key == 'category':
            record[key] = value if value in CATEGORIES else 'other'
    _enqueue(json.dumps(record, separators=(',', ':')))


def diagnosed_call(function):
    @functools.wraps(function)
    def wrapped(self, *args, **kwargs):
        token = _CALL.set(uuid.uuid4().hex)
        started = time.monotonic()
        emit('call_start', timeout_seconds=self._timeout, attempts=self._attempts)
        try:
            result = function(self, *args, **kwargs)
            emit('call_end', elapsed_seconds=time.monotonic()-started)
            return result
        except BaseException as exc:
            emit('call_failure', elapsed_seconds=time.monotonic()-started,
                 category='interrupted' if isinstance(exc, KeyboardInterrupt) else getattr(exc,'category','other'))
            raise
        finally:
            _CALL.reset(token)
    return wrapped
