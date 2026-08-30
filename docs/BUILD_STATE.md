# Build state

Updated: 2026-08-30 UTC

| Field | State |
|---|---|
| SPARKLE version | 0.15.0-alpha.1 |
| Current phase | Phase 32 — Multimodal architecture release verification |
| Current task | Publish the exact locally verified v0.15 tree, then require all four remote CI jobs |
| Completed | v0.3-v0.14 private GitHub releases/CI; model abstraction/registry/MiniMax adapter; orchestrator/context/tracing; memory and knowledge lifecycle with backup; 16 built-in agents; persistent generated-agent installation; bounded workspaces/static verification/fixed local tests; signed external-worker client and deployable worker; reproducible approval-gated application artifacts; supervised automation service; safe tools; text API/CLI/dashboard; bearer/session/CSRF/origin/rate/audit security; six bounded proactive rule types; provider-neutral deterministic text/image/audio/document content contracts with validation, backward-compatible strings, capability routing, API/context/adapter/result flow, raw-content-free trace metadata, fail-closed provider handling, and 138-test local evidence; presence interface |
| In progress | v0.15 exact-tree GitHub publication and four-job CI verification; the non-editable wheel gate passed |
| Blocked | Real Bubblewrap isolation on this executor (namespace setup denied); named remote worker/TLS target and live hostile-code validation; live MiniMax call (no key in build process); semantic non-text provider mapping; voice hardware; browser/computer runtime adapters; public application deployment target |
| Failed tests | None in the current 138-test local suite. Prior corrected failures remain preserved in the release report; v0.15 remote CI has not run yet |
| Next action | Commit and publish the exact verified tree, verify all CI jobs, then inspect the first incomplete Phase 33 requirement |
| Estimated directive completion | 83% |

The percentage measures the full long-term directive, not code volume. Agent
specifications are operational through the common orchestrator. Generated
agents, internal automations, bounded workspace creation/static verification,
the full external-worker protocol/service loop, deterministic artifact
packaging, the supervised automation lifecycle, and six structured proactive
rule types now have runtime evidence.
The provider-neutral multimodal transport phase is implemented and locally
tested. It proves bounded content flow, not semantic understanding by the
currently text-only MiniMax adapter. The reference production executor and
deployment profiles exist, but this host
cannot validate their namespaces and no remote instance is provisioned, so
isolation remains blocked. Autonomous code generation and external deployment
adapters, notification/calendar/webhook delivery, live research/browser
control, real voice, physical embodiment, multi-user role authorization,
TLS/edge rate limiting, and deployment are not
complete.
