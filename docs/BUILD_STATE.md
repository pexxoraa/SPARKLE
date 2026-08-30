# Build state

Updated: 2026-08-29 UTC

| Field | State |
|---|---|
| SPARKLE version | 0.14.0-alpha.1 |
| Current phase | Phase 29 — Proactive intelligence |
| Current task | Publish and remotely verify the bounded proactive-evidence release, then resume the next unfinished phase |
| Completed | v0.3-v0.13 private GitHub releases/CI; model abstraction/registry/MiniMax adapter; orchestrator/context/tracing; memory and knowledge lifecycle with backup; 16 built-in agents; persistent generated-agent installation; bounded workspaces/static verification/fixed local tests; signed external-worker client and deployable worker; reproducible approval-gated application artifacts; supervised automation entrypoint with no-follow singleton lock, expiring tokenized claims, explicit crash-recovery records, stale-runner fencing, persisted health, SIGTERM draining, real deterministic execution, hardened systemd profile, corrected non-editable wheel/XDG configuration fallback; safe tools; text API/CLI/dashboard; bearer/session/CSRF/origin/rate/audit security; six bounded proactive rule types with strict metadata evidence, conditional matching/cooldowns, safe API/dashboard exposure, and 120-test local regression evidence; presence interface |
| In progress | v0.14 packaging, private GitHub publication, and all-job CI verification |
| Blocked | Real Bubblewrap isolation on this executor (namespace setup denied); named remote worker/TLS target and live hostile-code validation; live MiniMax call (no key in build process); voice hardware; browser/computer runtime adapters; public application deployment target |
| Failed tests | None in v0.14 local suite; corrected v0.13 CI run #27 passes all four jobs. Prior run #26's wheel failure is preserved in the release report |
| Next action | Publish the exact v0.14 tree, require every GitHub CI job to pass, and record remote evidence |
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
