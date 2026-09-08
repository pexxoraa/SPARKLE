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
