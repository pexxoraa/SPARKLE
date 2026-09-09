# Model management

SPARKLE remains provider-neutral:

`core → model manager → registry → adapter → provider → model`

The default record is NVIDIA Nemotron 3.5 Lightning. MiniMax remains a built-in
legacy adapter and disabled registry record; it was not deleted.

## Current default

| Field | Value |
|---|---|
| Provider | NVIDIA |
| Registry ID | `nvidia-nemotron-3.5-lightning` |
| Provider model ID | `nvidia/nemotron-3.5-lightning-30b-a3b` |
| Endpoint | `https://integrate.api.nvidia.com/v1/chat/completions` |
| Authentication | `Authorization: Bearer`, resolved from `NVIDIA_API_KEY` or `SPARKLE_LLM_API_KEY` |
| API format | NVIDIA NIM Chat Completions |
| Input/output | Text → text |
| Context | Up to 1M tokens |
| Configured output bound | 16,384 tokens |
| Streaming | SSE, normalized to text deltas |
| Tools | OpenAI-style `tools` and `tool_calls`, normalized to SPARKLE contracts |
| Live status | **NOT VERIFIED** — no NVIDIA credential was available during this milestone |

The exact model was selected from NVIDIA's current catalog on 2026-09-02. The
older `nvidia/nemotron-3-nano-30b-a3b` free endpoint was not selected because
NVIDIA marks it deprecated. Official references:

- https://build.nvidia.com/nvidia/nemotron-3.5-lightning-30b-a3b
- https://docs.api.nvidia.com/nim/reference/nvidia-nemotron-3-5-lightning-30b-a3b
- https://docs.nvidia.com/nim/large-language-models/latest/api-reference.html

## Adapter boundary

`NVIDIAChatCompletionsAdapter` maps provider-neutral messages, system content,
tools, tool results, response text, tool calls, finish reasons, request IDs,
usage, retryable failures, and SSE chunks. It uses the standard library and
does not introduce an OpenAI SDK dependency. Credentials are resolved only at
request time and are never written to the registry, request evidence, traces,
dashboard, or artifacts.

MiniMax remains behind `MiniMaxMessagesAdapter`. Core orchestration, agents,
memory, knowledge, tools, API, CLI, and dashboard import neither provider.
Changing the active registry record requires no core-code change.

## Health

Provider-neutral states are:

- `HEALTHY`: a real provider request succeeded.
- `DEGRADED`: configured but not live verified, or a transient timeout,
  connectivity, rate-limit, or provider failure was observed.
- `UNAVAILABLE`: disabled, missing configuration, authentication failure, or
  model-unavailable evidence.

Configuration presence alone never produces `HEALTHY`. Injected deterministic
adapters are explicitly tagged `test_harness`; their successes cannot set live
Nemotron verification.

## Request policy

The router evaluates task capability, declared model roles, complete input
modalities, tool requirement, streaming requirement, health, latency class,
timeout ceiling, enabled state, and explicit fallback permission. Fallback is
allowed only to a compatible enabled record whose configuration permits it.
The decision and reason are content-free evidence; provider-specific routing is
not embedded in the orchestrator.

## Usage evidence

Each request records a generated request ID, registry/provider/model identity,
capability, health at selection, selection reason, fallback flag, start/end
timestamps, latency, status, attempts, safe error class, bounded provider
request ID, and provider-reported token counts. Prompts, responses, tools,
credentials, and provider reasoning are excluded. If usage is absent, token
fields remain `null`; SPARKLE never invents counts.

Inspect with:

```bash
sparkle status
sparkle model-requests --limit 20
sparkle smoke-test --live
```

The live smoke test requires a real NVIDIA key. Without one it fails before
network access and does not change live verification status.

### Connectivity smoke versus exact output

`smoke-test --live` now returns exit 0 / `ok=true` for a normalized provider
response bound to the selected provider/model, with a nonempty provider request
ID and a recognized completion reason. Injected test harnesses, fallback,
unexpected tool calls, missing identity and malformed/provider failures do not
satisfy this check. This command uses the configured adapter transport; synthetic
unit fixtures are not live evidence. TLS/authentication remain the adapter's
responsibility. A request ID is correlation metadata, not a cryptographic proof.

`live_provider_connectivity` is separate from `exact_response_match` and
`exact_output_compliance`. The latter requires the exact marker and a normal
completion; `length` / `max_tokens` sets `output_truncated=true` even when
connectivity succeeds. This does not establish answer quality. The 64-token cap
and exact instruction remain unchanged. Request ID, finish reason, measured
latency and available usage are retained; absent usage is null. Response text,
reasoning and raw provider error bodies are not printed by the smoke command.

