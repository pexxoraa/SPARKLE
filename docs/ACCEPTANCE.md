# Acceptance status

Updated 2026-09-15. `CURRENT_AUDIT.md` and `LEVEL3_STATUS.md` are the
authoritative current ledgers; historical release evidence below is retained
without being promoted into a current external acceptance claim.

`PASS` requires implementation plus executed evidence. `PARTIAL` means a useful
implementation exists but the complete requirement is not verified. `BLOCKED`
means an external dependency is unavailable.

| Requirement | Status | Evidence / gap |
|---|---|---|
| Model-independent architecture | PASS | Provider-neutral contracts, external factories, exact identities, NVIDIA/MiniMax adapters, and deterministic provider switching are tested |
| NVIDIA Nemotron primary adapter | PARTIAL | Exact `nvidia/nemotron-3.5-lightning-30b-a3b` mapping, auth, retry, stream, tools, usage, errors, registry default, API/CLI/dashboard, and local doubles pass. Three preserved real campaigns completed provider traffic successfully but only 3/12 tasks validated; no post-fix live campaign exists and competence remains false |
| Model health, request policy, and usage | PASS | Configuration alone is never healthy; capability/modality/tool/stream/health/latency/timeout/fallback policy and content-free evidence are tested; absent usage remains unknown |
| MiniMax-M3 adapter retained | PASS | Legacy HTTP mapping/retry/stream/tool tests pass; record is disabled rather than deleted |
| Model registry works | PASS | Validation/list/add/remove/enable/disable/activate tests |
| Model switching works | PASS | Registry activation test; routes remain configurable |
| Separate AI environment | PASS | Dedicated config/provider/registry boundary |
| Separate secrets environment | PASS | Provider/API secret references, presence-only status, redaction and fail-closed tests |
| Separate memory environment | PASS | Independent SQLite CRUD/search/archive/restore/delete/export/backup tests |
| Separate knowledge environment | PASS | Independent source/chunk ingest/search/list/delete/backup tests |
| Separate data environment | PASS | Independent automation, generated-agent, AI-system Blueprint/draft/implementation-plan/candidate/runtime/promotion/controlled-build, structured-project, build, verification, and test-run stores |
| Trace environment | PASS | Sequential IDs, redacted execution traces, and separate query-free API audit outcomes/durations tested |
| Core orchestrator | PASS | Single-agent, tool-loop, failure-trace paths implemented and tested |
| Context system | PASS | Memory and knowledge retrieval integrated before calls |
| 16 initial agents | PARTIAL | A domain matrix verifies all 16 capabilities, instructions, minimum tool boundaries, routing, common safety prompts, deterministic execution, and trace linkage; live-provider response-quality evaluations remain incomplete |
| Agent Builder deploys new agents | PARTIAL | Blueprint generation/static routing plus approval-gated `SPARKLE-AGENT-EVALUATION/1` execute isolated no-context/no-tool response contracts, persist content-free bounded evidence, and fail closed on drift/tool calls. Natural-language source generation, semantic correctness evaluation, live-provider verification, and external deployment remain incomplete |
| AI system builder | PARTIAL | Blueprint through controlled build remains intact. v0.30 adds separate authorization, exact signed policy, legal lifecycle transitions, pinned worker identity, and controlled execution of the immutable artifact with result verification and no deployment implication. Local Level 2 passes and the real loopback Bubblewrap worker is ready; trusted remote/full-chain/restart acceptance and deployment remain incomplete |
| Project Agent | PARTIAL | `SPARKLE-PROJECT/1` provides strict structured lifecycle/priority/deadline/dependency/risk/milestone/blocker/next-action/progress state, optimistic updates, approval-gated archive, content-free change evidence, proactive integration, API/CLI/dashboard, and least-privilege reads for Personal/Project/Productivity agents. Live-provider decision quality and external project/calendar connectors remain incomplete |
| Skill mastery system | PARTIAL | `SPARKLE-SKILL/1` transactionally derives levels 0–6 only from bounded verified question/exercise/test/project/implementation/independent-problem-solving evidence, rejects duplicates/future evidence, exposes content-free Personal/Learning/Skill reads, and integrates API/CLI/dashboard/proactive automation. Local regression and packaging pass; independent artifact authentication, external learning platforms, and live-provider teaching quality remain unverified |
| Application builder | PARTIAL | Approval-gated workspaces, static verification, fixed tests, the signed external-worker loop, and deterministic content-addressed ZIP packaging are tested; target-specific build/deployment adapters remain absent |
| External test worker | PARTIAL | The separately installed `prem-macharla` systemd worker is locally ready with Bubblewrap preflight, filesystem/network isolation, and seven structured canaries true. Trusted HTTPS ingress, protected GitHub Environment, remote/lifecycle/full-chain artifacts, and genuine restart/rerun evidence do not yet exist |
| Tool framework | PASS | Registry, schemas, allowlists, bounds, scaffold, static verifier, and fixed local test tools pass; source-transfer tool is intentionally operator-only and excluded from the agent registry |
| Browser capabilities | PASS | Concrete safe HTTPS adapter plus fixed host checkset passed public HTTPS, non-public rejection, TLS failure, redirect revalidation, output bounds, and persistent session lifecycle on `prem-macharla`; owner-only evidence is exact-build and one-way host-identity bound, expiring, and revocable |
| Computer capabilities | PARTIAL | Typed bounded screenshot/click/text/key contracts and fail-closed/test-harness adapters are tested; live GUI control is unavailable and shell control is intentionally absent |
| Voice works | BLOCKED | Interfaces exist; no microphone/speaker or STT/TTS adapter |
| Text works | PASS | CLI, HTTP API, dashboard, bearer/session auth, CSRF, origin, preflight, rate-limit, and API-audit integration tests |
| Voice/text share context | PARTIAL | Shared architecture exists; voice cannot execute here |
| Automation works | PASS | Due/conditional execution, retry/recurrence/cooldown, expiring claims, crash recovery, fencing, supervision, and bounded dashboard-notification actions are tested; external email/SMS/push/calendar/webhook connectors remain unfinished |
| Proactive intelligence | PARTIAL | Eight bounded evidence-backed rules include structured schedule conflicts, explicit knowledge-revision change detection, and direct validated project-state/deadline evidence; conditions can deliver content-safe traced dashboard notifications, while external research polling and external notification channels remain absent |
| Dashboard works | PASS | Local panels plus bounded login/reload/CSRF/logout session lifecycle are integration tested; deployed TLS/reverse-proxy validation remains absent |
| Data tracing works | PASS | Success/tool/failure metadata implemented; trace tests |
| Motion/presence architecture | PASS | Independent presence engine; physical motion intentionally absent |
| Multimodal architecture prepared | PASS | `SPARKLE-CONTENT/1` text/image/audio/document contracts flow through API, context, routing, adapters, results, and raw-content-free traces; mixed and failure paths are tested. Live non-text semantic understanding remains a separate provider capability |
| Tests pass | PASS | Current audit candidate passes compileall, 546 full tests with 1 explicit live-provider skip and 0 failures, the focused 85-test Level-3 gate, deterministic benchmark reproduction, probe compilation, shell syntax, and dashboard JavaScript syntax; exact-head CI remains pending |
| Documentation complete for implementation | PASS | All master-directive documents are present; relative links, version consistency, and required truth fields have executable regression tests |
| Installation reproducible | PASS | A fresh no-index `0.30.0a1` wheel installed without dependencies and passed version/status plus fail-closed live Nemotron and interaction checks. SHA-256 `b3f7f94fc9e73afb90828e5239780b6287af17b8469ade1e06392620e3fe817c` |
| End-to-end workflows | PARTIAL | A cohesive HTTP → context → mixed content → agent/model → trace/presence workflow and worker/automation/application flows pass; live provider and external actions remain blocked |
| Release | PARTIAL | Last published certified baseline `6d59b45b0a91f56b8932c2a1822f0781a926701a` passed SPARKLE CI #182. Current audit fixes are locally green but not yet exact-head published/CI-certified. Live Nemotron competence is 3/12; Level 3 is locally ready but remotely incomplete; deployment remains frozen |
