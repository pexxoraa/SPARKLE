# Changelog

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