The NVIDIA adapter previously omitted `chat_template_kwargs` when
`thinking=False`, leaving the server default in effect. It now explicitly sends
`enable_thinking=false` (also for streaming), and only sends a reasoning budget
when thinking is enabled. NVIDIA documents default-on reasoning for Lightning
and recommends disabling it for constrained output:
https://docs.nvidia.com/nim/large-language-models/2.0.10/get-started/advanced/get-started-nemotron-3.5-lightning.html

Host-reported evidence: authenticated response, request ID, usage, measured
latency and HEALTHY/verified_success; exact output failed with finish_reason=length
and 64 output tokens. This is not an authentication failure. The missing explicit
thinking control is confirmed in source; reasoning exhausting that host request's
budget is consistent with the evidence, not independently proven without its
response. Normalization deliberately keeps reasoning separate from final text.
No response text or secret is needed to rerun the content-free smoke check.

The development executor has no NVIDIA credential, so the corrected live request
still requires host revalidation. Host-reported connectivity remains evidence;
exact-output compliance is not yet verified. Keep NVIDIA_API_KEY environment-based.
Level 3 remains BLOCKED/PARKED and deployment FROZEN.

Correction verification (2026-09-08): baseline 321 tests ran, 320 passed and one
optional live test skipped. Final suite: 331 ran, 330 passed and one optional live
test skipped. Focused smoke/NVIDIA/runtime: 21/21; documentation: 4/4.
Ten new synthetic smoke tests cover truncation, exact and extra output, invalid
identity/envelopes, harness/fallback rejection, credentials/errors, missing usage,
reasoning separation and streaming thinking controls. Fresh offline wheel build
and installation passed. Local live command exited 2 at credential presence;
no corrected authenticated live request is claimed by these tests.

### NVIDIA request deadlines and interrupted benchmarks

The router's `max_timeout_seconds` is a configuration-selection constraint, not
an orchestrator wall-clock timer. `urlopen(timeout=...)` bounds blocking socket
operations, not elapsed time across an entire response. The former whole-body
read could therefore outlast that setting when data trickled in; DNS and other
transport stalls were not governed by a caller-owned deadline. Raw TimeoutError
was also not consistently normalized into runtime ModelError evidence. A traceback
interrupted in SSL recv establishes where the caller waited, not its elapsed time
or an agent-quality failure.

The default NVIDIA transport now performs trusted HTTPS I/O in a short-lived
spawned process. The caller owns a monotonic per-attempt deadline covering startup,
DNS, connect/TLS, headers and body/stream reads. Every socket operation also receives
the configured timeout. Progress does not reset the deadline. On timeout or caller
interruption the transport process is joined, terminated, and if necessary killed
with bounded cleanup waits (up to 0.5 seconds plus OS scheduling). No abandoned
provider thread remains. A 16 MiB response limit bounds buffering. TLS validation
is unchanged. This is provider I/O containment, NOT a Level 3 execution sandbox.
Python embedding entrypoints must support multiprocessing spawn and use the usual
`if __name__ == '__main__'` guard. The documented CLI and unittest entrypoints do.

Non-streaming retries retain the configured attempt count and exponential backoff
with jitter. With defaults, three attempts each have a 120-second deadline: a
single model call may take about 360 seconds plus bounded backoff/cleanup. That is
not a 120-second task budget; an agent can make several bounded model calls.
Streaming remains one attempt; it is never silently replayed after partial output.
The injected opener interface remains for deterministic tests only.

Direct/wrapped timeouts normalize to retryable ModelError(category='timeout').
Runtime records failure, attempts, latency and timeout; benchmark failure_reason
is `provider_timeout`, separate from authentication_failure, provider_failure,
malformed_response, JSON/protocol failure and independent validation rejection or
inconclusive results. No task or scoring criterion changed. No error body is read
for HTTP failure classification; bodies can stall or echo credentials. Network
exception details are not emitted. Secrets remain environment-resolved and are
not passed as command-line arguments or written to files.

Tests use spawned harmless stall/trickle workers and in-process HTTP fixtures;
ordinary CI makes no external request. These tests demonstrate deadline enforcement
and structured failure handling, not live NVIDIA performance or agent competence.
The earlier successful authenticated smoke remains valid host evidence. The
interrupted live benchmark remains incomplete, and no new live run was attempted
while implementing this fix. Level 3 remains BLOCKED/PARKED; deployment FROZEN.

