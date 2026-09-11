# SPARKLE current capability audit — 2026-09-11

Software baseline audited: `57e5c3946f7620df30035fc89122a8234e62b4c1`.
This file replaces the historical 2026-09-09 primary inventory. Earlier benchmark
reports remain historical evidence; they are not silently reinterpreted as current
live verification.

## Completion rule

This audit classifies implementation separately from real-world acceptance.
`COMPLETE` means the ordinary software-completable contract is implemented and
integrated in the repository. It does **not** mean semantic quality, provider
availability, hardware behavior, accessibility, production reliability, or live
host acceptance has been established. `EXTERNALLY BLOCKED` is used only where the
software boundary is implemented and the remaining requirement depends on an
external provider, credential, host, device, hardware driver, production target, or
human/live acceptance environment.

Final software-build result: **zero ordinary software-completable capabilities are
PARTIALLY COMPLETE, INTERFACE ONLY, or NOT IMPLEMENTED.** Level 3 remains PARKED.
Deployment remains FROZEN. No live provider/device/production campaign was performed
for this audit.

## Capability classification

| Capability | Status | Current implementation evidence | Remaining external acceptance, if any |
|---|---|---|---|
| SPARKLE core runtime | COMPLETE | `system.py`, persistent environments, status surface, bounded orchestration and integrated subsystems | Live end-user task acceptance is separate |
| Orchestrator | COMPLETE | bounded rounds/calls/specialists, shared budgets, tool allowlists, traces, single/multi-agent routing | Semantic answer quality is covered by live-agent acceptance below |
| Context construction | COMPLETE | bounded attributed memory/knowledge/content handling and modality-aware requests | Real-model relevance/injection-resistance evaluation remains acceptance evidence |
| Memory lifecycle | COMPLETE | scoped durable records, archive/restore/revoke/retention, backups, proposal/review boundary, exact digests | Longitudinal usefulness is acceptance evidence |
| Factual memory validation | COMPLETE | VERIFIED/REJECTED/INCONCLUSIVE evidence pipeline; operator review and atomic approved writes | Open-world truth with unavailable evidence remains correctly INCONCLUSIVE |
| Knowledge lifecycle | COMPLETE | ingest/search/list/delete, archive/restore/revoke/expiry/supersession, revision conflicts, event history | External source credibility remains a research judgment |
| Lexical retrieval | COMPLETE | bounded literal-safe indexed retrieval with source lifecycle filtering | None in bounded software contract |
| Persistent semantic-vector software | COMPLETE | `vector_index.py`, provider identity/dimension binding, input/content digests, normalized finite vectors, batching, stale cleanup, lifecycle revalidation, `SemanticRetriever` synchronization | Quality is intentionally not inferred |
| Real semantic embedding quality | EXTERNALLY BLOCKED | provider-neutral embedding protocol and persistent index are complete; `semantic_quality_verified=false` is preserved | Select/configure a real embedding provider/model, supply credentials/runtime, run retrieval quality evaluation, and retain evidence before changing the flag |
| Model manager and registry | COMPLETE | validated persistent records, activation, routing, health/runtime state | Provider-specific live acceptance is separate |
| Model runtime | COMPLETE | retries, timeouts, fallbacks, error classification, runtime evidence | Host/network reliability is external evidence |
| NVIDIA/Nemotron provider | EXTERNALLY BLOCKED | concrete NIM adapter, tool calls, streaming, diagnostics, image serialization, failure taxonomy | Credentialed unchanged live benchmark/provider regression and retained outcomes are required; current live-agent competence is not verified |
| MiniMax/secondary provider | EXTERNALLY BLOCKED | concrete secondary adapter/configuration path implemented | Credentialed provider regression required when enabled |
| Personal Agent software | COMPLETE | registered specialist, routing, tools, orchestration and trace path | Live longitudinal usefulness belongs to live-agent acceptance |
| Learning Agent software | COMPLETE | specialist integration plus persisted curriculum/progress/practice workflows | Teaching outcome quality belongs to live-agent acceptance |
| Skill Agent software | COMPLETE | evidence-derived mastery store, read tool and specialist integration | Human skill validity/calibration is acceptance evidence |
| Exam Agent software | COMPLETE | persisted practice/timed attempts, grading/error evidence and specialist integration | Real exam outcome calibration is acceptance evidence |
| Research Agent software | COMPLETE | persistent research plans/evidence/claims/reports, exact stored citation integrity, read tool | External web/source discovery and source credibility require available connectors/sources and human/live evaluation |
| Coding Agent software | COMPLETE | repository/file/verifier tools, bounded orchestration and trace integration | Generated patch quality belongs to live-agent acceptance |
| Software Engineering Agent software | COMPLETE | repository engineering inspection/plans, verifier/tool integration | Representative semantic-change quality belongs to live-agent acceptance |
| Application Builder | COMPLETE | bounded source workspace materialization, verification, test, package and artifact records | Generated-application quality and target-host acceptance are external evaluation |
| AI Builder | COMPLETE | blueprint → requirements draft → implementation plan → source candidate → runtime evaluation → promotion → controlled build/execution pipeline | Live model generation quality and Level-3 execution acceptance are external |
| Agent Builder | COMPLETE | persistent blueprints, schema/tool/routing checks, installation and response-evaluation store | Generated-agent semantic quality is live acceptance evidence |
| Project system | COMPLETE | versioned projects, milestones/blockers/events/search/status | None in bounded software contract |
| Project task graph | COMPLETE | persisted task dependencies, readiness, revisions and events | Real task execution remains operator-reported by design |
| Content workflow | COMPLETE | persistent templates/items/versions, transforms, status transitions, exports, CLI, read-only agent tool | External publishing remains frozen/unconfigured |
| Data Analysis | COMPLETE | persisted CSV/JSON datasets, typed inference, deterministic transformations, statistics/grouping/chart specs, recipe digests/history, CLI and read-only model tool | Forecast/causal validity still depends on task-specific data and evaluation |
| Automation engine | COMPLETE | persistent schedules/conditions, leases/recovery, retries, evidence-gated replay, per-attempt records, service state | External notification/connectors require their own provider implementations |
| Automation Agent integration | COMPLETE | read-only `automation_inspect` tool exposes bounded definitions/runs/attempts/service state; mutations remain operator-owned | None in model authority contract |
| Notifications | COMPLETE | bounded persisted dashboard notifications, dedupe/read state, automation integration | Non-dashboard delivery providers are separate external connectors |
| Proactive engine | COMPLETE | bounded evidence-derived deadline/project/learning/research/schedule alerts | Rule usefulness is acceptance evidence |
| Tool registry/discovery/permissions | COMPLETE | definitions, execution, unknown-tool rejection, per-agent allowlists and generated-agent validation | External connector tools depend on connector availability |
| Browser software runtime | COMPLETE | concrete read-only safe HTTPS adapter, public-DNS policy, pinned TLS, redirect revalidation, response bounds, persistent operator sessions, CLI, `SparkleSystem` default integration | Live host/network behavior still needs manual acceptance; `live_browser_verified=false` |
| Live browser host acceptance | EXTERNALLY BLOCKED | software runtime complete | On an approved host, exercise public allowlisted destinations, DNS rebinding/private-address rejection, TLS hostname validation, redirects and body limits; retain evidence |
| Computer interaction | EXTERNALLY BLOCKED | typed bounded actions, persistent permission sessions, optimistic revisions, host-adapter injection through `SparkleSystem` | Supply a concrete `ComputerAdapter`, OS GUI/display permissions and live screenshot/click/type/key acceptance |
| Voice | EXTERNALLY BLOCKED | bounded persistent voice sessions/events, STT/TTS interfaces, CLI, host-adapter injection through `SparkleSystem` | Supply concrete STT/TTS provider/device adapters plus microphone/speaker/provider permissions; perform live transcript/synthesis acceptance |
| Multimodal content protocol and image transport | COMPLETE | bounded text/image/audio/document envelopes; modality-aware routing; NVIDIA OpenAI-compatible image payload serialization; configured model records still gate modalities | Live image understanding requires an explicitly image-capable configured model and provider acceptance |
| Audio/document model understanding | EXTERNALLY BLOCKED | envelopes/routing fail closed instead of flattening unsupported binary content | Configure a model/provider adapter that explicitly supports audio/document modalities and run live modality acceptance |
| Presence state | COMPLETE | durable presence state/history integrated with runtime transitions and health/status | UI/human perception acceptance is separate |
| Physical motion | EXTERNALLY BLOCKED | bounded command/result contract, explicit approval, capability checks, persisted events, host-adapter injection | Supply hardware-specific `MotionAdapter`, transport/permissions/device and approved-command acceptance |
| Application/build pipeline | COMPLETE | workspace scaffold, static verifier, bounded tests, package artifacts, immutable controlled build path | External target execution is handled by worker/deployment gates |
| Controlled promotion | COMPLETE | identities/digests, approvals, replay/tamper/concurrency defenses, exclusions and atomic records | None in bounded promotion contract |
| Controlled build | COMPLETE | approval-bound immutable deterministic artifacts and evidence | None in bounded build contract |
| Controlled execution and cancellation | COMPLETE | authorization, execution lifecycle, results, worker cancellation protocol and API/CLI cancellation | Level-3 worker acceptance remains external |
| External worker / Level 3 | EXTERNALLY BLOCKED | signed worker protocol, client/service, identities, bounds, cancellation and evidence paths implemented | Provision hardened Linux worker host, TLS/HMAC secrets, approved worker identity, isolation controls, then run the documented approved-artifact acceptance. Level 3 stays PARKED until it passes |
| Trace/evidence | COMPLETE | persistent content-minimized traces, model/tool identities, redaction and lifecycle evidence | Trace success never implies semantic correctness |
| API | COMPLETE | authenticated/rate-limited local JSON API covering core operator workflows; newer specialist state is exposed through `/api/health` and dedicated CLIs/tools where a duplicate mutation API would add no capability | External service integrations are separate connectors |
| CLI | COMPLETE | core CLI plus data/content/research/engineering/interaction/voice/worker/automation commands and controlled-build/execution operations | Host/provider commands still need their external runtime |
| Dashboard | COMPLETE | session-authenticated status, memory review, projects/tasks, learning, automation/notification/proactive evidence, builders/releases; `/api/health` includes vectors/data/content/research/browser/voice/platform state | Real browser accessibility/end-user journey acceptance remains manual evidence |
| Security boundaries | COMPLETE | secrets indirection, API auth/origin/CSRF/session/rate limits, path bounds, tool permissions, worker signing, browser SSRF controls, explicit approvals | Broader independent threat review and real host hardening are acceptance activities |
| Session/rate limiting | COMPLETE | bounded fixed-window rate state and authenticated session/CSRF lifecycle | Multi-process/distributed deployment would require a different backend contract |
| Testing/evaluation framework | COMPLETE | deterministic unit/integration suites, benchmark protocol/validators, runtime evidence and focused platform workflow | Live-provider/device/host acceptance is intentionally deferred |
| Live agent semantic quality | EXTERNALLY BLOCKED | unchanged benchmark/evaluation machinery is implemented; benchmarks were not weakened | Run the unchanged credentialed live campaign and retain per-task evidence. Existing historical 3/12 validated baseline is not upgraded by software implementation |
| Linux core platform software | COMPLETE | native state path, stdlib runtime and Linux worker software | Host acceptance remains separate |
| Windows core platform software | COMPLETE | native state path and focused Windows smoke workflow definition | Real Windows host acceptance/CI evidence must be observed separately |
| macOS core platform software | COMPLETE | native state path and focused macOS smoke workflow definition | Real macOS host acceptance/CI evidence must be observed separately |
| Android/iOS/GrapheneOS host runtime | EXTERNALLY BLOCKED | mobile platform classification/state-layout and external-adapter architecture implemented | Provide an embedded Python/app host with storage/network/device permissions and run platform-specific install/state/API/browser/voice acceptance |
| Documentation | COMPLETE | current architecture/workflow docs plus this reconciled audit/backlog; historical reports remain explicitly historical | Operator acceptance evidence will be added after the later campaign |
| Packaging | COMPLETE | `pyproject.toml`, package data and entry points cover implemented runtime/CLI assets | Platform installation acceptance remains external evidence |
| Production deployment | EXTERNALLY BLOCKED | controlled artifacts/execution records exist; software does not silently deploy | Requires explicit user authorization, target credentials/environment, applicable Level-3 prerequisites, and a separate production acceptance milestone. Deployment remains FROZEN |

