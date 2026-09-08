# Foundation capability audit — 2026-09-07

Source inspected: `main` at `21c6f5797460650ce352c5e589bceab84a3443e4`,
tree `f09e534de2bdd5fa123cbc010b7e10322caa1ca1`; remote main matched.
The initial worktree was clean. Baseline: **297/297** tests passed freshly.
This report includes the bounded retrieval improvement in this milestone.
Version stays **0.30.0-alpha.1**. No new release boundary is claimed.

## Method and scope

Each of the requested 46 categories has exactly one classification. COMPLETE
AND VERIFIED means the documented bounded local behavior is implemented and
meaningfully exercised; it does not certify every future use or live provider.
Evidence paths below are relative to `src/sparkle/` or `tests/` as appropriate.
Prompt/routing tests do not certify an agent's domain competence. Local protocol
tests do not certify external integration. Priority P1 precedes P2 and P3;
parked/frozen gates are excluded from this milestone.

| Capability | Current State | Evidence | Missing Work | Priority |
|---|---|---|---|---|
| SPARKLE CORE | PARTIALLY IMPLEMENTED | system.py; test_system_e2e.py: real local HTTP, deterministic model | Verified autonomous task completion across live components | P1 |
| Orchestrator | PARTIALLY IMPLEMENTED | orchestrator.py; test_orchestrator_api.py: bounded tool loop, sequential specialists | Independent result quality checks; robust cross-agent task outcomes | P1 |
| Context | PARTIALLY IMPLEMENTED | context.py; test_system_e2e.py: memory/knowledge reach model prompt | Relevance budgets, retrieved-content trust separation, semantic retrieval | P1 |
| Memory | IMPLEMENTED BUT INSUFFICIENTLY VERIFIED | storage.py; test_storage.py: upsert, search, archive; lifecycle methods exist | Broader restore/delete/backup failure and end-to-end memory quality evidence | P1 |
| Knowledge | PARTIALLY IMPLEMENTED | storage.py, knowledge.py; test_knowledge_retrieval.py: migration, Unicode/title ranking, HTTP integration | Semantic/hybrid retrieval, representative relevance benchmark, source revision UX | P1 |
| Model Manager | COMPLETE AND VERIFIED | model.py, registry.py; test_model_registry.py: switching and capability routing | Live provider evidence belongs to provider rows | Maintain |
| Model Registry | COMPLETE AND VERIFIED | registry.py; test_model_registry.py: validation, persistence, switching/rollback | No identified gap in bounded registry contract | Maintain |
| NVIDIA Nemotron provider | IMPLEMENTED BUT INSUFFICIENTLY VERIFIED | providers/nvidia.py; test_nvidia_adapter.py: normalized mocked HTTP, stream/tools/errors | Live authentication, response, stream/tool quality; credentials absent | P1/external |
| MiniMax/secondary providers | IMPLEMENTED BUT INSUFFICIENTLY VERIFIED | providers/minimax.py; test_minimax_adapter.py; retained disabled configuration | Live provider regression; do not replace primary NVIDIA | P3/external |
| Model runtime | COMPLETE AND VERIFIED | model_runtime.py; test_model_runtime.py: health, policy, fallback, retries, missing usage | Real latency/reliability evidence remains provider-specific | Maintain |
| Personal Agent | PARTIALLY IMPLEMENTED | agents.py; test_agent_evaluations.py: routing/prompt/tools, shared orchestrator | Longitudinal personal task quality and verified memory writes | P1 |
| Learning Agent | PARTIALLY IMPLEMENTED | agents.py, mastery.py; test_agent_evaluations.py, test_mastery.py | Demonstrated adaptive teaching and learning outcome evaluation | P2 |
| Skill Agent | PARTIALLY IMPLEMENTED | agents.py, mastery.py; test_mastery.py: evidence-based local levels | Quality of skill assessment and practice recommendations | P2 |
| Exam Agent | PARTIALLY IMPLEMENTED | agents.py; test_agent_evaluations.py: exam routing/instructions | Real grading, calibrated questions, exam outcome evidence | P2 |
| Research Agent | PARTIALLY IMPLEMENTED | agents.py, knowledge.py; test_system_e2e.py: retrieved facts reach prompt | Source discovery, citation/factual verification, semantic quality | P1 |
| Coding Agent | PARTIALLY IMPLEMENTED | agents.py, tooling.py; test_agent_evaluations.py, test_development_verifier.py | Real generated patch correctness across representative tasks | P1 |
| Software Engineering Agent | PARTIALLY IMPLEMENTED | agents.py, development.py; routing and local verifier tests | Repository-level semantic change evaluation and repair quality | P2 |
| Application Builder | PARTIALLY IMPLEMENTED | builders.py; test_builders_agents.py: safe scaffold and artifacts | Functional requirements-to-application generation and user workflows | P2 |
| AI Builder | PARTIALLY IMPLEMENTED | ai_system_*.py; builder/plan/source/runtime tests | Live semantic generation/evaluation; isolated artifact acceptance | P2 |
| Agent Builder | PARTIALLY IMPLEMENTED | agent_builder.py, agent_evaluation.py; test_agent_evaluation.py | Generated agent quality beyond string assertions and registration | P2 |
| Project system | COMPLETE AND VERIFIED | projects.py; test_projects.py: persisted versioned lifecycle, conflicts, events | Task dependencies/execution scheduling are additional unfinished scope | Maintain/P2 |
| Content system | PARTIALLY IMPLEMENTED | content.py, agents.py; test_multimodal.py: safe content envelopes | Content production/editing quality; external publication remains frozen | P2 |
| Data Analysis | PARTIALLY IMPLEMENTED | agents.py, tooling.py: calculator/file read; test_tools_agents.py | Dataset execution, computed statistics/charts and reproducible analysis | P2 |
| Automation | PARTIALLY IMPLEMENTED | automation.py, automation_service.py; runner/service/notification tests | Real external connectors; action outcome quality beyond local delivery | P2 |
| Tools | COMPLETE AND VERIFIED | tooling.py; test_tools_agents.py, builder/artifact tests: allowlists and approvals | New runtime connectors evaluated separately | Maintain |
| Browser capability | CONTRACT/INTERFACE ONLY | interaction.py; test_interaction.py: bounded HTTPS contract and injected harness | Real browser adapter and endpoint/redirect/download safety evidence | P2 |
| Computer interaction | CONTRACT/INTERFACE ONLY | interaction.py; test_interaction.py: typed bounded actions, disabled default | Real GUI runtime, permissions, screenshots and action verification | P3 |
| Voice | CONTRACT/INTERFACE ONLY | voice.py; test_voice_presence.py: STT/TTS doubles, disabled default | Real STT/TTS adapters and microphone/speaker evidence | P3 |
| Multimodal | PARTIALLY IMPLEMENTED | content.py, contracts.py; test_multimodal.py: bounded envelopes, trace metadata | Real non-text provider mapping/understanding and modality quality | P2 |
| Presence/motion | PARTIALLY IMPLEMENTED | presence.py, dashboard; test_voice_presence.py: state and timestamps | Physical motion/perception absent; UI presence is not hardware | P3 |
| Application/build pipeline | PARTIALLY IMPLEMENTED | builders.py, development.py, artifacts.py; artifact/verifier tests | End-to-end generated application quality and isolated acceptance | P2 |
| Controlled promotion | COMPLETE AND VERIFIED | ai_system_promotion.py; test_ai_system_promotion.py: exact identities, replay, tamper, atomicity | No identified gap in bounded promotion contract | Maintain |
| Controlled build | COMPLETE AND VERIFIED | ai_system_build.py; test_ai_system_build.py: approval and immutable deterministic ZIP | No identified gap in bounded build contract | Maintain |
| Controlled execution | PARTIALLY IMPLEMENTED | ai_system_execution.py; test_ai_system_execution.py: authorization/lifecycle; local harness | Level 3 acceptance; synchronous RUNNING remote cancellation not implemented | Park Level 3 |
| External worker | BLOCKED BY EXTERNAL INFRASTRUCTURE | external_worker.py, worker_service.py; protocol/local TLS/HMAC tests | Hardened host and final authenticated approved-artifact acceptance | Park Level 3 |
| Trace/evidence | COMPLETE AND VERIFIED | trace.py; storage, execution, runtime and API tests: identities/redaction/lifecycle | Trace success does not establish semantic correctness | Maintain |
| API | COMPLETE AND VERIFIED | api.py; test_orchestrator_api.py, test_api_security.py, test_system_e2e.py | Supported local endpoints verified; not external integration evidence | Maintain |
| CLI | COMPLETE AND VERIFIED | cli.py; test_cli.py plus builder/artifact CLI tests | Supported CLI contract verified; production operator acceptance separate | Maintain |
| Dashboard | IMPLEMENTED BUT INSUFFICIENTLY VERIFIED | dashboard/*; API tests and node --check | Real browser interaction/accessibility and end-user journey testing | P2 |
| Security | PARTIALLY IMPLEMENTED | security.py, secrets.py, worker boundaries; security/negative tests | Broader threat-model review and actual Level 3 system acceptance | P1/park host |
| Session/rate limiting | COMPLETE AND VERIFIED | security.py; test_api_security.py: CSRF, expiry, revoke, bounded rate state | No identified gap in documented single-process contract | Maintain |
| Testing/evaluation | PARTIALLY IMPLEMENTED | tests/*; agent_evaluation.py: deterministic regressions and negative tests | Semantic benchmarks, live providers, host acceptance, broader platform matrix | P1 |
| Cross-platform architecture | PARTIALLY IMPLEMENTED | stdlib core; Linux worker; .github/workflows/ci.yml: Python 3.12/3.13 Ubuntu | Windows/macOS behavior and execution adapters unverified | P3 |
| Documentation | PARTIALLY IMPLEMENTED | docs/*; test_documentation.py: inventory, links, version contracts | Historical checkpoint claims need interpretation; operator workflows need live evidence | P2 |
| Deployment | BLOCKED BY EXTERNAL INFRASTRUCTURE | docs/ACCEPTANCE.md; explicit freeze and unverified artifact deployment records | Level 3 prerequisites plus separate authorized deployment milestone | Frozen |
| Packaging | COMPLETE AND VERIFIED | pyproject.toml; wheel/offline install and CI worker-image smoke | Cross-platform installation matrix remains separate | Maintain |

## Actual completion estimate

**12/46 = 26.1% fully verified category coverage.** This replaces the unsupported 93% assertion. It is a conservative scope
coverage estimate, **not** a measurement of engineering effort completed.
Categories overlap (for example builders and their pipeline), differ greatly
in size, and have no agreed acceptance weights; an exact remaining-work
percentage cannot honestly be computed from class counts or passing tests.

- COMPLETE AND VERIFIED: 12
- IMPLEMENTED BUT INSUFFICIENTLY VERIFIED: 4
- PARTIALLY IMPLEMENTED: 25
- CONTRACT/INTERFACE ONLY: 3
- MISSING: 0
- BLOCKED BY EXTERNAL INFRASTRUCTURE: 2

## Integrated workflow: what actually works

HTTP request → validated content → context retrieval → orchestrator → routed
model adapter → specialized agent/tool loop → trace → response works with the
local deterministic model. Memory tools persist explicit writes when invoked;
memory is not automatically updated with a verified conclusion on every turn.
Sequential specialist synthesis exists, but is not independently fact-checked.
A successful trace records completion of the program, not truth of its answer.

Broken or simulated links: the model response in CI is a double; domain agent
quality is not established; browser/computer/voice actions have no live runtime;
external connector delivery is absent; independent semantic result verification
is incomplete. Content envelope validation is not multimodal understanding.

## Selected milestone and dependency order

First improve the shared knowledge retrieval path used by context and the
research tool: persisted SQLite FTS5 index, transactional legacy backfill,
Unicode/literal queries, title-aware BM25 ranking, deterministic ties, bounded
results/chunks, and source/chunk identifiers in context. This fixes an observed
full-corpus ASCII/raw-overlap search gap without a model or cloud dependency.
It is **lexical**, not semantic retrieval. No latency benchmark is claimed.

Next highest-value local work is a curated retrieval/agent outcome benchmark
and explicit result-validation integration, then project/task-to-tool workflow
evaluation. Semantic/hybrid retrieval needs an evaluated embedding adapter and
corpus, not a renamed keyword ranker. A browser runtime requires a separate
network/action threat model and executable runtime evidence. Live NVIDIA testing
can run when a real credential arrives; no NVIDIA, generic LLM, or MiniMax key
was present in this executor's environment. No live call was fabricated.

## Parked Level 3 and deployment

**Level 3 = BLOCKED. Deployment = FROZEN.** No Level 3 code or acceptance
workflow changes belong to this milestone. User-supplied Ubuntu host evidence:

- Bubblewrap standalone host execution: verified on that host, not rerun here.
- Seven Bubblewrap isolation canaries: verified on that host, not rerun here.
- Hardened systemd worker compatibility: still requires host-level acceptance.
- Final authenticated external-worker acceptance: not completed.
- Approved immutable artifact acceptance: not completed.

Final acceptance still requires pinned worker identity, matching artifact/result
digests, cleanup, and authenticated `isolation_verified=true`. Passing this
milestone's unit/integration tests changes none of those requirements.
