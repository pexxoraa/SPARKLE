# Build state

Updated: 2026-08-31 UTC

| Field | State |
|---|---|
| SPARKLE version | 0.27.0-alpha.1 |
| Current phase | Continuous improvement — Phase 18/21 bounded candidate runtime evaluation |
| Current task | Reconcile the non-force v0.27 history replay, remote publication, and CI evidence without claiming executable isolation, production verification, promotion, or deployment |
| Completed | v0.3-v0.22 capability releases and four-job CI; v0.23 capability publication and four-job CI; model abstraction/registry/MiniMax adapter; orchestrator/context/tracing; memory and knowledge lifecycle with backup; 16 built-in agents; persistent generated-agent installation; bounded structured Agent Blueprint generation/static routing evaluation/approval/rollback; isolated response-contract evaluation with bounded content-free evidence; provider-neutral AI System Blueprints; approval-gated `SPARKLE-AI-SYSTEM-DRAFT/1` natural-language conversion through the model router with isolated no-context/no-tool execution, exact duplicate-free JSON and full Blueprint revalidation, bounded content-free evidence, API/CLI/status/dashboard integration, and deterministic adapter tests; `SPARKLE-PROJECT/1` strict project lifecycle and evidence; `SPARKLE-SKILL/1` strict targets/evidence types/transactional derived levels/duplicate and future-evidence protection/optimistic metadata/archive/content-free proactive and least-privilege agent reads/API/CLI/status/dashboard integration; bounded workspaces/static verification/fixed local tests; signed external-worker client and deployable worker; reproducible approval-gated application artifacts; supervised automation service; bounded dashboard notifications; safe tools; text API/CLI/dashboard; bearer/session/CSRF/origin/rate/audit security; provider-neutral deterministic text/image/audio/document content contracts; dedicated voice/presence contracts; 16-agent matrix; documentation audit; cohesive E2E |
| In progress | v0.27 implements provider-neutral runtime-evaluation contracts for approved candidates, exact candidate/plan validation, isolated evaluation bundles, signed external-worker submission with contract-bound limits, explicit lifecycle/failure states, bounded content-free results/traces, API/CLI/status integration, and deterministic worker-boundary tests. After the non-force history replay, the complete suite passed 236/236, the focused runtime/worker suite passed 29/29, and a fresh no-index installed-wheel gate passed. Private GitHub `main` published replayed capability commit `76aec2e439e82d9766c0dccf4ca3487c54288e3c` and documentation checkpoint `eb707aaf28602f2a7ec69cb5dedf7cc6375d319f`; SPARKLE CI runs #50 and #51 passed all four jobs |
| Blocked | Real Bubblewrap isolation on this executor (namespace setup denied); named remote worker/TLS target and live hostile-code validation; live MiniMax call (no key in build process); semantic non-text provider mapping; voice hardware; browser/computer runtime adapters; public application deployment target |
| Failed tests | The first v0.26 full run executed all 228 tests; 227 passed and the documentation version contract failed because BUILD_STATE still said v0.25 while package metadata had advanced to v0.26. This expected reconciliation-order failure is now corrected. Earlier historical harness and fixture failures remain recorded in the release report |
| Next action | Repository synchronization is reconciled; keep feature development paused until a separate build directive. A real named worker, signing configuration, and executable Bubblewrap hostile-canary evidence remain required before live runtime-isolation verification; promotion remains a later separate stage |
| Estimated directive completion | 93% |

Release-state reconciliation confirmed local v0.24 implementation at commit
`e5895087e082287df197f4e5c27b925f6dbe4a4d`, tree
`8b0d76e414bd6e8bc547e3ad649e74b58a1b409a`, restored CHANGELOG coverage,
aligned runtime version markers, and added a cross-surface regression contract.
The reconciled source passed 213/213 official tests and a fresh installed-wheel
gate. At that checkpoint this was local evidence only: private GitHub `main`
remained at `78032c1fbbaeab7253421f8cdde6e70da5d6f97c`, and no v0.24 remote CI
existed. The later non-force replay publication is recorded below.

The local and GitHub repositories were later found to have unrelated commit
ancestry despite content-equivalent v0.23 trees. The original verified local
v0.27 checkpoint was
`e2ebfd454bf0b1b194a453b716628e34d4407235`, tree
`b5f94e9366263fd0f4f9a2abe07220b61c076b47`. Remote `main` before replay was
`78032c1fbbaeab7253421f8cdde6e70da5d6f97c`. Seven intended commits were
replayed without conflicts as normal descendants of that remote commit; no
force push, unrelated-history merge, deletion, or history replacement occurred.
The published v0.27 capability checkpoint is
`76aec2e439e82d9766c0dccf4ca3487c54288e3c` with the same verified tree
`b5f94e9366263fd0f4f9a2abe07220b61c076b47`. Post-replay verification passed
236/236 official tests in 35.407 seconds and 29/29 focused runtime/worker tests
in 9.534 seconds; dashboard syntax, whitespace, packaging, fresh offline
installation, version, binary, secret-signature, and generated-artifact checks
passed. SPARKLE CI run #50 (`33398943322`) passed `test (3.12)`, `test (3.13)`,
`worker-image`, and `automation-service`. The original local SHA was not
published; it remains preserved by the local `audit/original-v0.27` branch.

