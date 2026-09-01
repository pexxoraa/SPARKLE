# Build state

Updated: 2026-09-01 UTC

| Field | State |
|---|---|
| SPARKLE version | 0.29.0-alpha.1 |
| Current phase | Continuous improvement — Phase 20/21 promotion-bound controlled build |
| Current task | Reconcile published controlled-build and CI evidence without extending it into source execution, publication, or deployment |
| Completed | v0.3-v0.22 capability releases and four-job CI; v0.23 capability publication and four-job CI; model abstraction/registry/MiniMax adapter; orchestrator/context/tracing; memory and knowledge lifecycle with backup; 16 built-in agents; persistent generated-agent installation; bounded structured Agent Blueprint generation/static routing evaluation/approval/rollback; isolated response-contract evaluation with bounded content-free evidence; provider-neutral AI System Blueprints; approval-gated `SPARKLE-AI-SYSTEM-DRAFT/1` natural-language conversion through the model router with isolated no-context/no-tool execution, exact duplicate-free JSON and full Blueprint revalidation, bounded content-free evidence, API/CLI/status/dashboard integration, and deterministic adapter tests; `SPARKLE-PROJECT/1` strict project lifecycle and evidence; `SPARKLE-SKILL/1` strict targets/evidence types/transactional derived levels/duplicate and future-evidence protection/optimistic metadata/archive/content-free proactive and least-privilege agent reads/API/CLI/status/dashboard integration; bounded workspaces/static verification/fixed local tests; signed external-worker client and deployable worker; reproducible approval-gated application artifacts; supervised automation service; bounded dashboard notifications; safe tools; text API/CLI/dashboard; bearer/session/CSRF/origin/rate/audit security; provider-neutral deterministic text/image/audio/document content contracts; dedicated voice/presence contracts; 16-agent matrix; documentation audit; cohesive E2E |
| In progress | v0.29 adds provider-neutral `SPARKLE-AI-SYSTEM-CONTROLLED-BUILD/1`: a separate expiring approval bound to the exact completed promotion, actor, and origin; promotion/candidate/destination digest revalidation; deterministic content-addressed source-bundle creation; immutable artifact verification; replay/race protection; content-free lifecycle/trace evidence; and API/CLI/status/dashboard integration. The verified capability is published at commit `0caff6c7ab1ffcf149edf052f1119a371a2ea326`, tree `d3afe3ede6252996c6663f428839378cb9c8d0bf`; SPARKLE CI run #56 passed Python 3.12, Python 3.13, worker-image, and automation-service |
| Blocked | Real Bubblewrap isolation on this executor (namespace setup denied); named remote worker/TLS target and live hostile-code validation; live MiniMax call (no key in build process); semantic non-text provider mapping; voice hardware; browser/computer runtime adapters; public application deployment target |
| Failed tests | The first v0.26 full run executed all 228 tests; 227 passed and the documentation version contract failed because BUILD_STATE still said v0.25 while package metadata had advanced to v0.26. This expected reconciliation-order failure is now corrected. Earlier historical harness and fixture failures remain recorded in the release report |
| Next action | Controlled build is reconciled. Keep source execution, artifact publication, and deployment as later separate stages; do not merge their trust boundaries |
| Estimated directive completion | 93% |

The v0.28 controlled-promotion boundary accepts only an approved immutable
candidate with a matching materialized plan, successful runtime evaluation,
and a separate unexpired promotion approval bound to the exact evaluation,
actor, and request origin. It revalidates candidate content and metadata,
copies exact UTF-8 bytes atomically into
`promotion_environment/staging/<system-name>`, verifies equal source and
destination digests, and records requested, promoting, promoted, rejected, or
failed evidence. Identical replays are deterministic; conflicting requests,
tampering, stale approvals, invalidation, supersession, traversal, overwrite,
partial writes, and lifecycle skips fail closed. Promotion does not build,
package, publish, deploy, modify production source, or prove worker isolation.

The v0.29 controlled-build boundary accepts only a completed promotion with
matching candidate and staged-tree digests plus a separate unexpired approval
bound to the exact promotion, actor, and request origin. It creates a
deterministic content-addressed ZIP from the promoted tree, verifies the
immutable artifact digest, and records requested, building, built, rejected,
or failed evidence. Identical replays are deterministic; conflicting requests,
stale or mismatched approvals, promotion tampering, and archive integrity
failures fail closed. This boundary does not import or execute promoted source,
publish an artifact, deploy a target, or modify production source.

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
