# Acceptance status

`PASS` requires implementation plus executed evidence. `PARTIAL` means a useful
implementation exists but the complete requirement is not verified. `BLOCKED`
means an external dependency is unavailable.

| Requirement | Status | Evidence / gap |
|---|---|---|
| Model-independent architecture | PASS | Provider-neutral contracts; deterministic and MiniMax adapters tested |
| MiniMax-M3 adapter works | PARTIAL | HTTP mapping/retry/stream/tool tests pass; live call blocked by absent process key |
| Model registry works | PASS | Validation/list/add/remove/enable/disable/activate tests |
| Model switching works | PASS | Registry activation test; routes remain configurable |
| Separate AI environment | PASS | Dedicated config/provider/registry boundary |
| Separate secrets environment | PASS | Provider/API secret references, presence-only status, redaction and fail-closed tests |
| Separate memory environment | PASS | Independent SQLite CRUD/search/archive/restore/delete/export/backup tests |
| Separate knowledge environment | PASS | Independent source/chunk ingest/search/list/delete/backup tests |
| Separate data environment | PASS | Independent automation, generated-agent, build, verification, and test-run stores |
| Trace environment | PASS | Sequential IDs, redacted execution traces, and separate query-free API audit outcomes/durations tested |
| Core orchestrator | PASS | Single-agent, tool-loop, failure-trace paths implemented and tested |
| Context system | PASS | Memory and knowledge retrieval integrated before calls |
| 16 initial agents | PARTIAL | A domain matrix verifies all 16 capabilities, instructions, minimum tool boundaries, routing, common safety prompts, deterministic execution, and trace linkage; live-provider response-quality evaluations remain incomplete |
| Agent Builder deploys new agents | PARTIAL | Approval-gated manifests persist, hot-load, route, replace, and remove agents; autonomous requirements-to-evaluation generation remains incomplete |
| AI system builder | PARTIAL | Specialist exists; full build/deploy toolchain absent |
| Application builder | PARTIAL | Approval-gated workspaces, static verification, fixed tests, the signed external-worker loop, and deterministic content-addressed ZIP packaging are tested; target-specific build/deployment adapters remain absent |
| External test worker | PARTIAL | Separately installable service, exact validation, replay/concurrency/key controls, fixed executors, local end-to-end execution, Docker/Caddy/systemd assets, and fail-closed preflight are tested; no named remote instance or live namespace isolation evidence exists |
| Tool framework | PASS | Registry, schemas, allowlists, bounds, scaffold, static verifier, and fixed local test tools pass; source-transfer tool is intentionally operator-only and excluded from the agent registry |
| Browser capabilities | BLOCKED | No browser executable/runtime adapter in SPARKLE environment |
| Computer capabilities | PARTIAL | Safe file read exists; GUI/shell control intentionally unavailable |
| Voice works | BLOCKED | Interfaces exist; no microphone/speaker or STT/TTS adapter |
| Text works | PASS | CLI, HTTP API, dashboard, bearer/session auth, CSRF, origin, preflight, rate-limit, and API-audit integration tests |
| Voice/text share context | PARTIAL | Shared architecture exists; voice cannot execute here |
| Automation works | PASS | Due/conditional execution, retry/recurrence/cooldown, expiring claims, crash recovery records, fencing, singleton service, health, real SIGTERM drain, CLI and systemd profile are tested; external notification/calendar/webhook connectors are separate unfinished capabilities |
| Proactive intelligence | PARTIAL | Seven bounded evidence-backed rules now include structured schedule conflicts, strict condition filters/cooldowns, API/dashboard exposure, and free-text non-disclosure; research-change monitoring and notification delivery remain absent |
| Dashboard works | PASS | Local panels plus bounded login/reload/CSRF/logout session lifecycle are integration tested; deployed TLS/reverse-proxy validation remains absent |
| Data tracing works | PASS | Success/tool/failure metadata implemented; trace tests |
| Motion/presence architecture | PASS | Independent presence engine; physical motion intentionally absent |
| Multimodal architecture prepared | PASS | `SPARKLE-CONTENT/1` text/image/audio/document contracts flow through API, context, routing, adapters, results, and raw-content-free traces; mixed and failure paths are tested. Live non-text semantic understanding remains a separate provider capability |
| Tests pass | PASS | 154 local tests pass, including schedule-conflict adversarial/integration coverage; v0.16 CI run #35 passed all four jobs |
| Documentation complete for implementation | PASS | All master-directive documents are present; relative links, version consistency, and required truth fields have executable regression tests |
| Installation reproducible | PASS | Python 3.12 core has zero mandatory third-party dependencies |
| End-to-end workflows | PARTIAL | A cohesive HTTP → context → mixed content → agent/model → trace/presence workflow and worker/automation/application flows pass; live provider and external actions remain blocked |
| Release | PASS | v0.16 capability `d570107`/`ef33e08` is on `main` and passed all four jobs in CI run #35 |
