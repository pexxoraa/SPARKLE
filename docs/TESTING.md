# Testing

Run:

```bash
make check
```

The command compiles all Python files and runs the standard-library `unittest`
suite. Coverage includes secrets, configuration, model registry operations,
MiniMax request mapping, provider-state preservation, retry and streaming,
memory, knowledge, traces, automations, proactive rules, tool sandboxing, agent
routing, orchestration, multi-agent synthesis, the HTTP API, security headers,
and the dashboard.

The deterministic adapter avoids provider cost and network flakiness. The live
smoke test is intentionally separate:

```bash
sparkle smoke-test --live
```

Never report the live test as passed when the credential is absent or the exact
`SPARKLE_LIVE_OK` response is not observed.

Latest post-publication-documentation result on 2026-08-28: 32 tests passed in
2.291 seconds. See
`RELEASE_REPORT.md` for the executed commands, the corrected failed attempt, and
the live-provider blocker.
