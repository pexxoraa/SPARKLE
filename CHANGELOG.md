# Changelog

## 0.28.0-alpha.1 - 2026-09-01

- Added `SPARKLE-AI-SYSTEM-SOURCE-PROMOTION/1` for explicit, post-evaluation,
  approval-bound promotion into a dedicated controlled staging environment.
- Added exact candidate/plan/evaluation/approval identity checks, immutable
  source and destination digests, atomic no-overwrite materialization,
  invalidation/supersession, bounded lifecycle traces, deterministic replay,
  API, CLI, status, dashboard eligibility, and negative security tests.
- Promotion stops at staging. It does not build, package, publish, deploy,
  modify production source, or establish external-worker isolation evidence.

## 0.27.0-alpha.1 - 2026-08-31

- Added bounded `SPARKLE-AI-SYSTEM-RUNTIME-EVALUATION/1` requests for approved
  source candidates through the existing authenticated external-worker client.
- Added exact contract/plan/candidate validation, signed enforcement of runtime
  limits, explicit lifecycle and failure states, content-free results/traces,
  API, CLI, status, and isolated evaluation workspaces.
- Kept executable isolation, production verification, source promotion,
  publication, and deployment explicitly unverified or unexecuted.

## 0.26.0-alpha.1 - 2026-08-31

- Added bounded `SPARKLE-AI-SYSTEM-SOURCE-CANDIDATE/1` generation from an
  explicitly reviewed implementation plan through the model-agnostic router.
- Added separately approved provider disclosure, isolated candidate storage,
  explicit generated/reviewed/statically-verified/approved lifecycle states,
  content-free trace evidence, API/CLI/status/dashboard integration, and
  non-executing static verification.
- Kept runtime testing, external-worker submission, production promotion,
  publication, and deployment explicitly unexecuted.

## 0.25.0-alpha.1 - 2026-08-31

- Added deterministic `SPARKLE-AI-SYSTEM-IMPLEMENTATION-PLAN/1` derivation from
  fully revalidated AI System Blueprints.
- Added provider-neutral architecture inputs, bounded unique proposed paths,
  ordered work and release gates, evaluation/deployment review plans, explicit
  human-review state, approval-gated plan-only workspace materialization,
  content-free evidence, API, CLI, status, and dashboard integration.
- Kept source generation, human review completion, runtime evaluation,
  external deployment, live-provider verification, and remote CI explicitly
  unexecuted or unverified.

## 0.24.0-alpha.1 - 2026-08-31

- Added approval-gated `SPARKLE-AI-SYSTEM-DRAFT/1` conversion from bounded
  natural language to exact, duplicate-free structured AI System Blueprint
  requirements through the model-agnostic router.
- Added isolated no-context/no-tool execution, complete Blueprint
  revalidation, bounded content-free attempt evidence, and API, CLI, status,
  and dashboard integration.
- Verified deterministic injected-adapter behavior; live MiniMax semantic
  fidelity, implementation generation, runtime evaluation, deployment, and
  v0.24 remote CI remain unverified.

## 0.23.0-alpha.1 - 2026-08-31

- Added provider-neutral `SPARKLE-SKILL/1` mastery records with strictly
  validated evidence and transactionally derived levels 0-6.
- Added duplicate/future-evidence protection, optimistic updates,
  approval-gated archive, least-privilege agent reads, proactive rules, and
  API, CLI, status, and dashboard integration.

## 0.22.0-alpha.1 - 2026-08-31

- Added provider-neutral `SPARKLE-PROJECT/1` structured project state with
  validated lifecycle, dependencies, risks, milestones, blockers, progress,
  and next actions.
- Added optimistic updates, approval-gated archive, bounded content-free
  events, proactive alerts, least-privilege agent reads, API, CLI, and
  dashboard integration.

## 0.21.0-alpha.1 - 2026-08-30

- Added deterministic `SPARKLE-AI-SYSTEM-BLUEPRINT/1` requirements validation,
  registry-backed model capability/modality routing, agent/tool access checks,
  separate data-environment declarations, and evaluation/deployment plans.
- Added non-mutating preparation and approval-gated bounded workspace
  materialization with content-free attempt evidence.

## 0.20.0-alpha.1 - 2026-08-30

- Added approval-gated `SPARKLE-AGENT-EVALUATION/1` response-contract runs
  through an isolated no-context/no-tool orchestrator profile.
- Added strict bounded assertions and content-free persisted evaluation
  evidence with fail-closed manifest-drift and tool-call handling.

## 0.19.0-alpha.1 - 2026-08-30

- Added deterministic `SPARKLE-AGENT-BLUEPRINT/1` requirements-to-manifest
  preparation, production-router fixtures, approval-gated installation,
  persistent evidence, hot loading, rollback, API, CLI, and dashboard paths.

## 0.18.0-alpha.1 - 2026-08-30

- Added provider-neutral `SPARKLE-NOTIFICATION/1` dashboard delivery with
  validation, deduplication, retention, unread/read state, conditional
  automation actions, content-free traces, API, and dashboard support.

## 0.17.0-alpha.1 - 2026-08-30

- Added bounded knowledge-revision monitoring and research-change proactive
  evidence with deterministic content digests, opt-in controls, retention,
  conditional automation integration, API, CLI, and dashboard visibility.

## 0.16.0-alpha.1 - 2026-08-30

- Added validated structured schedule evidence, bounded conflict detection,
  and cooldown-aware `schedule_conflict` conditional automations without
  exposing calendar content.

## 0.15.0-alpha.1 - 2026-08-30

