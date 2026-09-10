# Current capability inventory — 2026-09-09

Inspected starting main: `73d2362ec9f3361bdec15f9ffbbcf402e77f4d27`;
remote matched after fetch/fast-forward pull and worktree was clean. Repository-wide
inventory covers 54 Python source modules, 47 Python test files and 37 documentation
files before this milestone. Focused behavioral review followed the benchmark,
system initialization, routing, NVIDIA adapter, HTTP transport, storage and evidence
paths. This is an evidence inventory, not a claim of exhaustive line-by-line security
certification. Full baseline: 364 passed, one optional live test skipped (365 total).
Fresh wheel build and offline installation passed. Deterministic reports reproduced.

Evidence classes below apply to bounded implemented contracts. No category is
upgraded from a class name, mock response, or user-reported connectivity alone.
A current-source/test reference is local evidence; live integration is stated
separately. Existing agent and builder quality limitations remain open.

| Capability | Status | Current implementation / test evidence | Missing components / dependencies | Priority |
|---|---|---|---|---|
| SPARKLE CORE | PARTIALLY IMPLEMENTED | system.py; test_system_e2e.py: real local HTTP, deterministic model | Verified autonomous task completion across live components | P1 |
| Orchestrator | PARTIALLY IMPLEMENTED | orchestrator.py; bounded tool loop, test_benchmarks.py independent outcome checks | Independent validator is benchmark-only; no automatic factual verification of chat or specialist synthesis | P1 |
| Context | PARTIALLY IMPLEMENTED | context.py; test_benchmarks.py, test_system_e2e.py: bounded attributed untrusted user-role data | Live model prompt-injection resistance and context relevance on real user tasks | P1 |
| Memory | IMPLEMENTED BUT INSUFFICIENTLY VERIFIED | storage.py; test_storage.py, test_storage_resources.py: scoped lifecycle/backup/rollback and explicit tool writes | Longitudinal quality and general factual validation; exact attestation, retention and operator review now tested | P1 |
| Knowledge | PARTIALLY IMPLEMENTED | storage.py, retrieval.py; 16-query benchmark and test_knowledge_retrieval.py | Real embedding evaluation, vector persistence, source revision workflows | P1 |
| Model Manager | COMPLETE AND VERIFIED | model.py, registry.py; test_model_registry.py: switching and capability routing | Live provider evidence belongs to provider rows | Maintain |
| Model Registry | COMPLETE AND VERIFIED | registry.py; test_model_registry.py: validation, persistence, switching/rollback | No identified gap in bounded registry contract | Maintain |
| NVIDIA Nemotron provider | IMPLEMENTED BUT INSUFFICIENTLY VERIFIED | nvidia.py; adapter/runtime/deadline tests; user-reported authenticated smoke success | Explain nine rejected live outcomes; broader live streaming/tool evidence | P1/external |
| MiniMax/secondary providers | IMPLEMENTED BUT INSUFFICIENTLY VERIFIED | providers/minimax.py; test_minimax_adapter.py; retained disabled configuration | Live provider regression; do not replace primary NVIDIA | P3/external |
| Model runtime | COMPLETE AND VERIFIED | model_runtime.py; policy/fallback tests, hard HTTP lifecycle tests, pre-request error classification | Host reliability evidence; routing timeout is a per-attempt policy, not a whole-benchmark deadline | Maintain |
| Personal Agent | PARTIALLY IMPLEMENTED | agents.py; test_agent_evaluations.py: routing/prompt/tools, shared orchestrator | Longitudinal personal task quality and verified memory writes | P1 |
| Learning Agent | PARTIALLY IMPLEMENTED | agents.py, mastery.py; test_agent_evaluations.py, test_mastery.py | Demonstrated adaptive teaching and learning outcome evaluation | P2 |
| Skill Agent | PARTIALLY IMPLEMENTED | agents.py, mastery.py; test_mastery.py: evidence-based local levels | Quality of skill assessment and practice recommendations | P2 |
| Exam Agent | PARTIALLY IMPLEMENTED | agents.py; test_agent_evaluations.py: exam routing/instructions | Real grading, calibrated questions, exam outcome evidence | P2 |
| Research Agent | PARTIALLY IMPLEMENTED | agents.py, knowledge.py; test_system_e2e.py: retrieved facts reach prompt | Source discovery, factual/semantic verification; stored citation identity checks now tested | P1 |
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
| Testing/evaluation | PARTIALLY IMPLEMENTED | benchmarks/*; 16 retrieval queries, 12 scripted tasks, deterministic independent validators | Real provider outcomes, real embedding quality, broader representative tasks | P1 |
| Cross-platform architecture | PARTIALLY IMPLEMENTED | stdlib core; Linux worker; .github/workflows/ci.yml: Python 3.12/3.13 Ubuntu | Windows/macOS behavior and execution adapters unverified | P3 |
| Documentation | PARTIALLY IMPLEMENTED | docs/* inventory; test_documentation.py; this refreshed audit and benchmark procedure | Historical reports remain historical; external operator evidence still missing | P2 |
| Deployment | BLOCKED BY EXTERNAL INFRASTRUCTURE | docs/ACCEPTANCE.md; explicit freeze and unverified artifact deployment records | Level 3 prerequisites plus separate authorized deployment milestone | Frozen |
| Packaging | COMPLETE AND VERIFIED | pyproject.toml; wheel/offline install and CI worker-image smoke | Cross-platform installation matrix remains separate | Maintain |

## Measured baseline and limits

Lexical Recall@1 = 0.625; Recall@3/5 = 0.75; MRR = 0.71875.
The semantic and hybrid paths use token-hashing test doubles, not trained embeddings.
All 12 scripted workflow outcomes validate; this is not live agent-quality evidence.
No NVIDIA credential is available in this executor. Host smoke connectivity is
user-reported verified. The current user-supplied credential-safe live baseline is
12 real Nemotron tasks executed, 3 validated and 9 rejected: 25% validated. This
supersedes the historical 8.33% run. It does not verify agent competence; no new live
run was performed here, and individual rejection diagnosis requires retained evidence.
No real semantic, multimodal, browser, desktop, voice or connector acceptance was
performed here. There is no defensible aggregate percentage of engineering completion:
these overlapping categories have neither equal size nor agreed acceptance weights.

## Dependency order and the current reliability milestone

P0: pre-request errors must not masquerade as HTTP provider outages. Missing NVIDIA
credentials now have configuration_failure; no eligible model has routing_failure.
The live runner preserves incremental content-free task/runtime evidence using
normal registry construction, including after interrupt/setup failure. It never
changes task definitions, validators, scoring, configured model or retry policy.
The original host provider_provider_failure cause is not proven by this code review.

P1: run the unchanged live benchmark on the credentialed host with the corrected
resource lifecycle and new evidence output. Use independent outcome validation;
retain failures and inconclusive cases. Then prioritize validated memory updates and
specialist synthesis against explicit trusted criteria; do not auto-persist model
claims. Real embedding evaluation requires a separately selected embedding model.

P2: project/task dependency workflows and representative generated-code validation
precede broader browser/connector expansion. Browser/GUI requires a runtime and
network/action threat model; interface doubles are insufficient. P3 voice/hardware
and OS-specific adapters remain external/runtime-dependent.

Level 3 remains BLOCKED/PARKED. Deployment remains FROZEN. No acceptance gate or
worker configuration is changed. The earlier foundation audit is historical; use
this inventory and newly recorded test evidence for this milestone.

## Fresh milestone verification

374 passed, one optional live skip (375 total); focused suite 44/44.
Wheel/offline install and tracked-tree audits passed. No live provider run.

## Response-protocol investigation

The final JSON-object requirement was implicit for ten of twelve task prompts.
The common response contract is now explicit/versioned; strict parsing and
independent validators remain in force. Structural metadata and criterion results
are exported without response text. The unchanged scripted baseline still validates
12/12. Historical response shapes and the rejected task cannot be recovered from
aggregate counts. No capability classification, Level 3, or deployment gate changes.

## Bounded workflow update

Shared tool-attempt and specialist-count limits are locally verified; orchestrator
remains PARTIALLY IMPLEMENTED. Aggregate wall-time policy, idempotent actions and
validated staged memory remain open. See [continuous backlog](capability_backlog.json).
Final regression: 394 passed, one optional live skip. No live or host upgrade.

## Memory query correction

An ASCII-only tokenization fallback returned unrelated recent memory for Japanese
and punctuation-only queries. Literal Unicode tokens, a 64-term bound and an empty
result for nonempty unsearchable queries correct that observed relevance defect.
Underscores no longer act as wildcards. Memory remains IMPLEMENTED BUT INSUFFICIENTLY
VERIFIED; this does not establish semantic retrieval or validated memory updates.

## Operator-reviewed memory boundary

Default system agent memory writes now stage proposals outside retrieval. An operator
reviews exact content and digest through CLI/API; expiry, replay, content tampering
and concurrent memory changes fail closed. Approval and memory update are atomic.
This is independent operator authorization, not automated factual validation.
The 46-capability inventory remains conservative: memory retention, deduplication,
trusted machine-verifiable criteria, and longitudinal quality remain unfinished.
The unchanged 12-task benchmark explicitly installs the legacy direct-write fixture
tool. Its metrics remain comparable but do not exercise this new default boundary.

## 2026-09-10 memory review UI verification

Continued from retention commit `9a08991d8f2f21365f3cb7ded0a4edace5d08b0d`,
tree `de55cbf934902e6ef4b090812c2779b82b5ffbd7`; CI #94 passed all five
jobs on that exact commit. Pending proposals now expose current exact-field
verification, evidence, digest, expiry and conflicts to the operator dashboard.
Approval defaults to requiring VERIFIED evidence; authoritative server checks
remain atomic and independent of the displayed state. Review/validation audit
and private memory version history are separate from the pending queue.

Fresh full suite: **436 total, 435 passed, 1 skipped, 0 failures/errors**
(63.238 seconds). Focused memory/UI/API/CLI integration: **49/49** (5.255s).
The UI wrapper includes **10/10** deterministic Node DOM interaction tests.
The baseline was 433 total, 432 passed, 1 skipped. Node syntax, whitespace,
wheel build, offline installation and installed CLI help passed; the wheel
contains the new dashboard asset. This is software/UI-contract evidence, not
live-browser accessibility, generalized factual correctness or live-agent
quality evidence. Live-agent baseline remains user-reported **3/12 (25%)**.
Level 3 stays **BLOCKED/PARKED**; deployment stays **FROZEN**.

## 2026-09-10 stored research citation integrity

Continued from `2955238a3cda0f57973a20e40e34a748839d144d`, tree
`d37eeb8b34b6f66a3d6ee39300d5af6e11666de1`; exact CI #95 passed.
The re-audit found retrieved identities without independent production citation
checking. The new bounded knowledge_verify tool/API checks stored source/chunk
identity, a retrieved snapshot digest and exact quotation. Research Agent tool
permissions include this read-only operation. Verification never establishes
claim truth or external source credibility and never automatically approves an
answer or a memory. Benchmark definitions, scoring and validators are unchanged.

Fresh full suite: **444 total, 443 passed, 1 skipped, 0 failures/errors**
(65.814s including runner overhead). Baseline: 436 total, 435 passed, 1 skipped.
Focused citation/benchmark/agent/API/orchestration tests: **38/38** (5.725s).
The deterministic benchmark report reproduced identically. No live request was
made. Fresh wheel build, offline install, installed CLI help, compile and
whitespace checks passed. General factual validation, source credibility,
semantic entailment, source revision workflows and live research quality remain
unfinished. Level 3 is BLOCKED/PARKED; deployment is FROZEN; live-agent baseline
remains user-reported 3/12 validated, with competence unverified.
