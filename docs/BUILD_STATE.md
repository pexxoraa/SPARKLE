# Build state

Updated: 2026-08-29 UTC

| Field | State |
|---|---|
| SPARKLE version | 0.9.0-alpha.1 |
| Current phase | Phase 35 — end-to-end validation |
| Current task | Verify and publish the v0.9 authenticated dashboard-session increment |
| Completed | v0.3-v0.8 private GitHub releases/CI; model abstraction/registry/MiniMax adapter; orchestrator/context/tracing; memory and knowledge lifecycle with backup; 16 built-in agents; persistent generated-agent installation; bounded workspaces, static verification, and opt-in fixed Python tests; executable internal automations; safe tools; text API/CLI/dashboard; secret-resolved bearer auth; bounded process-local dashboard sessions with CSRF and revocation; exact origin/preflight policy; fail-closed network/session binding; bounded API rate limiting; secret-free API audit; proactive rules; presence interface; 72-test regression suite |
| In progress | v0.9 final local verification, private GitHub publication, and Python 3.12/3.13 CI |
| Blocked | Live MiniMax call (no key in build process); hardened workspace filesystem/network isolation (container namespaces denied); deployed TLS/reverse-proxy validation; voice hardware; browser/computer runtime adapters; public deployment target |
| Failed tests | None; latest local `make check` ran 72 tests successfully |
| Next action | Publish v0.9, then design a hardened external container worker and deployment adapter |
| Estimated directive completion | 65% |

The percentage measures the full long-term directive, not code volume. Agent
specifications are operational through the common orchestrator, and generated
agents, internal automation execution, bounded workspace creation, and static
workspace verification now have runtime evidence. Autonomous code generation
and hardened build/package execution, live
research/browser control, real voice, physical embodiment, service-managed
scheduling, multi-user role authorization, TLS/edge rate limiting, and deployment are not
complete.
