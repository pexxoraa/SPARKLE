# Level 3 real-host acceptance

Level 3 is accepted only from executed evidence. Repository tests, a successful
container build, or the credential-free host diagnostic are not substitutes for a
real external worker run.

Deployment remains frozen. Level 3 execution authorizes only the fixed
`python_unittest` capability and never authorizes publishing or production
mutation.

## Required worker revision

The host must run the same repository revision being accepted. All supported
runtime surfaces resolve to the Level-3 worker:

- installed console script: `sparkle-worker = sparkle.level3_worker:entrypoint`
- container entrypoint: `python3 -m sparkle.level3_worker`
- Compose healthcheck: `python3 -m sparkle.level3_worker --check`
- systemd service: `/opt/sparkle/.venv/bin/sparkle-worker`
- CI diagnostic: `python -m sparkle.level3_worker --diagnose`

The legacy `sparkle.worker_service` module remains an internal base implementation
and test surface. It is not an accepted deployment entrypoint.

## GitHub environment prerequisites

The manual workflow `.github/workflows/level3-worker-acceptance.yml` uses the
GitHub Environment named `sparkle-level3-worker`. Configure exactly these values:

- environment variable `SPARKLE_EXTERNAL_WORKER_URL`: the public HTTPS URL ending
  in `/v1/jobs`; no username, password, query string, or fragment
- environment variable `SPARKLE_EXTERNAL_WORKER_ID`: the exact remote
  `SPARKLE_WORKER_ID`
- environment secret `SPARKLE_WORKER_SIGNING_KEY`: the same 32-4096 byte HMAC
  credential installed on the worker

The signing value must never be committed or printed. For systemd, the supported
host configuration uses `LoadCredential` and
`SPARKLE_WORKER_SIGNING_KEY_FILE=%d/sparkle-worker-signing-key`. For Compose, the
credential is mounted as a container secret.

## Host prerequisites

The accepted host is Linux and must provide all of the following:

1. Bubblewrap at the configured `SPARKLE_WORKER_BWRAP` path.
2. Working user, mount, PID/process, and network isolation required by the
   `SPARKLE-WORKER-BUBBLEWRAP/1` preflight.
3. `PR_SET_NO_NEW_PRIVS` support.
4. A dedicated non-root worker identity.
5. A private persistent state directory. The systemd profile uses
   `/var/lib/sparkle-worker`; the Compose deployment uses the `worker-state`
   volume. This state contains replay and Level-3 lifecycle SQLite databases.
6. The fixed Python runtime configured by `SPARKLE_WORKER_PYTHON`.
7. Inbound reachability from the GitHub Actions runner to the public HTTPS
   endpoint. Execution inside Bubblewrap remains network-isolated.
8. TLS with a certificate and hostname trusted by the GitHub runner. Direct TLS
   may be configured on the worker, or a trusted terminating reverse proxy may be
   used. Non-loopback plaintext binding is rejected by `WorkerConfig`.

The included Compose topology keeps the worker on an internal network and exposes
only Caddy on 443. Caddy routes `/health`, `/v1/jobs`, and the signed
`/v1/jobs/cancel` endpoint. The worker process itself does not need public network
access.

## Automated real-host workflow

Run **SPARKLE Level 3 Worker Acceptance** manually against the upgraded worker.
The workflow retains its JSON/log evidence as a GitHub Actions artifact for 30
days.

The first probe is non-executing. It verifies:

- HTTPS connectivity and certificate/hostname validation
- exact worker identity
- exact Level-3 worker contract
- `python_unittest` as the only Level-3 capability
- the fixed authorized requesting-agent set
- forged HMAC rejection
- wrong-but-well-formed agent rejection
- unauthorized capability rejection
- malformed authority rejection
- Bubblewrap availability and preflight
- filesystem and network isolation
- all hostile canaries, including host read/write, process access, workspace
  escape, secret-environment exposure, prohibited network access, and artifact
  modification
- running cancellation support
- deployment remains unauthorized

The lifecycle probe then executes real worker jobs to verify:

- timeout classification
- execution-failure classification
- exact duplicate-request replay
- signed running cancellation through `/v1/jobs/cancel`
- persisted cancellation lifecycle evidence
- a successful fresh job after timeout, failure, and cancellation
- isolation evidence on every returned controlled result

Finally, `level3_acceptance.py` performs the provenance-bearing success chain:

`approved source candidate`
→ `real external runtime evaluation`
→ `controlled promotion`
→ `immutable controlled build`
→ `operator execution authorization`
→ `Level-3 worker`
→ `isolation validation`
→ `output-contract validation`
→ `result/trace evidence`
→ `controller verified result`

It also repeats the same controller request and requires exact idempotent replay
without a second worker side effect.

## Worker interruption/restart acceptance

A real worker-process interruption cannot be produced safely by the public worker
API and must not be faked by killing only a sandbox child. It therefore remains a
host-operator acceptance action.

On the named acceptance host:

1. Complete one automated Level-3 acceptance workflow run and retain its artifact.
2. Record the worker service/container identity and the latest persisted Level-3
   job IDs from `sparkle-worker --check` or `/health`.
3. Restart only the worker service/container using the host's service manager.
   Do not deploy application artifacts and do not alter the signing credential.
4. Confirm the same worker ID, state directory, and Level-3 database are present
   after restart and prior lifecycle records remain readable.
5. Run the manual acceptance workflow again. The post-restart run must pass the
   remote probe, lifecycle probe, and full approved-artifact chain with new job and
   trace IDs.
6. Retain the host service-manager restart evidence together with both workflow
   artifacts.

Only this host restart evidence may satisfy the `worker interruption/recovery`
real-host gate. A repository unit test or a killed unittest subprocess does not.

## Acceptance result rules

Level 3 software may be `COMPLETE` when repository implementation and deterministic
CI are green. Real-host acceptance is `EXTERNALLY BLOCKED` until the named worker
is reachable with the required GitHub Environment values and the host restart
procedure above has executed successfully.

Level 3 overall is `COMPLETE` only after all automated real-host probes, the full
approved-artifact chain, and the worker interruption/recovery procedure have
executed successfully on the named external worker. Deployment remains a separate,
explicitly frozen phase.
