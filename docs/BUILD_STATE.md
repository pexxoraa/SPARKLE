# Build state

Updated: 2026-08-29 UTC

| Field | State |
|---|---|
| SPARKLE version | 0.8.0-alpha.1 |
| Current phase | Phase 35 — end-to-end validation |
| Current task | Publish the verified v0.8 capability tree and verify CI |
| Completed | v0.3-v0.7 private GitHub releases/CI; model abstraction/registry/MiniMax adapter; orchestrator/context/tracing; memory and knowledge lifecycle with backup; 16 built-in agents; persistent generated-agent installation; bounded workspaces, static verification, and opt-in fixed Python tests; executable internal automations; safe tools; text API/CLI/dashboard; optional secret-resolved bearer auth; exact origin/preflight policy; fail-closed network binding; bounded API rate limiting; secret-free API audit; proactive rules; presence interface; 68-test regression suite |
| In progress | v0.8 private GitHub publication and Python 3.12/3.13 CI |
| Blocked | Live MiniMax call (no key in build process); hardened workspace filesystem/network isolation (container namespaces denied); voice hardware; browser/computer runtime adapters; public deployment target |
| Failed tests | None; latest local `make check` ran 68 tests successfully |
| Next action | Publish v0.8, then design a hardened external container worker and authenticated remote session UI |
| Estimated directive completion | 62% |

The percentage measures the full long-term directive, not code volume. Agent
specifications are operational through the common orchestrator, and generated
agents, internal automation execution, bounded workspace creation, and static
workspace verification now have runtime evidence. Autonomous code generation
and hardened build/package execution, live
research/browser control, real voice, physical embodiment, service-managed
scheduling, user/role authorization, TLS/edge rate limiting, and deployment are not
complete.
