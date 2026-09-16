# SPARKLE Level 3 gate status — 2026-09-16

This document records the current Level-3 acceptance split. It is an acceptance-gate addendum to `CURRENT_AUDIT.md`; it does not reinterpret deterministic software checks as real-host evidence.

## Current authoritative state

- Current published certified private/local revision: `32643a826dc394c9a86244fa724932c797fce08a` (tree `11f6e56414b1a3d94bfbaa9b1c133f4f671e8778`).
- Exact-head SPARKLE CI: run `35068307402` / run number 199 — **PASS** across all five jobs.
- Python 3.12: **PASS**.
- Python 3.13: **PASS**.
- Current private/local integration is published and exact-head CI-certified; final focused security/worker/browser/documentation regression: **76/76 PASS**; full local `make check`: **552 tests, 1 intentional live-provider skip, 0 failures**.
- Controlled-execution / Level-3 deterministic software gate: **PASS**; real installed binary-key/TLS controlled execution is also verified.
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

The real host worker is locally ready: the hardened systemd service is active on loopback, its `/health` reports `ready=true`, executor/preflight/filesystem/network isolation true, all seven hostile canaries true, credentials not exposed, direct TLS true and deployment unauthorized. The current installed `sparkle` package has 89/89 files matching the published source tree with zero missing, mismatched or extra files. The mandatory second `systemctl restart sparkle-worker.service` changed PID `733750` to `737630`; replay-store count 14 and Level-3 lifecycle counts (`cancelled=1`, `completed=4`, `failed=3`) survived unchanged. A fresh post-restart signed execution `SPK-EXEC-7BDA9E78AC294320ABFF230B1AD110EC` completed and verified with isolation evidence. Public GitHub-hosted remote acceptance is a separate future deployment gate and is not inferred from it.

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

Any future public remote host must run the same accepted repository revision and satisfy `LEVEL3_ACCEPTANCE.md`; this does not alter the current private/local acceptance result.

## Future public remote evidence

If a future public remote campaign is authorized, the manual workflow must retain its `sparkle-level3-acceptance-<run_id>` artifact containing distinct evidence for:

1. `remote-probe.json` / `.log`: HTTPS/TLS, exact worker identity, Level-3 contract, Bubblewrap/preflight and hostile isolation canaries, forged HMAC rejection, wrong-agent rejection, unauthorized-capability rejection, malformed-authority rejection, cancellation availability, and deployment remaining unauthorized.
2. `lifecycle-probe.json` / `.log`: real timeout, execution failure, exact duplicate replay, signed running cancellation, persisted cancellation state, verified isolation on returned results, and recovery with a fresh successful job.
3. `full-chain.json` / `.log`: approved source/runtime evaluation, controlled promotion, immutable build, execution authorization, external Level-3 execution, output/isolation validation, artifact provenance, result digest, requesting-agent/capability/policy/output-contract identity, trace association, controller replay idempotency, and no deployment/production mutation.

These workflow artifacts do not by themselves prove a worker-service interruption/restart.

## Private/local worker interruption/restart gate

The current installed build has survived the required second genuine systemd restart on `prem-macharla`, retained replay and Level-3 lifecycle state, continued to pass localhost TLS health and all seven hostile canaries, and completed a fresh signed execution afterward. Pairing local restart evidence with GitHub-hosted remote workflow artifacts is deferred to public deployment.

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

Level-3 **private/local** readiness is **COMPLETE**: trusted localhost TLS, binary HMAC, signed success, execution failure, timeout, exact replay without duplicate worker work, signed running cancellation, isolation validation, persistent worker state and genuine restart/post-restart execution are all observed on the installed build. Public remote acceptance is **DEFERRED — PUBLIC DEPLOYMENT**. Deployment remains a separate explicit authorization gate and stays **FROZEN**.
