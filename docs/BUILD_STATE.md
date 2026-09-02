# Build state

Updated: 2026-09-02 UTC

| Field | State |
|---|---|
| SPARKLE version | 0.30.0-alpha.1 |
| Current phase | Infrastructure-independent foundation completion while preserving controlled execution boundaries |
| Current task | Publish the evidence-backed foundation audit; await only genuine external prerequisites |
| Completed | Existing promotion/build/execution foundations; NVIDIA Nemotron 3.5 Lightning primary adapter; retained disabled MiniMax adapter; evidence-based model health; capability/modality/tool/stream/latency/timeout request policy; explicit fallback; content-free usage/retry/routing evidence; orchestrator, trace, API, CLI, status, dashboard; fail-closed provider-neutral browser/computer contracts; all previously published memory, knowledge, agent, builder, project, skill, automation, security, and worker capabilities |
| In progress | NVIDIA adapter commit `c7c1512d8b08b72df8330a769b8a2033037638e2` passed CI #67. Model runtime commit `5c7d5a06471663462cabbab4edf757adf5e4f1ad` passed CI #68. Interaction/dashboard commit `acaf61936e305da104bcb7ccaa37086273f880a0`, tree `e18e0bc8bb2ea7edfabc5661e075ff732e4c71f4`, passed CI #69 (`33629696189`) across all five jobs. Fresh evidence is 295/295 and focused model/interaction/API/CLI coverage is 70/70. |
| Blocked | Real Bubblewrap isolation on this executor; named isolated worker/TLS endpoint and hostile-canary evidence; live Nemotron call without a credential; semantic non-text provider mapping; voice hardware/providers; live browser/computer runtime adapters; public application deployment target |
| Failed tests | The first v0.26 full run executed all 228 tests; 227 passed and the documentation version contract failed because BUILD_STATE still said v0.25 while package metadata had advanced to v0.26. This expected reconciliation-order failure is now corrected. Earlier historical harness and fixture failures remain recorded in the release report |
| Next action | Supply an NVIDIA key for live-model verification or a namespace-capable worker for Level 3. Deployment remains frozen. |
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

The v0.30 controlled-execution boundary accepts only a `built` controlled-build
record and a new unexpired authorization bound to the exact artifact ID and
digest, full promotion lineage, requested mode, timeout, output limit, actor,
and origin. It revalidates the authoritative chain, artifact database record,
regular-file identity, ZIP digest, manifest, entry paths, entry types, sizes,
and per-file digests. It rechecks the artifact immediately before submitting an
ephemeral extracted snapshot through the existing authenticated worker. The
signed result binds execution ID, request ID, artifact digest, worker identity,
status, output digest, result digest, and timestamps. `VERIFIED` means the
controlled execution result was authenticated and internally consistent; it
does not mean published, deployed, production, or isolation-verified.

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