- Added provider-neutral `SPARKLE-CONTENT/1` text, image, audio, document, and
  mixed-modality transport contracts across API, context, routing, model
  requests/results, and raw-content-free traces.
- Added the 16-agent domain matrix, expanded interface contracts, documentation
  validation, and cohesive end-to-end coverage.

## 0.14.0-alpha.1 - 2026-08-29

- Added evidence-backed proactive intelligence for deadlines, weak learning,
  revision, incomplete projects, and repeated mistakes with bounded structured
  outputs and conditional automation integration.

## 0.13.0-alpha.1 - 2026-08-29

- Added a separately supervised automation service with single-instance
  locking, expiring claims, crash recovery, stale-runner fencing, persisted
  health, signal draining, packaging, and hardened systemd configuration.

## 0.12.0-alpha.1 - 2026-08-29

- Added deterministic content-addressed application ZIP artifacts with exact
  manifests, immutable integrity checks, portable path validation, explicit
  approval, and append-only explicitly unverified deployment records.

## 0.11.0-alpha.1 - 2026-08-29

- Added the separately installable worker service with exact signed schemas,
  replay/idempotency storage, bounded concurrency, fixed executors, key-file
  controls, fail-closed Bubblewrap preflight, and deployment profiles.
- Kept real namespace isolation, a named remote instance, and hostile-code
  isolation validation explicitly unverified.

## 0.10.0-alpha.1 - 2026-08-29

- Added the disabled-by-default external worker client with bounded source
  bundles, exact HMAC-authenticated request/response schemas, strict response
  validation, safe evidence, operator approval, API, CLI, and dashboard paths.

## 0.9.0-alpha.1 - 2026-08-29

- Added bounded, process-local dashboard sessions exchanged from the existing
  secret-resolved API bearer credential.
- Added host-only HttpOnly `SameSite=Strict` cookies, configurable `Secure`,
  absolute expiry, capacity eviction, CSRF tokens for mutations, reload
  recovery, logout/revocation, and credential-free session status.
- Added a dashboard authentication gate that never writes tokens to local or
  session storage, while preserving bearer authentication for API clients.
- Added fail-closed non-loopback session binding without secure cookies and
  expanded the deterministic regression suite from 68 to 72 tests.

## 0.8.0-alpha.1 - 2026-08-29

- Added a disabled-by-default Python unittest workspace runner with a fixed
  command; arbitrary executables, arguments, and package installation are not
  accepted.
- Added explicit enablement and per-run approval, strict parent-environment allowlisting,
  stripped child environment, workspace/symlink/file bounds, POSIX CPU/memory/
  file/process/descriptor limits, process-group wall timeout, output redaction,
  and persistent test-run evidence.
- Added CLI, API, dashboard, system-status, agent-tool, and configuration paths.
- Expanded the deterministic regression suite from 61 to 68 tests.

## 0.7.0-alpha.1 - 2026-08-29

- Added a thread-safe fixed-window API limiter applied before origin and bearer
  checks, with bounded in-memory client state and standard quota headers.
- Added a separate SQLite API audit store containing only method, query-free
  path, status, coarse outcome, duration, and timestamp.
- Added API audit and aggregate quota status endpoints/dashboard views without
  client identities, origins, headers, query values, request bodies, or tokens.
- Added configuration/environment overrides, query-stripped and unknown-route-normalized request logging,
  and expanded deterministic tests from 54 to 61.

## 0.6.0-alpha.1 - 2026-08-29

- Added optional bearer authentication using secret references and constant-time
  credential comparison.
- Added exact same-origin/allowlist enforcement and explicit CORS preflight
  responses without wildcard origins.
- Added fail-closed startup for missing required tokens and non-loopback binds
  without configured authentication.
- Added security status containing presence booleans/counts only.
- Added a console entrypoint that reports operational refusals without a
  traceback.
- Expanded the deterministic regression suite from 47 to 54 tests.

## 0.5.0-alpha.1 - 2026-08-29

- Added approval-gated static verification for generated application workspaces.
- Added non-executing Python compile, JavaScript syntax, and JSON parse checks.
- Added verification path/symlink/type/size/count bounds, five-second Node timeout,
  bounded output, a secret-free subprocess environment, and persistent evidence.
- Added CLI, API, dashboard, system-status, agent-tool, and end-to-end coverage.
- Expanded the deterministic regression suite from 41 to 47 tests.

## 0.4.0-alpha.1 - 2026-08-29

- Added persistent generated-agent installation, hot-loading, removal, and routing.
- Added approval-gated Agent Builder and workspace-scaffolding tools.
- Added bounded application workspaces with path, file-count, byte, symlink, and overwrite controls.
- Added executable scheduled and conditional automations with claims, retries, rescheduling, run history, and traces.
- Added CLI and API operations for generated agents, builds, and automation execution.
- Expanded the dashboard with generated-agent, automation-run, and build status.
- Expanded the deterministic regression suite from 32 to 41 tests.

## 0.3.0-alpha.1 — 2026-08-28

- Created the first GitHub-ready SPARKLE foundation.
- Added model-neutral contracts, registry, routing, and MiniMax-M3 Messages adapter.
- Added 16 modular agents and single/multi-agent orchestration.
- Added separate SQLite memory, knowledge, data, and trace environments.
- Added safe tools, automation records, proactive deadline rules, voice/presence interfaces, CLI, API, and dashboard.
- Added 32 deterministic unit/integration/security/end-to-end tests and CI.
- Documented verified, partial, blocked, and deferred Definition-of-Done items.
