# Build state

Updated: 2026-09-08 UTC

| Field | State |
|---|---|
| SPARKLE version | 0.30.0-alpha.1 |
| Current phase | Infrastructure-independent foundation completion while preserving controlled execution boundaries |
| Current task | Indexed knowledge retrieval and integrated research-context verification; Level 3 parked |
| Completed | Existing promotion/build/execution foundations; NVIDIA Nemotron 3.5 Lightning primary adapter; retained disabled MiniMax adapter; evidence-based model health; capability/modality/tool/stream/latency/timeout request policy; explicit fallback; content-free usage/retry/routing evidence; orchestrator, trace, API, CLI, status, dashboard; fail-closed provider-neutral browser/computer contracts; all previously published memory, knowledge, agent, builder, project, skill, automation, security, and worker capabilities |
| In progress | Retrieval capability 7cc716f published; CI #74 passed all five jobs. Full suite 304/304. Evidence documentation follow-up; semantic retrieval/agent-quality evaluation remains unfinished. |
| Blocked | Level 3 = BLOCKED: user reports standalone Bubblewrap and seven canaries verified on Ubuntu; hardened systemd acceptance, authenticated external-worker acceptance and approved immutable artifact acceptance remain incomplete. Live model credentials, browser/computer/voice runtimes remain unavailable or unimplemented. |
| Failed tests | Initial retrieval focused run: 21/22 passed, one chunk whitespace-preservation failure; fixed and rerun 22/22. Final full suite 304/304. Historical failures below are not current failures. |
| Next action | Evaluate retrieval/agent outcomes and independent result validation, then project/task integration. Do not resume the parked systemd investigation. Deployment remains frozen. |
| Estimated directive completion | 12/46 (26.1%) fully verified category coverage, not effort completion; 93% withdrawn. See FOUNDATION_AUDIT.md for all 46 classifications and limitations. |

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


## Retrieval milestone local verification (2026-09-07)

- Baseline official suite: 297/297.
- Updated official suite: 304/304.
- Retrieval/storage/HTTP integration: 22/22.
- Execution/worker/runtime/promotion/build/security/artifact regression: 92/92.
- Documentation contracts: 4/4.
- Dashboard JavaScript syntax and whitespace: passed.
- Fresh wheel build and offline installation: passed, including installed
  Unicode/title retrieval and deletion smoke.
- Tracked source plus new test audit: 158 files; no symlinks, unsafe relative
  paths, generated binaries/databases/keys, files over 5 MiB, or detected
  private-key/provider-token material. This is a bounded pattern/path audit,
  not a guarantee that arbitrary secrets can be recognized.
- No credentials were created or used. Model live verification remains pending.
- Level 3 remains BLOCKED; deployment remains FROZEN.


## Published retrieval checkpoint — 2026-09-08

- Capability commit: `7cc716fd6121b680bc024728f9fffd34a0c677de`.
- Exact published tree: `d785ab0a14a37944f9d7d04854381a0e9d3443e7`.
- Parent: `21c6f5797460650ce352c5e589bceab84a3443e4`.
- Remote main and tree verified after a non-force fast-forward; local worktree
  clean at this capability checkpoint.
- [CI #74](https://github.com/pexxoraa/SPARKLE/actions/runs/34179742080):
  **5/5 jobs passed** for this exact commit: Python 3.12, Python 3.13,
  worker-image, controlled-execution-software, automation-service.
- Local full suite 304/304, focused retrieval 22/22, pipeline/security 92/92,
  documentation 4/4. Final wheel SHA-256:
  `6c03c82c2fe0658ae8111bfa72e07c3f65bf2ef5a7e000046aaccdfce88bad52`.
- Version unchanged. Level 3 BLOCKED. Deployment FROZEN.

This documentation follow-up records the capability checkpoint; its own commit
and exact CI result are reported separately after publication.
