# Build state

Updated: 2026-08-29 UTC

| Field | State |
|---|---|
| SPARKLE version | 0.12.0-alpha.1 |
| Current phase | Phase 28 — Automation |
| Current task | Package the existing automation runner as a supervised long-running service with lease recovery, health, bounded shutdown, and deployment profiles |
| Completed | v0.3-v0.12 private GitHub releases/CI; model abstraction/registry/MiniMax adapter; orchestrator/context/tracing; memory and knowledge lifecycle with backup; 16 built-in agents; persistent generated-agent installation; bounded workspaces/static verification/fixed local tests; signed external-worker client; separately installable server with strict validation, replay protection, concurrency bounds, key-file hardening, fixed executors, fail-closed Bubblewrap preflight, container/TLS and systemd deployment profiles; reproducible approval-gated ZIP artifacts with manifests and tamper refusal; append-only unverified deployment records; executable internal automations; safe tools; text API/CLI/dashboard; bearer/session/CSRF/origin/rate/audit security; proactive rules; presence interface; 104-test regression suite |
| In progress | Supervised automation-service lifecycle and recovery implementation |
| Blocked | Real Bubblewrap isolation on this executor (namespace setup denied); named remote worker/TLS target and live hostile-code validation; live MiniMax call (no key in build process); voice hardware; browser/computer runtime adapters; public application deployment target |
| Failed tests | None; latest corrected local `make check` ran 104 tests successfully |
| Next action | Implement service status/health, stale-claim recovery, graceful shutdown, single-instance locking, and systemd/container deployment assets |
| Estimated directive completion | 73% |

The percentage measures the full long-term directive, not code volume. Agent
specifications are operational through the common orchestrator. Generated
agents, internal automations, bounded workspace creation/static verification,
the full external-worker protocol/service loop, and deterministic artifact
packaging now have runtime evidence.
The reference production executor and deployment profiles exist, but this host
cannot validate their namespaces and no remote instance is provisioned, so
isolation remains blocked. Autonomous code generation and external deployment
adapters, live
research/browser control, real voice, physical embodiment, service-managed
scheduling, multi-user role authorization, TLS/edge rate limiting, and deployment are not
complete.
