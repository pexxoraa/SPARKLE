# SPARKLE Level 3 gate status — 2026-09-15

This document records the current Level-3 acceptance split. It is an acceptance-gate addendum to `CURRENT_AUDIT.md`; it does not reinterpret deterministic software checks as real-host evidence.

## Current authoritative state

- Published certified repository revision: `b013d768ddd0a7161a394b4c78afef9a50384eb1` (tree `ac0c9ee9e4972fbda116971577b923aab445e18b`).
- Exact-head SPARKLE CI: run `34973509546` / run number 192 — **PASS** across all five jobs.
- Python 3.12: **PASS**.
- Python 3.13: **PASS**.
- Current audit candidate local suite: **PASS**; 546 tests run, 1 skipped, 0 failures.
- Controlled-execution / Level-3 deterministic software gate: **PASS**; 85 tests run, 0 failures.
- Worker image: **PASS**.
- Automation service: **PASS**.
- Credential-free benchmark reproduction: **PASS**.

The deterministic host diagnostic on the GitHub-hosted runner reports Bubblewrap/user/mount/network namespaces unavailable and therefore explicitly reports `level_3_verified=false`. This is expected runner evidence and is not real-host acceptance.

## Level-3 classification

- **Level-3 software: COMPLETE**
- **Level-3 deterministic acceptance: COMPLETE**
- **Level-3 real worker local host readiness: VERIFIED on `prem-macharla`**
- **Level-3 local worker restart/recovery: VERIFIED on `prem-macharla`**
- **Level-3 trusted remote acceptance: EXTERNALLY BLOCKED**
- **Level-3 remote restart/post-restart acceptance: EXTERNALLY BLOCKED**
- **Level 3 overall: NOT COMPLETE**
- **Deployment: FROZEN**

The real host worker is locally ready: the hardened systemd service is active on loopback, its `/health` reports `ready=true`, executor/preflight/filesystem/network isolation true, all seven hostile canaries true, credentials not exposed, and deployment unauthorized. A genuine `systemctl restart sparkle-worker.service` changed the worker PID from `236382` to `239329`; the new process retained the certified installed source hashes and returned the same complete ready contract. This is local service restart/recovery evidence only. No trusted-HTTPS remote acceptance, GitHub Environment acceptance, remote post-restart workflow evidence, or production result is inferred from it.

## Trusted remote acceptance not yet observed

No `SPARKLE Level 3 Worker Acceptance` workflow run exists in the repository
Actions history inspected on 2026-09-14, and the repository currently has zero
GitHub Environments. The workflow does expose `workflow_dispatch`, but a valid run
cannot be created until the protected `sparkle-level3-worker` Environment and its
variables/secret exist. The host also has no trusted public HTTPS ingress: the
worker listens only on `127.0.0.1:8770`.

The exact required external actions are:

> Provision a named trusted-HTTPS ingress to the loopback worker, create and
> securely configure the `sparkle-level3-worker` GitHub Environment, then
> dispatch SPARKLE Level 3 Worker Acceptance.

The GitHub Environment must provide:

- `SPARKLE_EXTERNAL_WORKER_URL`
- `SPARKLE_EXTERNAL_WORKER_ID`
- secret `SPARKLE_WORKER_SIGNING_KEY`

The remote host must run the same accepted repository revision and satisfy the prerequisites in `LEVEL3_ACCEPTANCE.md`, including trusted HTTPS/TLS, persistent worker state, Bubblewrap namespaces, no-new-privileges, the hardened Level-3 worker entrypoint, and the fixed authority contract.

## Required real-host evidence

The manual workflow must retain its `sparkle-level3-acceptance-<run_id>` artifact containing distinct evidence for:

1. `remote-probe.json` / `.log`: HTTPS/TLS, exact worker identity, Level-3 contract, Bubblewrap/preflight and hostile isolation canaries, forged HMAC rejection, wrong-agent rejection, unauthorized-capability rejection, malformed-authority rejection, cancellation availability, and deployment remaining unauthorized.
2. `lifecycle-probe.json` / `.log`: real timeout, execution failure, exact duplicate replay, signed running cancellation, persisted cancellation state, verified isolation on returned results, and recovery with a fresh successful job.
3. `full-chain.json` / `.log`: approved source/runtime evaluation, controlled promotion, immutable build, execution authorization, external Level-3 execution, output/isolation validation, artifact provenance, result digest, requesting-agent/capability/policy/output-contract identity, trace association, controller replay idempotency, and no deployment/production mutation.

These workflow artifacts do not by themselves prove a worker-service interruption/restart.

## Mandatory worker interruption/restart gate

The local systemd restart/recovery has been demonstrated on `prem-macharla`, but the acceptance gate still requires the same genuine service/container interruption to be paired with retained trusted-remote acceptance evidence before and after the restart. Retain the service-manager/container restart evidence together with both pre- and post-restart workflow artifacts.

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

Level 3 may be changed to **COMPLETE** only after the real remote probe, lifecycle probe, complete-chain acceptance, and genuine worker service/container interruption/recovery have all produced retained passing evidence. Deployment remains a separate explicit authorization gate and stays **FROZEN**.
