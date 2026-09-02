# Controlled execution

`SPARKLE-AI-SYSTEM-CONTROLLED-EXECUTION/1` is the boundary after controlled
build. It executes only an immutable controlled-build artifact and stops after
authenticated result verification.

## Trust sequence

1. Reload the `built` record and its authoritative promotion, candidate,
   implementation plan, and successful runtime evaluation.
2. Require a separate unexpired, one-use authorization bound to every identity,
   mode, timeout, output limit, actor, and origin. Require the exact deterministic
   `SPARKLE-CONTROLLED-EXECUTION-POLICY/1` object in the request contract.
3. Reject an invalidated or superseded artifact. Verify its database record,
   stable regular file, SHA-256, canonical ZIP manifest, entry paths/types,
   sizes, and entry digests.
4. Extract only verified regular UTF-8 entries into an ephemeral controller
   workspace and recheck the immutable archive immediately before submission.
5. Submit through `SPARKLE-WORKER-CONTROLLED-EXECUTION/1`, which reuses the
   existing HTTPS/HMAC freshness, replay store, fixed executor, bounded output,
   timeout/process termination, minimal environment, and cleanup controls.
6. Verify the signed response, exact execution/artifact context, configured and
   pinned worker identity,
   output digest, canonical result digest, status, and timestamps. Delete the
   controller workspace in every outcome.

## Lifecycle

Success is `REQUESTED → AUTHORIZED → QUEUED → SUBMITTED → RUNNING → COMPLETED
→ VERIFIED`. Terminal failures distinguish rejection, authorization failure,
artifact mismatch, timeout, unavailable worker, worker authentication failure,
protocol failure, execution failure, output-limit failure, isolation failure,
result-integrity failure, and cancellation.
The store enforces the legal transition graph; direct lifecycle skips fail.

`VERIFIED` does not mean isolation-verified, published, deployed, production,
or released. Those flags and stages remain separate.

## Signed execution policy

- operation: fixed Python `unittest`
- network: disabled
- wall time: 1–60 seconds
- output: 100–12,000 characters
- address space: 512 MiB
- CPU: equal to the approved wall timeout
- processes: 32
- input workspace: 5 MB, 500 files, 500 KB per file
- environment: fixed allowlist; no SPARKLE credentials
- artifact mount: read-only; writable state is temporary and separate

## Evidence levels

- Level 1: the controller and worker contracts are implemented and tested.
- Level 2: the real local service, HMAC round trip, fixed process executor,
  result verifier, and cleanup execute successfully. Process mode is never
  described as filesystem or network isolation.
- Level 3: Bubblewrap must pass its executable hostile-canary preflight on the
  actual worker. `SPARKLE-WORKER-BUBBLEWRAP/1` emits signed booleans for host
  read/write refusal, cross-workspace refusal, secret environment absence,
  network denial, host-process refusal, and artifact-modification refusal.

On the current build host, Bubblewrap 0.9.0 is installed but namespace setup is
denied, producing `IsolationPreflightFailed`. Level 3 is therefore blocked and
`isolation_verified` remains false.

## Interfaces

CLI:

- `ai-system-execution-approve`
- `ai-system-controlled-execute`
- `ai-system-execution-cancel`
- `ai-system-controlled-executions`
- `ai-system-controlled-execution-status`
- `ai-system-controlled-execution-result`

Authenticated API:

- `POST /api/ai-systems/execution/approve`
- `POST /api/ai-systems/execution/request`
- `POST /api/ai-systems/execution/cancel`
- `GET /api/ai-system-controlled-executions`
- `GET /api/ai-system-controlled-executions/<execution-id>`
- `GET /api/ai-system-controlled-executions/<execution-id>/result`

`tests/controlled_execution_harness.py` is explicitly a test harness. It can
simulate timeout, output overflow, execution failure, identity mismatch,
result tampering, and transport failure, but never produces Level 3 evidence.

Cancellation is deterministic before worker submission (`REQUESTED`,
`AUTHORIZED`, or `QUEUED`) and always cleans the controller workspace. The v1
synchronous worker protocol intentionally has no remote cancellation command;
after `RUNNING`, its signed wall timeout and process-group termination are the
fail-closed termination mechanism. Remote operator cancellation is therefore
infrastructure/protocol-dependent and is not claimed as implemented.
