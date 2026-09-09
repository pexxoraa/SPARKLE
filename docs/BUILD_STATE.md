# Build state

Updated: 2026-09-08 UTC

| Field | State |
|---|---|
| SPARKLE version | 0.30.0-alpha.1 |
| Current phase | Infrastructure-independent foundation completion while preserving controlled execution boundaries |
| Current task | Retrieval benchmark, four-agent outcome harness and independent deterministic result validation |
| Completed | Existing promotion/build/execution foundations; NVIDIA Nemotron 3.5 Lightning primary adapter; retained disabled MiniMax adapter; evidence-based model health; capability/modality/tool/stream/latency/timeout request policy; explicit fallback; content-free usage/retry/routing evidence; orchestrator, trace, API, CLI, status, dashboard; fail-closed provider-neutral browser/computer contracts; all previously published memory, knowledge, agent, builder, project, skill, automation, security, and worker capabilities |
| In progress | Benchmark capability and CI-discovered migration fix published; CI #77 passed 5/5 jobs. Final documentation checkpoint. Live-model and real semantic quality remain unverified. |
| Blocked | Level 3 = BLOCKED: user reports standalone Bubblewrap and seven canaries verified on Ubuntu; hardened systemd acceptance, authenticated external-worker acceptance and approved immutable artifact acceptance remain incomplete. Live model credentials, browser/computer/voice runtimes remain unavailable or unimplemented. |
| Failed tests | Initial retrieval focused run: 21/22 passed, one chunk whitespace-preservation failure; fixed and rerun 22/22. Final full suite 304/304. Historical failures below are not current failures. |
| Next action | Evaluate real embedding and live-agent outcomes when authorized providers are available; expand reviewed tasks and validators. Keep Level 3 parked and deployment frozen. |
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


## 2026-09-08 measurable evaluation milestone

Baseline inspected: `ca893e430f5905d5c4663f43eda576eb8800fedb`, tree
`ca75de89229d299d796dacbf9e8bceda470fc95b`, clean main.
Fresh baseline: 304/304 tests. See [benchmark methodology](BENCHMARKS.md)
and [machine-generated report](../benchmarks/evidence/REPORT.md).

The frozen 16-query lexical baseline is Recall@1 0.625, Recall@3/5 0.75,
MRR 0.71875. Token-hash semantic/hybrid results are labeled test-double
experiments; no production retriever switch or semantic-quality claim is made.
Twelve scripted tasks across Personal, Research, Learning and Coding independently
validate real tool/state outcomes. Wrong-answer and missing/subjective-evidence
controls distinguish rejection and inconclusive results from execution success.
Context is now bounded, attributed untrusted data outside the system role.

A stronger coding fixture initially requested unsupported `python_syntax`;
SPARKLE rejected it, producing 11/12 task passes and one failed benchmark test.
The fixture was corrected to the existing `python_compile` contract. No verifier
or security boundary was loosened. Optional live evaluation is explicitly skipped
without opt-in; NVIDIA is still IMPLEMENTED BUT INSUFFICIENTLY VERIFIED.
No capability category, version, Level 3 or deployment status is upgraded.


### Final local verification

- Official discovery suite: **319 run; 318 passed; 1 optional live test skipped;
  0 failures**, in 30.883 seconds. Baseline was 304/304.
- Focused benchmark/retrieval/HTTP suite: **22/22**.
- Documentation contracts: **4/4**.
- Regenerated benchmark JSON and Markdown match committed evidence byte-for-byte.
- Fresh wheel build/offline installation and installed retrieval/context/validator
  smoke: passed. Wheel SHA-256:
  `6c418ae309fa5f38edf61a83e798aa031f8dbce67e3d90bb82d6c436cdb8f8cc`.
- Dashboard JavaScript and whitespace: passed. Audit of 172 tracked/proposed
  files found no symlinks, unsafe paths, unintended generated binaries/databases,
  files above 5 MiB, or recognized private-key/provider-token material. Intended
  benchmark JSON/Markdown evidence is version-controlled, not excluded as output.
- Lexical Recall@1/3/5: 0.625 / 0.75 / 0.75; MRR 0.71875.
- Scripted agent outcomes: 12/12 validated. Controls: 1 rejected, 2 inconclusive.
- Live provider/real semantic quality remains pending; Level 3 BLOCKED and
  deployment FROZEN. No production-retriever or worker changes.


## CI-discovered automation migration race — 2026-09-08

