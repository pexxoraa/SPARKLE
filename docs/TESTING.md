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

The deterministic adapter avoids provider cost and network flakiness. The live
smoke test is intentionally separate:

```bash
sparkle smoke-test --live
```

Never report the live test as passed when the credential is absent or the exact
`SPARKLE_LIVE_OK` response is not observed.

Latest v0.6 pre-release result on 2026-08-29: 54 tests passed in 6.953 seconds.
Dashboard JavaScript syntax and Git whitespace checks also passed. See
`RELEASE_REPORT.md` for the complete release evidence and live-provider blocker.
