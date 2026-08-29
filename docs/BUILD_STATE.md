# Build state

Updated: 2026-08-29 UTC

| Field | State |
|---|---|
| SPARKLE version | 0.10.0-alpha.1 |
| Current phase | Phase 36 — release |
| Current task | Publish and CI-verify the v0.10 signed external-worker client boundary |
| Completed | v0.3-v0.9 private GitHub releases/CI; model abstraction/registry/MiniMax adapter; orchestrator/context/tracing; memory and knowledge lifecycle with backup; 16 built-in agents; persistent generated-agent installation; bounded workspaces, static verification, opt-in fixed local Python tests, and a disabled/operator-only signed external-worker client protocol; executable internal automations; safe tools; text API/CLI/dashboard; secret-resolved bearer auth; bounded process-local dashboard sessions with CSRF and revocation; exact origin/preflight policy; fail-closed network/session binding; bounded API rate limiting; secret-free API audit; proactive rules; presence interface; 81-test regression suite |
| In progress | v0.10 GitHub capability publication, exact-tree comparison, and Python 3.12/3.13 CI |
| Blocked | Deployed compatible hardened external worker and live isolation validation; live MiniMax call (no key in build process); deployed TLS/reverse-proxy validation; voice hardware; browser/computer runtime adapters; public deployment target |
| Failed tests | None; latest local `make check` ran 81 tests successfully |
| Next action | Publish the exact tested tree and validate GitHub CI, then design the deployable hardened worker service |
| Estimated directive completion | 67% |

The percentage measures the full long-term directive, not code volume. Agent
specifications are operational through the common orchestrator, and generated
agents, internal automation execution, bounded workspace creation, and static
workspace verification and the signed external-worker protocol boundary now
have runtime evidence. Autonomous code generation and hardened build/package
execution, live
research/browser control, real voice, physical embodiment, service-managed
scheduling, multi-user role authorization, TLS/edge rate limiting, and deployment are not
complete.
