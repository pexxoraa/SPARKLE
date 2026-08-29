# Testing

Run:

```bash
make check
```

The command compiles all Python files and runs the standard-library `unittest`
suite. Coverage includes secrets, configuration, model registry operations,
MiniMax request mapping, provider-state preservation, retry and streaming,
memory lifecycle and backup, knowledge lifecycle and backup, traces, automation
claiming/execution/retry/recurrence/cooldown/history, proactive rules, generated
agent persistence/routing/removal, bounded workspace scaffolding, tool
sandboxing, static workspace verification, non-execution guarantees, CLI
scaffold-to-verify flow, orchestration, multi-agent synthesis, the HTTP API,
security headers, bearer authorization, unauthorized non-mutation, origin and
preflight policy, fail-closed bind validation, and the dashboard. Session tests
cover login failure/success, opaque HttpOnly cookies, absolute expiry, bounded
capacity, reload recovery, CSRF rejection/acceptance, logout/revocation, remote
secure-cookie binding, secret-free status/audit, and absence of browser storage.
The API-security cases also cover deterministic fixed-window reset/rejection,
bounded client state, rate limiting before authorization, quota response
headers, query stripping, and absence of credentials, origins, headers, and
client identities from audit records.
Supervised-automation coverage adds legacy-schema migration, expiring claims,
explicit recovery records, old-token fencing, real deterministic orchestrator
execution and traces, singleton lock refusal, mode-0600/no-follow lock policy,
bounded degraded cycles, fresh/stale lifecycle status, pre-requested shutdown,
installed-style CLI check/once/status/health behavior, a real subprocess
SIGTERM drain, and systemd hardening inspection.
Request-log coverage verifies that query names and values are stripped.
Workspace-runner coverage executes a real fixed unittest suite and verifies
POSIX resource limits, a stripped child environment, credential-pattern output
redaction, parent-secret refusal, symlink and arbitrary-field rejection,
process-group wall timeout, pre-persistence output bounding, persistence, CLI/API/dashboard integration, and
explicit status that filesystem/network isolation is absent.
External-client coverage uses a deterministic signed worker double to verify
request signatures, source digests and bounds, response signatures, freshness,
job identity, exact schemas, status consistency, output redaction, safe
persistence, disabled/default behavior, operator approval, non-registration as
a model tool, and API/CLI integration.
Adversarial cases cover signature tampering, stale responses, mismatched job
IDs, unknown fields, oversized responses, transport failures, symlinks, hidden
and credential-like files, non-UTF-8 files, oversized files, and source that
contains the configured signing key.

Reference-worker coverage adds real server-side request validation, private
no-follow key files, replay/idempotency conflict behavior, concurrency refusal,
executor-unavailable recovery, exact-key response redaction, signed health/job
HTTP behavior, immutable Bubblewrap command inspection, real Bubblewrap
preflight, process timeout, deployment-policy inspection, and a true in-memory
client → service → child unittest → signed response workflow. That workflow
imports submitted application code and persists the verified client result.
The process executor explicitly reports no isolation. The production executor
reports ready only when its real namespace/canary/environment/network preflight
succeeds. Worker sandbox booleans remain explicitly unverified claims at the
application client.

Artifact coverage verifies byte-for-byte deterministic ZIP output, canonical
embedded manifests, normalized archive metadata, immutable content-addressed
reuse, new artifacts after source changes, tamper refusal, stable no-follow
file reads, symlink/sensitive/reserved/portable-name/size rejection, approval
gates, CLI/API/dashboard integration, and append-only deployment reports that
remain explicitly unverified and execute no external action.

The deterministic adapter avoids provider cost and network flakiness. The live
smoke test is intentionally separate:

```bash
sparkle smoke-test --live
```

Never report the live test as passed when the credential is absent or the exact
`SPARKLE_LIVE_OK` response is not observed.

Latest v0.13 release-state result on 2026-08-29: 114 tests passed in 21.288
seconds. Dashboard JavaScript syntax, Git whitespace, offline installation, and
the installed automation check/once/status lifecycle also passed. See
`RELEASE_REPORT.md` for remote evidence and external blockers.