Python timeout semantics:
https://docs.python.org/3.12/library/urllib.request.html
Process lifecycle semantics:
https://docs.python.org/3.12/library/multiprocessing.html

Deadline correction verification (2026-09-08): baseline 331 tests ran (330 passed,
one optional live test skipped); final 340 ran (339 passed, one optional live test
skipped). Focused deadline/NVIDIA/smoke/runtime/benchmark suite: 43/43. Documentation:
4/4. Nine new deterministic tests include spawned connection/read/trickle stalls,
cleanup, successful transport, socket-timeout propagation, bounded retries, stream
normalization, HTTP-error safety and all-12-task timeout/runtime evidence. Wheel
build and fresh offline installation passed. Baseline tasks, scores and retrieval
metrics are identical; only the agents.py implementation fingerprint changed in
the reproducible report. No authenticated live benchmark was rerun.

### Partial-IPC deadline correction

The HTTP child owns the HTTPS socket; the caller owns the monotonic deadline.
A second inspection found a gap in the initial process transport: Pipe.poll()
only establishes that bytes are readable, not that a whole framed message has
arrived. The following blocking Connection.recv() could wait outside the deadline.
A harmless reproducer on the previous implementation sent a partial completion
frame, delayed the remainder, and returned SUCCESS after 1.603 seconds despite a
0.8-second deadline. Previous doubles only sent complete IPC frames and missed
this case. Python documents poll as checking for any available data:
https://docs.python.org/3/library/multiprocessing.html#connection-objects

The observed host traceback in poll(remaining) does not establish that this
specific defect caused that interruption. No elapsed duration or attempt number
was supplied. A finite wait inside poll is expected; three attempts and multiple
agent calls can appear idle for minutes. We do not claim to have reproduced the
host's live response or rerun its benchmark.

The parent now reads a private socketpair nonblocking, assembling bounded JSON
frames incrementally (no pickle receive). It waits at most 100 ms per readiness
check and recomputes the SAME absolute deadline after every partial read. Socket
or IPC trickling never extends it. Partial frames, including late completion
frames, cannot bypass expiry. The child may still wait in urllib while reading
headers/body; the independent parent deadline terminates it. Parent-side response
size and frame bounds also fail closed.

Configured timeout remains per attempt from before process startup through the
complete body/stream. Cleanup retains at most 0.5 seconds of explicit join waits,
with terminate then kill escalation; actual scheduling is OS-dependent. Child
exit code and closed resources are asserted in tests; failed cleanup is a
structured failure, never success. Retry/backoff semantics are unchanged. Default
three 120-second attempts can still consume approximately 360 seconds plus
backoff/cleanup PER MODEL CALL, not for the whole 12-task benchmark.

New regression tests exercise the real transport against a loopback HTTP server:
normal success, slow headers, slow body, periodic bytes and incomplete body.
Additional IPC cases stall inside a partial frame and send a late completion.
They assert deadline failure, process exit, no remaining active child and closed
IPC descriptors. Existing tests retain safe timeout normalization, bounded retry
counts and provider_timeout runtime/benchmark classification. Loopback tests do
not contact NVIDIA and do not constitute live model or agent-quality evidence.
Tasks, scores, validators, baseline reports, Level 3 and deployment gates remain
unchanged. A credentialed host rerun remains pending after publication and CI.

Partial-IPC verification (2026-09-08): baseline 340 tests ran (339 passed, one live
skip); final 347 ran (346 passed, one live skip). Focused transport/provider/runtime/
benchmark/documentation suite: 54/54. Seven new loopback/IPC tests passed. Wheel
build and fresh offline installation passed; current-tree secret/path/symlink/size
audit passed over 177 files. No live provider call or benchmark outcome is claimed.

### Diagnose the live benchmark lifecycle without guessing from a stack frame

The latest host interruption in select(..., min(remaining, 0.1)) does not prove
an expired deadline. The actual host cause remains UNRESOLVED without timing and
attempt evidence. No further parent-deadline failure was reproduced. In particular:

- `max_timeout_seconds=120` is an argument to ModelRouter.complete, NOT a
  ModelRequest field. Registry selection accepts models whose configured timeout
  is at most 120. It neither creates a task deadline nor overwrites adapter state.
- The configured NVIDIA adapter uses timeout_seconds=120 and three attempts.
  Each attempt enters a NEW DeadlineResponse; its parent sets
  deadline_monotonic = monotonic_start + 120 before process startup.
