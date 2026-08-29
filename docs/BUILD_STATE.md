# Build state

Updated: 2026-08-29 UTC

| Field | State |
|---|---|
| SPARKLE version | 0.6.0-alpha.1 |
| Current phase | Phase 36 — release |
| Current task | Publish and verify the v0.6 API-security increment |
| Completed | v0.3-v0.5 private GitHub releases/CI; model abstraction/registry/MiniMax adapter; orchestrator/context/tracing; memory and knowledge lifecycle with backup; 16 built-in agents; persistent generated-agent installation; bounded workspaces and static verification; executable internal automations; safe tools; text API/CLI/dashboard; optional secret-resolved bearer auth; exact origin/preflight policy; fail-closed network binding; proactive rules; presence interface; 54-test regression suite |
| In progress | v0.6 GitHub publication and Python 3.12/3.13 CI verification |
| Blocked | Live MiniMax call (no key in build process); voice hardware; browser/computer runtime adapters; public deployment target |
| Failed tests | None; latest local `make check` ran 54 tests successfully |
| Next action | Publish v0.6 and verify CI, then design an isolated executable test runner and authenticated remote session UI |
| Estimated directive completion | 55% |

The percentage measures the full long-term directive, not code volume. Agent
specifications are operational through the common orchestrator, and generated
agents, internal automation execution, bounded workspace creation, and static
workspace verification now have runtime evidence. Autonomous code generation
and test/build execution, live
research/browser control, real voice, physical embodiment, service-managed
scheduling, user/role authorization, TLS/rate limiting, and deployment are not
complete.
