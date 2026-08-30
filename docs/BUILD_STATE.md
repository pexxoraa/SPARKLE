# Build state

Updated: 2026-08-30 UTC

| Field | State |
|---|---|
| SPARKLE version | 0.14.0-alpha.1 |
| Current phase | Phase 32 — Multimodal architecture |
| Current task | Implement provider-neutral multimodal input contracts and preserve text compatibility |
| Completed | v0.3-v0.14 private GitHub releases/CI; model abstraction/registry/MiniMax adapter; orchestrator/context/tracing; memory and knowledge lifecycle with backup; 16 built-in agents; persistent generated-agent installation; bounded workspaces/static verification/fixed local tests; signed external-worker client and deployable worker; reproducible approval-gated application artifacts; supervised automation entrypoint with no-follow singleton lock, expiring tokenized claims, explicit crash-recovery records, stale-runner fencing, persisted health, SIGTERM draining, real deterministic execution, hardened systemd profile, corrected non-editable wheel/XDG configuration fallback; safe tools; text API/CLI/dashboard; bearer/session/CSRF/origin/rate/audit security; six bounded proactive rule types with strict metadata evidence, conditional matching/cooldowns, safe API/dashboard exposure, and 120-test local/CI regression evidence; presence interface |
| In progress | Phase 32 multimodal request/content contracts; implementation awaits an available development executor |
| Blocked | Development execution environment currently unavailable; real Bubblewrap isolation on this executor (namespace setup denied); named remote worker/TLS target and live hostile-code validation; live MiniMax call (no key in build process); voice hardware; browser/computer runtime adapters; public application deployment target |
| Failed tests | None in v0.14 local suite or CI run #29; Python 3.12/3.13, worker-image, and installed automation-service jobs all pass. Prior run #26's corrected wheel failure remains preserved in the release report |
| Next action | Restore an execution environment, sync remote main, then implement and test bounded image/audio/document content contracts |
| Estimated directive completion | 79% |

The percentage measures the full long-term directive, not code volume. Agent
specifications are operational through the common orchestrator. Generated
agents, internal automations, bounded workspace creation/static verification,
the full external-worker protocol/service loop, deterministic artifact
packaging, the supervised automation lifecycle, and six structured proactive
rule types now have runtime evidence.
The reference production executor and deployment profiles exist, but this host
cannot validate their namespaces and no remote instance is provisioned, so
isolation remains blocked. Autonomous code generation and external deployment
adapters, notification/calendar/webhook delivery, live research/browser
control, real voice, physical embodiment, multi-user role authorization,
TLS/edge rate limiting, and deployment are not
complete.
