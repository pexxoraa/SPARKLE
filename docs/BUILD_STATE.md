# Build state

Updated: 2026-09-11 UTC

| Field | State |
|---|---|
| SPARKLE version | 0.30.0-alpha.1 |
| Current phase | Software implementation completion gate passed; comprehensive manual/live/host acceptance remains later |
| Current task | Preserve the completed software baseline and execute only regression fixes if final CI exposes a concrete defect; otherwise hand off the external acceptance plan |
| Completed | All ordinary software-completable capability families in `docs/CURRENT_AUDIT.md`: stateful memory/knowledge/projects/learning/content/data/research; persistent semantic-vector indexing; model/orchestrator/agent/tool integration; builders and controlled promotion/build/execution/cancellation; automation reliability and agent inspection; safe HTTPS browser; multimodal image transport; API/CLI/dashboard/status; cross-platform state architecture; host-adapter injection; security/evidence/packaging/documentation |
| In progress | GitHub regression CI for the final documentation/software lineage. CI is supporting evidence only and does not establish semantic/provider/device/production quality. |
| Blocked | External acceptance only: real semantic embedding quality; credentialed NVIDIA/secondary-provider and live-agent quality; live browser host/network acceptance; GUI computer adapter/permissions; STT/TTS provider/device; audio/document-capable provider; physical motion hardware; Android/iOS/GrapheneOS embedded host acceptance; Level 3 hardened Linux worker acceptance; production deployment authorization/target. Level 3 is PARKED and deployment is FROZEN. |
| Failed tests | No failure status is asserted by this document while the final regression run is in progress. Any CI failure must be retained and fixed rather than rerun until green. Historical failures remain historical evidence. |
| Next action | Human operator runs the manual/live/host acceptance plan only after the final software regression gate is green; do not unpark Level 3 or unfreeze deployment implicitly. |
| Estimated directive completion | 100% of ordinary software implementation; external/live/manual acceptance intentionally excluded from this percentage. See `CURRENT_AUDIT.md` and `capability_backlog.json`. |

## Completion boundary

`COMPLETE` in the current audit means the repository-side contract is implemented
and integrated. It does not mean a real model, network, GUI, microphone/speaker,
mobile host, physical device, hardened worker, or production target has been
accepted. Those dependencies are listed as `EXTERNALLY BLOCKED` with exact manual
acceptance requirements.

The software completion gate contains no ordinary `PARTIALLY COMPLETE`,
`INTERFACE ONLY`, or `NOT IMPLEMENTED` capability. This does not change any
runtime verification flag: semantic quality, live browser/computer/voice/motion,
Level-3 isolation and production deployment remain unverified until their separate
acceptance gates pass.

## Current externally blocked acceptance families

- **Real semantic embeddings:** select/configure a real provider/model and evaluate
  retrieval quality before changing `semantic_quality_verified`.
- **Live model/agent quality:** run the unchanged credentialed benchmark and retain
  task-level validator evidence; do not infer competence from deterministic doubles.
- **Browser:** exercise the implemented safe HTTPS runtime on an approved networked
  host and retain DNS/TLS/redirect/output-bound evidence.
- **Computer/voice/motion:** provide concrete host adapters through `SparkleSystem`,
  grant only required OS/device permissions, and perform live acceptance without
  treating adapter presence as verification.
- **Mobile:** provide an embedded Python/application host on Android, iOS and
  GrapheneOS and validate startup/state/network/device integration.
- **Level 3:** provision and accept the hardened Linux external-worker environment,
  signed identity/transport, isolation controls and approved immutable artifact.
- **Deployment:** obtain explicit authorization and target credentials only after
  applicable acceptance gates; deployment remains frozen.

Historical checkpoint percentages and test counts in older release/audit documents
remain historical and must not override this current build-state classification.
