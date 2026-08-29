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
preflight policy, fail-closed bind validation, and the dashboard.
The API-security cases also cover deterministic fixed-window reset/rejection,
bounded client state, rate limiting before authorization, quota response
headers, query stripping, and absence of credentials, origins, headers, and
client identities from audit records.
Request-log coverage verifies that query names and values are stripped.
Workspace-runner coverage executes a real fixed unittest suite and verifies
POSIX resource limits, a stripped child environment, credential-pattern output
redaction, parent-secret refusal, symlink and arbitrary-field rejection,
process-group wall timeout, pre-persistence output bounding, persistence, CLI/API/dashboard integration, and
explicit status that filesystem/network isolation is absent.

The deterministic adapter avoids provider cost and network flakiness. The live
smoke test is intentionally separate:

```bash
sparkle smoke-test --live
```

Never report the live test as passed when the credential is absent or the exact
`SPARKLE_LIVE_OK` response is not observed.

Latest v0.8 pre-release result on 2026-08-29: 68 tests passed in 9.102 seconds.
Dashboard JavaScript syntax and Git whitespace checks also passed. See
`RELEASE_REPORT.md` for the complete release evidence and live-provider blocker.
