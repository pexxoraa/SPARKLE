# SPARKLE Level 3 gate status — 2026-09-15

This document records the current Level-3 acceptance split. It is an acceptance-gate addendum to `CURRENT_AUDIT.md`; it does not reinterpret deterministic software checks as real-host evidence.

## Current authoritative state

- Published certified repository revision before the current private/local worker integration: `b56693bb759a9d3e136e594635b50fdf64d1ae85` (tree `a6c3e18ecfc423afbd7b4f076b8f4bad7654cd2a`).
- Exact-head SPARKLE CI: run `34984651242` / run number 193 — **PASS** across all five jobs.
- Python 3.12: **PASS**.
- Python 3.13: **PASS**.
- Current published-baseline local suite: **PASS**; later private/local integration tests are tracked separately until publication.
- Controlled-execution / Level-3 deterministic software gate: **PASS** on the published baseline; the private/local integration candidate expands this gate with binary-key/TLS regressions.
- Worker image: **PASS**.
- Automation service: **PASS**.
- Credential-free benchmark reproduction: **PASS**.

The deterministic host diagnostic on the GitHub-hosted runner reports Bubblewrap/user/mount/network namespaces unavailable and therefore explicitly reports `level_3_verified=false`. This is expected runner evidence and is not real-host acceptance.

## Level-3 classification

- **Level-3 software: COMPLETE**
- **Level-3 deterministic acceptance: COMPLETE**
- **Level-3 real worker local host readiness: VERIFIED on `prem-macharla`**
- **Level-3 local worker restart/recovery: VERIFIED on `prem-macharla`**
- **Level-3 private/local acceptance: READY**
- **Level-3 public trusted-remote acceptance: DEFERRED — PUBLIC DEPLOYMENT**
- **Level-3 public remote restart/post-restart acceptance: DEFERRED — PUBLIC DEPLOYMENT**
- **Deployment: FROZEN**

The real host worker is locally ready: the hardened systemd service is active on loopback, its `/health` reports `ready=true`, executor/preflight/filesystem/network isolation true, all seven hostile canaries true, credentials not exposed, and deployment unauthorized. A genuine `systemctl restart sparkle-worker.service` changed the worker PID from `236382` to `239329`; the new process retained the certified installed source hashes and returned the same complete ready contract. This is private/local service restart/recovery evidence. Public GitHub-hosted remote acceptance is a separate future deployment gate and is not inferred from it.

## Public remote acceptance — DEFERRED — PUBLIC DEPLOYMENT

Public GitHub-hosted remote acceptance is intentionally out of scope for the current private/local target. The worker remains loopback-only and must not be exposed publicly. A future public-deployment phase may configure a protected GitHub Environment and trusted public ingress, but their absence does not block private/local readiness.

Future public-deployment actions, if explicitly authorized, would be:

> Provision a named trusted-HTTPS ingress to the loopback worker, create and
> securely configure the `sparkle-level3-worker` GitHub Environment, then
> dispatch SPARKLE Level 3 Worker Acceptance.

The GitHub Environment must provide:

- `SPARKLE_EXTERNAL_WORKER_URL`
- `SPARKLE_EXTERNAL_WORKER_ID`
- secret `SPARKLE_WORKER_SIGNING_KEY`

Any future public remote host must run the same accepted repository revision and satisfy `LEVEL3_ACCEPTANCE.md`; this does not alter the current private/local acceptance target.

## Future public remote evidence

If a future public remote campaign is authorized, the manual workflow must retain its `sparkle-level3-acceptance-<run_id>` artifact containing distinct evidence for:

1. `remote-probe.json` / `.log`: HTTPS/TLS, exact worker identity, Level-3 contract, Bubblewrap/preflight and hostile isolation canaries, forged HMAC rejection, wrong-agent rejection, unauthorized-capability rejection, malformed-authority rejection, cancellation availability, and deployment remaining unauthorized.
2. `lifecycle-probe.json` / `.log`: real timeout, execution failure, exact duplicate replay, signed running cancellation, persisted cancellation state, verified isolation on returned results, and recovery with a fresh successful job.
3. `full-chain.json` / `.log`: approved source/runtime evaluation, controlled promotion, immutable build, execution authorization, external Level-3 execution, output/isolation validation, artifact provenance, result digest, requesting-agent/capability/policy/output-contract identity, trace association, controller replay idempotency, and no deployment/production mutation.

These workflow artifacts do not by themselves prove a worker-service interruption/restart.

## Private/local worker interruption/restart gate

The local systemd restart/recovery has been demonstrated on `prem-macharla`. For private/local readiness, the current installed build must again survive a genuine service restart and continue to pass localhost TLS health plus signed execution. Pairing the restart with GitHub-hosted remote workflow artifacts is deferred to public deployment.

Killing a sandbox child or unittest process is not accepted as worker-interruption evidence.

## Hardened deployment surfaces

The repository surfaces under deterministic regression coverage use the hardened worker:

- console script: `sparkle-worker = sparkle.level3_worker:entrypoint`
- Docker entrypoint: `python3 -m sparkle.level3_worker`
- Compose healthcheck: `python3 -m sparkle.level3_worker --check`
- systemd service: `/opt/sparkle/.venv/bin/sparkle-worker`
- CI diagnostic: `python -m sparkle.level3_worker --diagnose`
- HTTPS gateway routes `/health`, `/v1/jobs`, and `/v1/jobs/cancel`
- manual acceptance workflow executes the remote, lifecycle, and full-chain probes and retains evidence

The legacy `sparkle.worker_service` module remains an internal base/test implementation; it is not an accepted deployment entrypoint.

## Independent acceptance state

Nemotron live-agent evidence remains unchanged: 3 of 12 tasks validated, 9 rejected, 25% validation pass rate, `agent_competence_verified=false`. Level-3 acceptance does not alter that benchmark result.

Level-3 **private/local** readiness is complete when the exact installed build passes localhost TLS health, signed execution, isolation canaries and genuine service restart/recovery. Public remote acceptance is **DEFERRED — PUBLIC DEPLOYMENT**. Deployment remains a separate explicit authorization gate and stays **FROZEN**.