- The child receives the relative socket timeout (120), not that absolute value.
  It owns urlopen/TLS/headers/body reads. Only the parent owns and enforces the
  absolute wall deadline. Child cooperation is not required for expiry.
- The parent recomputes remaining from that same absolute deadline. An unreadable
  channel (including a child blocked before headers) produces repeated waits of
  at most 0.1 seconds. Nonpositive remaining raises category=timeout, and context
  exit terminates/kills/reaps the child with bounded waits.
- Child progress frames now identify opening, body and http_complete. Only done
  completes the response. HTTP completion without done still hits the deadline;
  an EOF without done is a connectivity failure, never successful completion.
- Cleanup joins remain bounded (0.1 + 0.2 + 0.2 seconds, plus OS scheduling).
  A child ignoring SIGTERM is killed. Tests assert exit codes and no active orphan.
- Retry count/backoff have NOT changed. Three attempts can consume roughly six
  minutes per model call. The benchmark's max_tool_rounds=4 permits up to five
  calls per task. A task can approach 30 minutes when earlier calls finish near
  their deadlines; twelve tasks are not governed by one 120-second global timer.

The smoke uses 64 output tokens and thinking=False. Agent calls use up to 4096
output tokens with thinking=True and may request tools. Smoke connectivity does
not establish agent latency, quality, or task completion. Retry amplification and
repeated model rounds are possible explanations, not verified diagnoses of the
host's interrupted run. No interruption has been converted into provider_timeout.

#### Content-free timing diagnostics (optional)

After installing this verified checkpoint, the host may perform ONE controlled
live rerun, using its existing environment-injected credential:

```sh
SPARKLE_PROVIDER_DIAGNOSTICS=1 SPARKLE_BENCHMARK_LIVE=1 PYTHONPATH=src \
  python -m unittest tests.test_benchmarks_live -v 2>provider-timing.log
```

Ordinary CI leaves both flags unset. No live benchmark ran during this change.
Diagnostic events contain only locally generated call IDs, task ordinal, attempt
numbers, monotonic timestamps/deadlines, durations, remaining seconds, worker PID,
exit code, alive boolean, fixed phase names and allowlisted error categories.
No prompt, response, tool arguments, model content, URL, key, authorization header
or provider error message is included. The unittest runner also writes its usual
summary/traceback to this stderr file; it is not a pure JSON document.

Use task_start/task_end to locate the task, call_start/call_end to count model
rounds, attempt_start/attempt_failure/retry_wait to identify retry amplification,
worker_phase to locate HTTP progress, transport_wait (every five seconds) to
observe the SAME deadline, and deadline_expired/cleanup_end to verify termination.
A manual interrupt is recorded as interrupted, not timeout. Every model call has
a new locally generated correlation ID. Numeric monotonic timestamps are meaningful
only within that run/machine.

Diagnostics are opt-in and best-effort. A bounded queue and daemon writer keep a
blocked stderr consumer from blocking the provider deadline/cleanup. Events can be
dropped if the queue fills or the interpreter exits; missing diagnostics do not
constitute success or failure evidence. This instrumentation changes no budget,
task, score, validator or acceptance criterion.

The secondary SQLite ResourceWarning had a concrete local cause: SQLite connection
context managers manage transactions but do not close connections. The shared
SQLiteStore now uses a connection subclass that commits/rolls back through SQLite's
existing context behavior and closes in finally. Backup destinations close too.
Regression tests prove persisted commits, rollback and closed handles. This fixes
the shared-store lifecycle; it does not prove the cause of the host HTTP wait.

Lifecycle diagnostic verification (2026-09-08): baseline 347 ran (346 passed, one
optional live skip); final 355 ran in 81.205 seconds (354 passed, one optional live
skip). Focused lifecycle/IPC/provider/runtime/benchmark/documentation: 62/62.
Eight new tests cover no first frame, HTTP completion without IPC completion,
SIGTERM-ignore kill escalation, repeated near-deadline attempts, safe opt-in
logging, nonblocking diagnostic overflow, SQLite commit/close and rollback/close.
Two initial fixture timing assertions were corrected to separate spawn time from
cleanup and allow the intended child stage to execute; production budgets were
not altered. Existing loopback/partial-frame tests remain passing. Wheel build,
fresh offline installation and current-tree audits passed (179 files). Benchmark
outcomes and metrics are identical; only storage.py and agents.py implementation
hashes were refreshed. No live benchmark ran; host cause remains unconfirmed.

