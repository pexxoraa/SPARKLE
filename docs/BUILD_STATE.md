# Build state

Updated: 2026-08-29 UTC

| Field | State |
|---|---|
| SPARKLE version | 0.13.0-alpha.1 |
| Current phase | Phase 28 — Automation release verification |
| Current task | Verify and publish the supervised automation service, expiring claims, recovery/fencing, health lifecycle, and hardened systemd profile |
| Completed | v0.3-v0.12 private GitHub releases/CI; model abstraction/registry/MiniMax adapter; orchestrator/context/tracing; memory and knowledge lifecycle with backup; 16 built-in agents; persistent generated-agent installation; bounded workspaces/static verification/fixed local tests; signed external-worker client and deployable worker; reproducible approval-gated application artifacts; supervised automation entrypoint with no-follow singleton lock, expiring tokenized claims, explicit crash-recovery records, stale-runner fencing, persisted health, SIGTERM draining, real deterministic execution, hardened systemd profile, and non-editable wheel configuration fallback; safe tools; text API/CLI/dashboard; bearer/session/CSRF/origin/rate/audit security; proactive rules; presence interface; 116-test regression suite |
| In progress | v0.13 exact-tree publication and Python/installed-entrypoint CI verification |
| Blocked | Real Bubblewrap isolation on this executor (namespace setup denied); named remote worker/TLS target and live hostile-code validation; live MiniMax call (no key in build process); voice hardware; browser/computer runtime adapters; public application deployment target |
| Failed tests | None locally; corrected release suite runs 116 tests successfully. CI run #26 exposed and recorded the missing wheel configuration; its three other jobs passed, and the fix is awaiting replacement CI evidence |
| Next action | Verify v0.13 remotely, then expand proactive intelligence with evidence-backed weak-learning, overdue-task, and incomplete-project conditions |
| Estimated directive completion | 76% |

The percentage measures the full long-term directive, not code volume. Agent
specifications are operational through the common orchestrator. Generated
agents, internal automations, bounded workspace creation/static verification,
the full external-worker protocol/service loop, and deterministic artifact
packaging, and the supervised automation lifecycle now have runtime evidence.
The reference production executor and deployment profiles exist, but this host
cannot validate their namespaces and no remote instance is provisioned, so
isolation remains blocked. Autonomous code generation and external deployment
adapters, notification/calendar/webhook delivery, live research/browser
control, real voice, physical embodiment, multi-user role authorization,
TLS/edge rate limiting, and deployment are not
complete.