Benchmark capability `d3e529598430c9939a1b900fb0d5aa01d22466b5`, tree
`724ff0fad93521784d3e1a3a2022c8d889d66c66`, was published as a strict descendant
of `ca893e4`. [CI #76](https://github.com/pexxoraa/SPARKLE/actions/runs/34193484793)
passed four jobs, including Python 3.13 benchmark reproduction, but Python 3.12
failed an existing automation SIGTERM test: simultaneous startup attempted to add
`claim_token` twice. This was a real schema check/migration race, not a benchmark
metric failure or a reason to rerun until green.

The fix acquires SQLite's write reservation before schema creation/inspection
and holds it through migration. A coordinated two-connection test reproduces the
published duplicate-column error and passes with the fix. A six-initializer test
also preserves stored records. No automation policy or worker boundary changes.
Fresh verification after the fix: **321 run, 320 passed, 1 optional live test
skipped, zero failures** (38.637 seconds); automation/benchmark focus **32/32**.
Benchmark metrics and evidence remain unchanged. Level 3 remains parked/BLOCKED;
deployment remains FROZEN. Exact follow-up publication/CI evidence follows.


## Verified benchmark checkpoint — 2026-09-08

- Benchmark capability: `d3e529598430c9939a1b900fb0d5aa01d22466b5`.
- CI-driven migration fix / verified code HEAD:
  `b73495dc86fd0745a31a596891aff40c1c719caa`.
- Verified code tree: `cd41f390574d4be5fd6675318c302f95ca113eab`.
- [CI #77](https://github.com/pexxoraa/SPARKLE/actions/runs/34194421673): all
  **5/5 jobs passed**, including Python 3.12 and 3.13 full suites and exact
  benchmark reproduction. CI #76's migration race remains documented above.
- Local final suite: 321 run, 320 passed, 1 explicitly skipped live test;
  automation/benchmark focus 32/32; retrieval/HTTP focus 22/22; docs 4/4.
- Fresh wheel with the migration fix installed offline and passed startup/
  independent-validator smoke. Post-fix audit covered 173 files without
  recognized secret, path, symlink or oversized-file findings.
- Remote HEAD/tree and strict non-force lineage verified; worktree clean at
  the code checkpoint. This documentation follow-up receives separate CI.
- Credential-free benchmark/validator milestone complete; live agent competence,
  trained semantic retrieval, NVIDIA authentication and production-scale quality
  remain unverified. Level 3 BLOCKED/PARKED; deployment FROZEN. Version unchanged.

## 2026-09-09 — benchmark evidence and pre-provider classification

Starting published main: `73d2362ec9f3361bdec15f9ffbbcf402e77f4d27`.
Fresh baseline: 364 passed, 1 optional live test skipped (365 total).
Final local suite: 374 passed, 1 optional live test skipped (375 total), 52.223s.
Focused benchmark/provider/runtime/storage suite: 44/44 passed, 5.482s.
Ten new regression tests cover classification, actual adapter plumbing with explicit
HTTP doubles, usage, timeout/retry evidence, incomplete setup, interruption,
redaction, and refusal to overwrite evidence. These are not live NVIDIA results.

Missing NVIDIA configuration and routing rejection no longer share the generic
provider-failure classification. The optional live runner preserves incremental
content-free evidence and uses normal per-task model registries. The unchanged
12 tasks, expected outcomes, scoring, validators and model configuration remain
intact. Deterministic retrieval and agent results reproduce exactly; only the
benchmark implementation fingerprint changed. No version increment is claimed.

Wheel build and fresh no-index/no-dependency installation passed. Compile checks,
dashboard JavaScript, whitespace, and tracked-file credential-pattern/path/symlink/
5-MB size audits passed. No live call occurred; this executor has no NVIDIA key.
The user-reported successful host smoke remains connectivity evidence. The latest
host benchmark is inconclusive and its original generic failure is not diagnosed
from a traceback alone. See [live evidence procedure](BENCHMARKS.md) and
[current capability inventory](CURRENT_AUDIT.md).

Level 3 remains BLOCKED/PARKED. Deployment remains FROZEN. Real embedding quality,
real agent outcome rates and host acceptance are not upgraded. This milestone
completes local diagnostic/evidence preparation, not the entire platform mission.

## 2026-09-09 — response protocol and failure evidence

Starting main: `64bba98b549bbd7fcc37eaca9aed09f6bcac48f1`.
The user reports a completed real 12-task NVIDIA run: 1 validated, 1 rejected,
9 JSONDecodeError, 1 RuntimeError; 200.914 seconds; 8.33% validated.
This updates the prior pre-provider/inconclusive checkpoint: evaluation now
executed, but autonomous competence remains unestablished. Individual historical
failure causes remain unproven because the response shapes and task-level evidence
were not supplied. No live rerun occurred in this debugging milestone.

A shared versioned final JSON contract now accompanies the unchanged tasks.
No parser extraction/repair is permitted. Safe response structure/hash, parsing
stage, typed runtime code and individual validator checks are captured. Explicit
orchestrator failures retain the public RuntimeError type; no tool limit is relaxed.
An initial full regression exposed a subclass-name incompatibility, which was
corrected without changing its existing test or evaluator. Native tool calls and
NVIDIA reasoning/content separation have deterministic regression coverage.

See [protocol investigation and missing-evidence gate](BENCHMARKS.md).
Tasks, scoring, validators, model settings, Level 3 and deployment remain unchanged.
The scripted baseline remains 12/12 and retrieval metrics remain unchanged.
No new capability classification or version increment is warranted by this fix.
Level 3 remains BLOCKED/PARKED; deployment remains FROZEN.

Fresh verification: baseline 374 passed + 1 optional live skip (375 total).
Final full suite: 387 passed + 1 optional live skip (388 total), 62.524 seconds.
Focused suite: 64/64, 23.469 seconds. Thirteen new test methods cover the requested
protocol/outcome cases, including an early runtime JSON error negative control.
Wheel build, fresh offline installation, compile/JavaScript checks and tracked-tree
secret-pattern/path/symlink/size audits passed. The deterministic benchmark outcome
and retrieval sections remain exactly equal; implementation fingerprints changed.