### SQLite setup failure and descriptor ownership

A subsequent host run failed in system initialization before any NVIDIA request,
with SQLite CANTOPEN and then EMFILE during directory cleanup. That run remains
INCONCLUSIVE — never reached provider execution. The earlier authenticated smoke
remains separate valid connectivity evidence.

Source audit: the application creates SQLite connections only in SQLiteStore.connect
and its backup destination. All store operations use scoped connections; no SQL
pool/cache or retained connection attribute was found. SparkleSystem constructs
many stores, including model runtime, memory, knowledge, automation, project, skill
and AI-builder stores. These own database paths, not persistent connections. A
system-wide close hook would not repair a handle lost before its store returns.
Connections are closed after each operation, before system/task teardown; strong
reference/GC-disabled tests establish that destruction is not required.

Confirmed remaining defect: connect() opened a ClosingConnection and configured
row_factory and two PRAGMAs BEFORE returning it to the caller's `with` statement.
If setup raised, __enter__/__exit__ had never run; the prior __exit__ closure fix
could not release the handle. The connect factory now owns that setup window and
closes on ANY escaping exception, including interruption. SQLite/OS setup failures
become StorageConnectionError with content-free structured metadata:
`{"stage":"storage_initialization","error_type":"storage_unavailable"}`.
It remains a sqlite3.OperationalError subtype for existing handlers. It is not
an agent outcome or provider failure, and does not change benchmark scoring.

Before/after local reproduction (GC disabled and connection references retained):
normal system creation stayed at 3,3,3,3 descriptors on the previous checkpoint.
Five injected failures during connection PRAGMA setup grew 3,4,5,6,7,8 before the
fix; after the fix they stayed 3,3,3,3,3,3. Explicitly closing the old leaked handles
returned the count to 3. This proves the setup-exception leak, not that it alone
caused the host's complete exhaustion. Its initial FD state and loaded module
provenance were not supplied. An unavailable path is not automatically EMFILE;
the structured error intentionally does not guess which CANTOPEN cause occurred.

The failure tests keep every connection object alive and check that native SQLite
operations reject it as closed. Tests cover both PRAGMAs, interrupted setup, backup,
later AISystemBlueprintStore initialization failure, repeated systems retained in
memory, all twelve successful scripted tasks, all twelve synthetic provider-timeout
tasks, setup failure, and temporary-directory removal. Earlier successful stores
hold no open connections when later initialization fails. Four direct raw SQLite
connections in test fixture/inspection code now explicitly close after transaction
exit as well; warning absence alone is not the evidence.

A separate subprocess LOWERS RLIMIT_NOFILE to 32, initializes ten systems, and
checks every possible descriptor in that range: before=3, after=3. It then fills
its own remaining slots, observes structured storage_unavailable, releases only
its own filler handles, and verifies successful temporary-directory cleanup.
No OS limit was increased. A process whose unrelated descriptors are already
exhausted must release those owners before cleanup needing new descriptors can
succeed; the application does not close arbitrary unrelated descriptors.

SQLite descriptors opened in the tests are non-inheritable. The NVIDIA worker
uses multiprocessing spawn and is passed only its explicit IPC socket and request
configuration, never a SQLite connection. The benchmark failure occurred before
any such worker was started. There is no provider quality result from this run.

Before a future live rerun, verify the host actually imports the installed fix
(the reported line number alone is not module provenance):

```sh
python -c 'import hashlib, pathlib, sparkle.storage as s; p=pathlib.Path(s.__file__); print(p); print(hashlib.sha256(p.read_bytes()).hexdigest()); print(hasattr(s,"StorageConnectionError"))'
```

No key or private database content is printed. Ordinary CI and this debugging
milestone make no live NVIDIA call. Tasks, scores, validators, model configuration,
Level 3 and deployment status remain unchanged.

Resource-lifecycle verification (2026-09-09): baseline 355 ran (354 passed, one
optional live skip); final 365 ran in 60.929 seconds (364 passed, one optional live
skip). Focused resource/storage/lifecycle/migration/benchmark/documentation: 51/51.
Ten new resource tests passed, retaining connection references and disabling GC.
The initial interruption fixture also intercepted its own closure assertion; that
assertion now calls the native SQLite method so it tests handle state rather than
re-triggering the injected interruption. Commit/rollback tests remain passing.
Wheel build, fresh offline installation and current-tree audits passed (180 files).
Baseline results are identical; only storage.py's implementation hash changed.
No credentialed benchmark ran and no live-model outcome is claimed.
