# Build state

Updated: 2026-09-15 UTC

| Field | State |
|---|---|
| SPARKLE version | 0.30.0-alpha.1 |
| Current phase | Published software baseline is exact-head CI-certified; only remaining external acceptance and documentation reconciliation are in progress |
| Current task | Deployment-surface reconciliation and independent runtime audit. Proven repository defects may be fixed; production deployment remains frozen. |
| Completed | All ordinary software-completable capability families in `docs/CURRENT_AUDIT.md`: stateful memory/knowledge/projects/learning/content/data/research; persistent semantic-vector indexing; model/orchestrator/agent/tool integration; builders and controlled promotion/build/execution/cancellation; automation reliability and agent inspection; safe HTTPS browser; multimodal image transport; API/CLI/dashboard/status; cross-platform state architecture; host-adapter injection; security/evidence/packaging/documentation |
| Final software verification | Published certified baseline `b56693bb759a9d3e136e594635b50fdf64d1ae85` (tree `a6c3e18ecfc423afbd7b4f076b8f4bad7654cd2a`); SPARKLE CI run #193 passed all five jobs. The current private/local worker integration adds localhost-only TLS and binary signing-key file support; its new exact-head verification is pending publication. |
| In progress | Level-3 private/local worker is ready on the connected host, uses localhost-only TLS, and has genuine local systemd restart/recovery evidence. Public GitHub-hosted remote acceptance is deferred to a future public-deployment phase. |
| Blocked | External acceptance only: real semantic embedding quality; live NVIDIA/secondary-provider agent quality beyond the preserved 3/12 result; GUI computer adapter/permissions; STT/TTS provider/device; audio/document-capable provider; physical motion hardware; Android/iOS/GrapheneOS embedded host acceptance. Public Level-3 remote acceptance and production deployment are DEFERRED — PUBLIC DEPLOYMENT. Deployment is FROZEN. |
| Failed tests | No current software regression failure remains. Earlier CI/platform failures are retained as historical evidence and were resolved without weakening tests, benchmarks, validators, security or capability definitions. |
| Next action | Complete private/local publication, exact installed-runtime verification and restart/recovery for the localhost TLS/binary-key integration. Public remote Level-3 acceptance is deferred and does not block private/local readiness. |
| Estimated directive completion | 100% of ordinary software implementation; external/live/manual acceptance intentionally excluded from this percentage. See `CURRENT_AUDIT.md` and `capability_backlog.json`. |

**SOFTWARE IMPLEMENTATION: 100% COMPLETE**

**REAL-WORLD VALIDATION: PARTIAL — browser host accepted; other listed gates remain external**

## Completion boundary

`COMPLETE` in the current audit means the repository-side contract is implemented
and integrated. It does not mean a real model, network, GUI, microphone/speaker,
mobile host, physical device, hardened worker, or production target has been
accepted. Those dependencies are listed as `EXTERNALLY BLOCKED` with exact manual
acceptance requirements.

The software completion gate contains no ordinary `PARTIALLY COMPLETE`,
`INTERFACE ONLY`, or `NOT IMPLEMENTED` capability. This does not change any
runtime verification flag: semantic quality, live computer/voice/motion,
public-remote Level-3 acceptance and production deployment remain deferred until
a future explicitly authorized public-deployment phase. Browser host acceptance is separately recorded
for the exact current browser build and does not imply those other capabilities.

Browser host acceptance is now recorded for the exact current browser build:
all six fixed checks passed, the content-free artifact is mode `0600`, and status
reports the unexpired/unrevoked record separately from current health.

## Current externally blocked acceptance families

- **Real semantic embeddings:** select/configure a real provider/model and evaluate
  retrieval quality before changing `semantic_quality_verified`.
- **Live model/agent quality:** run the unchanged credentialed benchmark and retain
  task-level validator evidence; do not infer competence from deterministic doubles.
- **Computer/voice/motion:** provide concrete host adapters through `SparkleSystem`,
  grant only required OS/device permissions, and perform live acceptance without
  treating adapter presence as verification.
- **Mobile:** provide an embedded Python/application host on Android, iOS and
  GrapheneOS and validate startup/state/network/device integration.
- **Level 3 private/local:** the connected hardened Linux worker is locally ready and isolated; localhost-only TLS, binary HMAC client integration and genuine local service restart/recovery are the private/local acceptance target. Public GitHub-hosted remote acceptance is **DEFERRED — PUBLIC DEPLOYMENT**.
- **Deployment:** obtain explicit authorization and target credentials only after
  applicable acceptance gates; deployment remains frozen.

The green Windows/macOS focused workflow is deterministic repository regression
evidence for the platform software paths only. It does not establish broader live
GUI, browser-network, voice/device, mobile-host or end-user acceptance.

Historical checkpoint percentages and test counts in older release/audit documents
remain historical and must not override this current build-state classification.