The v0.25 Implementation Plan boundary revalidates the Blueprint and derives a
deterministic provider-neutral plan with confined proposed paths, ordered work
dependencies, evaluation contracts, and release gates. Approved
materialization writes only the plan manifest and content-free evidence. The
complete local suite passes 219/219 and a fresh installed wheel passes, but
human review, source generation, runtime evaluation, and deployment remain
unexecuted. The completion estimate therefore remains 93%.
At the original v0.25 checkpoint, local capability commit
`2b98f25468a48bed992fb30fc187288f0de63705` has tree
`a74ff1148a00f543ca923ebffaa6258ab70b5ca3`; it is not published and has no
remote CI evidence under that original SHA. Its content was later replayed and
published through the reconciled lineage recorded above.

The v0.26 Source Candidate boundary consumes only an explicitly reviewed,
materialized implementation plan. A separate provider disclosure must be
approved before the isolated generation call. Output is exact, bounded,
plan-path-confined JSON written under `candidate_environment`, never the
application or production tree. Generated, human-reviewed, statically
verified, and approved are distinct states. Static verification parses and
scans source without importing it or claiming runtime correctness. Completion
remained 93% at that checkpoint because runtime evaluation, source promotion,
isolated execution, deployment, live MiniMax evidence, and remote publication
were incomplete. Runtime-evaluation contracts and remote publication were
added later; the other limitations remain.

The v0.27 Runtime Evaluation boundary accepts only an approved candidate and
exact matching plan ID. Approved declarative contracts create unique evaluation
and trace IDs, materialize an evaluator-owned bundle outside application and
production workspaces, and submit only through the existing HTTPS/HMAC worker
client with signed timeout/output limits. Results preserve distinct requested,
queued, submitted, running, completed, evaluated, rejected, start, timeout,
worker, protocol, execution, and criteria failure states. Deterministic tests
exercise these contracts, but no named worker is configured and no executable
isolation evidence exists; `isolation_verified` therefore remains false.

The percentage measures the full long-term directive, not code volume. Agent
specifications are operational through the common orchestrator. Structured
Agent Blueprints now provide deterministic non-mutating requirements-to-
manifest preparation, production-router fixtures, approval-gated installation,
separate evidence persistence, and rollback. Approved response-contract runs
now execute through an isolated no-context/no-tool profile and store bounded
content-free evidence. Generated agents, internal
automations, bounded workspace creation/static verification,
the full external-worker protocol/service loop, deterministic artifact
packaging, the supervised automation lifecycle, and eight structured proactive
rule types now have runtime evidence.
Structured AI System Blueprints now resolve capability/modality routes from the
model registry, validate installed agents and their tool access, preserve the
separate data environments, and materialize a deterministic architecture
manifest only after explicit approval. This is static architecture and
workspace evidence, not generated implementation, semantic evaluation, or
deployment evidence.
The separate AI System Draft boundary now converts explicitly approved bounded
natural language through the common model router and isolated execution
profile, then rejects anything that is not exact duplicate-free JSON satisfying
the entire Blueprint contract. Its persisted evidence contains no prompt or
generated JSON. Deterministic injected-adapter execution is verified; live
MiniMax semantic fidelity and autonomous implementation generation are not.
The Project Agent now reads validated structured project state through a
least-privilege tool. Explicit interfaces own optimistic create/update/archive
operations, and bounded content-free events plus proactive alerts make status,
deadlines, blockers, milestones, and next actions operational rather than
prompt-only. Live-model decision quality and external project/calendar
connectors remain incomplete.
The provider-neutral multimodal transport phase is implemented and locally
tested. It proves bounded content flow, not semantic understanding by the
currently text-only MiniMax adapter. The reference production executor and
deployment profiles exist, but this host
cannot validate their namespaces and no remote instance is provisioned, so
isolation remains blocked. Natural-language agent source generation, semantic
correctness evaluation, live-provider evaluation verification, autonomous code generation, and external
deployment adapters, external email/SMS/push/calendar/webhook delivery, external research
polling, live browser control, real voice, physical embodiment, multi-user role authorization,
TLS/edge rate limiting, and deployment are not
complete.
