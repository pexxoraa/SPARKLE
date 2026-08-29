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
sandboxing, orchestration, multi-agent synthesis, the HTTP API, security
headers, and the dashboard.

The deterministic adapter avoids provider cost and network flakiness. The live
smoke test is intentionally separate:

```bash
sparkle smoke-test --live
```

Never report the live test as passed when the credential is absent or the exact
`SPARKLE_LIVE_OK` response is not observed.

Latest v0.4 release-state result on 2026-08-29: 41 tests passed in 4.293 seconds.
Dashboard JavaScript syntax and Git whitespace checks also passed. See
`RELEASE_REPORT.md` for the complete release evidence and live-provider blocker.
