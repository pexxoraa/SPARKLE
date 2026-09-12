# SPARKLE Level 3 gate status — 2026-09-12

This document records the current Level-3 acceptance split. It is an acceptance-gate addendum to `CURRENT_AUDIT.md`; it does not reinterpret deterministic software checks as real-host evidence.

## Current authoritative state

- Repository head before this status-only update: `4d48a4ec6fd282cf35eca7c6470d458ba446e5e0`.
- Exact-head SPARKLE CI: run `34667812450` / run number 177 — **PASS**.
- Python 3.12: **PASS**.
- Python 3.13: **PASS**; 534 tests run, 1 skipped, 0 failures.
- Controlled-execution / Level-3 deterministic software gate: **PASS**; 82 tests run, 0 failures.
- Worker image: **PASS**.
- Automation service: **PASS**.
- Credential-free benchmark reproduction: **PASS**.

The deterministic host diagnostic on the GitHub-hosted runner reports Bubblewrap/user/mount/network namespaces unavailable and therefore explicitly reports `level_3_verified=false`. This is expected runner evidence and is not real-host acceptance.

## Level-3 classification

- **Level-3 software: COMPLETE**
- **Level-3 deterministic acceptance: COMPLETE**
- **Level-3 real-host acceptance: EXTERNALLY BLOCKED**
- **Level 3 overall: NOT COMPLETE**
- **Deployment: FROZEN**

No real external-worker result, isolation result, service/container restart result, or production result is inferred from repository CI.

## Real-host acceptance not yet observed

No `SPARKLE Level 3 Worker Acceptance` workflow run exists in the repository Actions history inspected on 2026-09-12. The connected GitHub automation surface can inspect and rerun existing runs/jobs but does not expose `workflow_dispatch`; therefore there is no existing real-host run that can be legitimately rerun from this session.

The exact required external action is:

> Run SPARKLE Level 3 Worker Acceptance against the configured sparkle-level3-worker environment.

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

A host operator must record the real service/container state and worker revision, interrupt or restart the worker service/container itself, verify recovery with the same worker identity and persistent state, and rerun the manual acceptance workflow. Retain the service-manager/container restart evidence together with both pre- and post-restart acceptance artifacts.

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