## API/dashboard exposure decision

The audit intentionally does not add redundant write endpoints for every stateful
service. Data Analysis, Content, Research, Interaction and Voice have dedicated
operator CLIs; Data Analysis/Content/Research also have bounded agent read tools;
Browser has operator-owned revisioned sessions; vector/platform/voice/browser/data/
content/research states are included in `SparkleSystem.status()` and therefore
`GET /api/health`. Automation and controlled execution already have dedicated API
and dashboard surfaces, including execution cancellation. This is deliberate least-
authority architecture rather than missing exposure.

## Cross-platform decision

Core state/configuration software supports Linux, Windows and macOS native layouts.
Android, iOS and GrapheneOS have explicit platform classifications and state layouts,
but require an external embedded-Python/application host. The hardened external
worker remains Linux-only by design and is not represented as a native mobile or
Windows/macOS worker capability.

## Verification state for this completion audit

Implementation inspection and focused deterministic test additions were used while
building. No new live Nemotron, semantic-embedding, microphone, speaker, GUI,
physical-hardware, mobile-host, Level-3 worker or production-deployment acceptance
was performed here. GitHub CI runs triggered by the final implementation commits are
supporting regression evidence only and do not change the external classifications.

**Software completion gate: PASS — no ordinary software-completable capability remains
PARTIALLY COMPLETE, INTERFACE ONLY, or NOT IMPLEMENTED.**

**Level 3: PARKED. Deployment: FROZEN.**
