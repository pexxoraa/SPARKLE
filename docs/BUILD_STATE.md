# Build state

Updated: 2026-09-16 UTC

| Field | State |
|---|---|
| SPARKLE version | 0.30.0-alpha.1 |
| Current phase | Private/local software and installed-runtime acceptance are complete; only explicitly external provider/device acceptance and deferred public deployment remain |
| Current task | Maintain private/local readiness and preserve external/deferred boundaries; production deployment remains frozen. |
| Completed | All ordinary software-completable capability families in `docs/CURRENT_AUDIT.md`: stateful memory/knowledge/projects/learning/content/data/research; persistent semantic-vector indexing; model/orchestrator/agent/tool integration; builders and controlled promotion/build/execution/cancellation; automation reliability and agent inspection; safe HTTPS browser; multimodal image transport; API/CLI/dashboard/status; cross-platform state architecture; host-adapter injection; security/evidence/packaging/documentation |
| Final software verification | Published `32643a826dc394c9a86244fa724932c797fce08a` (tree `11f6e56414b1a3d94bfbaa9b1c133f4f671e8778`); exact-head SPARKLE CI #199 passed all five jobs. Installed package comparison: 89/89 files match, zero missing/mismatched/extra. Fresh exact-head wheel SHA-256 `0307b4530bb576564ac62cfe29930a11d4506d1c9ff044e5edceb89779211ee3`. |
| In progress | No ordinary private/local capability remains in progress. Provider/device live acceptance remains externally blocked; public GitHub-hosted remote acceptance is deferred to a future public-deployment phase. |
| Blocked | External acceptance only: real semantic embedding quality; live NVIDIA/secondary-provider agent quality beyond the preserved 3/12 result; GUI computer adapter/permissions; STT/TTS provider/device; audio/document-capable provider; physical motion hardware; Android/iOS/GrapheneOS embedded host acceptance. Public Level-3 remote acceptance and production deployment are DEFERRED — PUBLIC DEPLOYMENT. Deployment is FROZEN. |
| Failed tests | No current software regression failure remains. Earlier CI/platform failures are retained as historical evidence and were resolved without weakening tests, benchmarks, validators, security or capability definitions. |
| Next action | None for ordinary private/local readiness. When an external provider/device is supplied, run its retained acceptance; public remote Level-3 and production deployment remain deferred until separately authorized. |
| Estimated directive completion | 100% of ordinary software implementation; external/live/manual acceptance intentionally excluded from this percentage. See `CURRENT_AUDIT.md` and `capability_backlog.json`. |

**SOFTWARE IMPLEMENTATION: 100% COMPLETE**

**PRIVATE/LOCAL READINESS: READY — applicable local software/runtime workflows are verified; explicitly listed provider/device semantics remain EXTERNALLY BLOCKED and public deployment remains DEFERRED**

## Completion boundary

`COMPLETE` in the current audit means the repository-side contract is implemented
and integrated. It does not promote unavailable real-model semantic quality, GUI, microphone/speaker,
mobile-host, physical-device, or production-target acceptance. The hardened private/local
worker and browser have separate retained real-host acceptance evidence; unavailable
provider/device dependencies remain `EXTERNALLY BLOCKED`.

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
- **Level 3 private/local:** VERIFIED on the connected hardened Linux worker with localhost-only TLS, binary HMAC, isolation canaries, signed execution/recovery and genuine service restart persistence. Public GitHub-hosted remote acceptance is **DEFERRED — PUBLIC DEPLOYMENT**.
- **Deployment:** obtain explicit authorization and target credentials only after
  applicable acceptance gates; deployment remains frozen.

The green Windows/macOS focused workflow is deterministic repository regression
evidence for the platform software paths only. It does not establish broader live
GUI, browser-network, voice/device, mobile-host or end-user acceptance.

Historical checkpoint percentages and test counts in older release/audit documents
remain historical and must not override this current build-state classification.
