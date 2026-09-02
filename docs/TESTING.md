# Testing

Run:

```bash
make check
```

The command compiles all Python files and runs the standard-library `unittest`
suite. Coverage includes secrets, configuration, model registry operations,
MiniMax request mapping, provider-state preservation, retry and streaming,
memory lifecycle and backup, knowledge lifecycle and backup, traces, automation
claiming/execution/retry/recurrence/cooldown/history, proactive rules, generated
agent persistence/routing/removal, bounded workspace scaffolding, tool
sandboxing, static workspace verification, non-execution guarantees, CLI
scaffold-to-verify flow, orchestration, multi-agent synthesis, the HTTP API,
security headers, bearer authorization, unauthorized non-mutation, origin and
preflight policy, fail-closed bind validation, and the dashboard. Session tests
cover login failure/success, opaque HttpOnly cookies, absolute expiry, bounded
capacity, reload recovery, CSRF rejection/acceptance, logout/revocation, remote
secure-cookie binding, secret-free status/audit, and absence of browser storage.
The API-security cases also cover deterministic fixed-window reset/rejection,
bounded client state, rate limiting before authorization, quota response
headers, query stripping, and absence of credentials, origins, headers, and
client identities from audit records.

NVIDIA/model-runtime coverage validates exact Nemotron identity, Bearer-secret
resolution, request/response/SSE/tool/usage normalization, safe retry/errors,
provider switching, evidence-based health, capability and latency policy,
explicit fallback, content-free usage evidence, and unknown usage. Interaction
coverage validates exact HTTPS allowlists, malformed ports, redirect escape,
output bounds, typed GUI actions, fail-closed defaults, and test-harness labels.
Neither suite claims a live NVIDIA request, browser execution, or GUI control.
Supervised-automation coverage adds legacy-schema migration, expiring claims,
explicit recovery records, old-token fencing, real deterministic orchestrator
execution and traces, singleton lock refusal, mode-0600/no-follow lock policy,
bounded degraded cycles, fresh/stale lifecycle status, pre-requested shutdown,
installed-style CLI check/once/status/health behavior, a real subprocess
SIGTERM drain, and systemd hardening inspection.
Proactive coverage validates exact condition schemas, unknown-field and
unsupported-category rejection, deadline compatibility, structured weak-skill
conditions with cooldown, all seven alert types, invalid-evidence suppression,
deterministic ordering and the 200-alert bound, API audit normalization,
dashboard loading, and
absence of memory free text from serialized alert evidence.
Configuration packaging coverage verifies that checkout defaults and bundled
defaults are identical, an installed runtime materializes separate mode-0600
application/model configuration, and the writable model registry remains
outside the installed package. The release checkpoint also builds and installs
a real non-editable wheel in a fresh virtual environment before running the
service lifecycle.
Request-log coverage verifies that query names and values are stripped.
Workspace-runner coverage executes a real fixed unittest suite and verifies
POSIX resource limits, a stripped child environment, credential-pattern output
redaction, parent-secret refusal, symlink and arbitrary-field rejection,
process-group wall timeout, pre-persistence output bounding, persistence, CLI/API/dashboard integration, and
explicit status that filesystem/network isolation is absent.
External-client coverage uses a deterministic signed worker double to verify
request signatures, source digests and bounds, response signatures, freshness,
job identity, exact schemas, status consistency, output redaction, safe
persistence, disabled/default behavior, operator approval, non-registration as
a model tool, and API/CLI integration.
Adversarial cases cover signature tampering, stale responses, mismatched job
IDs, unknown fields, oversized responses, transport failures, symlinks, hidden
and credential-like files, non-UTF-8 files, oversized files, and source that
contains the configured signing key.

Reference-worker coverage adds real server-side request validation, private
no-follow key files, replay/idempotency conflict behavior, concurrency refusal,
executor-unavailable recovery, exact-key response redaction, signed health/job
HTTP behavior, immutable Bubblewrap command inspection, real Bubblewrap
preflight, process timeout, deployment-policy inspection, and a true in-memory
client → service → child unittest → signed response workflow. That workflow
imports submitted application code and persists the verified client result.
The process executor explicitly reports no isolation. The production executor
reports ready only when its real namespace/canary/environment/network preflight
succeeds. Worker sandbox booleans remain explicitly unverified claims at the
application client.

Artifact coverage verifies byte-for-byte deterministic ZIP output, canonical
embedded manifests, normalized archive metadata, immutable content-addressed
reuse, new artifacts after source changes, tamper refusal, stable no-follow
file reads, symlink/sensitive/reserved/portable-name/size rejection, approval
gates, CLI/API/dashboard integration, and append-only deployment reports that
remain explicitly unverified and execute no external action.

Multimodal coverage validates byte-compatible legacy text serialization;
image, audio, and document construction; text+image, text+document, and fully
mixed requests; deterministic canonical round trips; empty, oversized,
malformed, wrong-MIME, unsupported-type, duplicate-ID, aggregate-message, and
metadata boundaries; API execution and rejection paths; context, routing,
adapter, result, and raw-content-free trace flow; fail-closed MiniMax behavior
before network access; trace-schema migration; and future compatible-adapter
selection without orchestrator changes.

Voice/presence contract coverage verifies explicit disabled STT/TTS failures,
provider-neutral deterministic adapter injection, shared-core status, initial
presence state, and agent/trace-linked presence transitions. These tests do not
claim hardware I/O or a production speech engine.

Built-in agent evaluation coverage uses a 16-agent domain matrix. It verifies
each agent's capability, domain instruction, minimum tool boundary,
unambiguous routing prompt, common evidence guardrails, actual deterministic
orchestrator execution, and successful trace linkage. This is structural and
execution evidence; it is not a live-provider response-quality benchmark.

Agent Blueprint coverage verifies deterministic non-mutating preparation,
exact fields and bounds, duplicate rejection, known-tool enforcement,
production-router fixture execution, approval refusal, persistent
install/reload/routing, split-store rollback, and equivalent API and CLI
lifecycles. These are static manifest and routing evaluations; no test claims a
live model response-quality benchmark or external deployment.

Agent response-evaluation coverage verifies exact bounded assertions,
approval before model calls, installed-manifest revalidation, deterministic
pass/fail contracts, an isolated no-history/no-user/no-context/no-tool
orchestrator profile, tool-call refusal, raw prompt/response non-disclosure,
generic traces, safe error types, API/CLI execution, and retention of only the
latest 1,000 evidence records. It does not claim semantic correctness or a live
provider evaluation.

AI System Blueprint coverage verifies exact bounded requirements,
provider/model-neutral capability and modality resolution from enabled model
records, installed-agent and registered-tool references, agent tool access,
separate data-environment declarations, deterministic preparation and
serialization, approval before mutation, two-file workspace materialization,
safe failure types, reload, latest-1,000 retention, and equivalent API/CLI
flows. It does not call a model, execute runtime evaluations, generate an
implementation, or claim deployment.

AI System Draft coverage verifies explicit approval before provider disclosure,
20–20,000-byte input bounds, dynamic provider-neutral registry vocabulary,
isolated no-history/no-user/no-context/no-tool execution, tool-call refusal,
exact-JSON and duplicate-key rejection, complete Blueprint revalidation,
content-free bounded evidence, latest-1,000 retention, generic traces, status,
dashboard counters, and equivalent API/CLI flows. Deterministic injected
adapters verify the integration; these tests do not claim live MiniMax use,
semantic fidelity, source generation, runtime evaluation, or deployment.

Structured-project coverage validates exact lifecycle manifests, normalized
timezone-aware deadlines, dependencies, risks, milestones, blockers, progress,
complete/blocked truth constraints, optimistic update conflicts, priority and
deadline ordering, literal search escaping, archive immutability, active and
event bounds, reload, content-free change evidence, least-privilege read-tool
access, direct content-free proactive alerts, API/CLI lifecycle, status, and a
read-only dashboard panel. No test claims semantic project decisions or an
external project/calendar connection.

## Phase 33 evidence matrix

| Required category | Executed evidence | Remaining external gap |
|---|---|---|
| Unit | Content, security, stores, routing, tools, services, and validators | None for implemented local units |
| Integration | API, orchestrator/context/model, multimodal, automation, artifact, and worker boundaries | Live provider and deployed external targets |
| System | Composed system, HTTP server, persisted stores, status, dashboard, and service lifecycle | Production identity/TLS/deployment environment |
| Agent | All 16 built-ins plus structured agent/AI-system blueprints, static routing fixtures, isolated response contracts, structured Project Agent evidence/read access, approval, persistence, rollback, routing, tools, deterministic execution, and traces | Natural-language source generation, semantic/live-provider quality evaluation, external deployment |
| Model | MiniMax mapping/retry/stream/tool state, registry switching, capability/modality routing, deterministic adapter | Live MiniMax credentialed smoke call |
| Memory | CRUD, search, archive/restore, structured proactive evidence, and backup | Production retention/encrypted backup policy |
| Tool | Allowlists, schemas, bounds, approval, confinement, execution, and failure paths | Disabled web/browser/computer adapters |
| Voice | Disabled failures, adapter injection, and shared-core contract | Real STT/TTS and microphone/speaker hardware |
| Application | Scaffold, static verification, fixed tests, artifacts, worker protocol/service, API/CLI/dashboard | Target-specific build and deployment adapters |
| AI system | Single/multi-agent orchestration, tool loop, structured agent and AI System Blueprints, registry-backed model routes, generated agents, model independence, multimodal transport, approval-gated deterministic architecture workspaces | Autonomous natural-language requirements-to-implementation, semantic runtime evaluation, and deployment |
| End-to-end | HTTP chat, automations, workspace flows, and client → worker → child unittest → signed result | Live provider, remote isolation, and external actions |
| Regression | Exact `make check` gate on the full standard-library suite | None for implemented local behavior |

`PASS` in this matrix means an executable local path exists and ran. It does
not convert an external or hardware-dependent requirement into a pass.

Documentation regression coverage verifies the complete master-directive file
inventory, repository-confined relative Markdown links, package/display version
consistency, required build-state fields, and continued `PARTIAL`/`BLOCKED`
honesty in acceptance reporting.

Schedule-conflict coverage verifies cross-category overlapping intervals,
normalized safe pair evidence, free-text non-disclosure, invalid/missing/past/
reversed/overlong suppression, touching and one-minute boundaries, the 30-day
horizon, deterministic ordering, the dedicated pair bound, conditional
automation cooldown, and API exposure.

The Phase 35 cohesive system workflow uses the real HTTP server and separate
memory, knowledge, and trace stores. It writes context through the API, submits
a mixed text/document request, proves retrieved context reached the selected
agent/model request, verifies result modalities and IDs, reads the completed
trace back through the API without raw document content, and confirms the
presence state links to the same agent and trace.

The deterministic adapter avoids provider cost and network flakiness. The live
smoke test is intentionally separate:

```bash
sparkle smoke-test --live
```

Never report the live test as passed when the credential is absent or the exact
`SPARKLE_LIVE_OK` response is not observed.

Latest Phase 35 continuation result on 2026-08-30: 150 local tests passed in
28.012 seconds after adding the Phase 34 documentation contracts and the
cohesive Phase 35 system workflow. The Phase 33 checkpoint passed 145 tests in
22.919 seconds after four voice/presence cases and three data-driven 16-agent
evaluation groups. The v0.15 capability release previously
passed 138 tests in 22.472 seconds; an earlier complete run passed in 23.005
seconds. Dashboard JavaScript syntax and Git whitespace checks passed. A zero-dependency
non-editable `0.15.0a1` wheel installed in a fresh virtual environment and
passed status, mixed-content round trip, legacy serialization, automation
check/once/status, worker-entrypoint, and mode-0600 configuration checks.
GitHub CI run #33 (`33290153808`) passed the 150-test final checkpoint on
Python 3.12 and 3.13, the separately deployable worker image
build/entrypoint, and the installed automation-service lifecycle. Runs #31 and
#32 preserve the earlier exact multimodal and Phase 33 checkpoints.

Latest v0.16 pre-publication result on 2026-08-30: the corrected full suite
passed 154 tests in 19.378 seconds after the four schedule-conflict cases were
added. Dashboard JavaScript syntax and Git whitespace checks passed. A clean
zero-dependency non-editable `0.16.0a1` wheel installed in a fresh virtual
environment and passed installed status, structured schedule-conflict
evaluation/non-disclosure, multimodal round trip, automation
check/once/status, worker-entrypoint, and mode-0600 configuration checks.
GitHub CI run #35 (`33299313086`) passed the exact v0.16 capability tree on
Python 3.12 and 3.13, the separately deployable worker image
build/entrypoint, and the installed automation-service lifecycle.

Latest v0.17 pre-publication result on 2026-08-30: six focused
knowledge-revision, automation, and API cases passed after correcting one
over-broad privacy assertion. The corrected adjacent storage, automation, and
API set passed 38 tests in 13.418 seconds. After adding the CLI revision flow,
the corrected complete suite passed 160 tests in 34.371 seconds; dashboard
JavaScript syntax and Git whitespace checks passed. A zero-dependency
non-editable `0.17.0a1` wheel installed without an index and passed installed
status, research-change/non-disclosure, multimodal round trip, automation
check/once/status, worker-entrypoint, and mode-0600 configuration checks.
GitHub CI run #37 (`33300452288`) passed the exact v0.17 capability tree on
Python 3.12 and 3.13, the separately deployable worker image
build/entrypoint, and the installed automation-service lifecycle.

Latest v0.18 pre-publication result on 2026-08-30: the focused notification
store, strict action, conditional-delivery/trace, API/read-state, and dashboard
set passed. The adjacent notification, storage, automation runner/service, and
API set passed 52 tests in 17.048 seconds. After the dedupe-retention boundary
case was added, the corrected complete suite passed 166 tests in 36.292
seconds; dashboard JavaScript syntax and Git whitespace checks passed.
A zero-dependency non-editable `0.18.0a1` wheel installed without an index and
passed installed notification automation/read-state, trace non-disclosure,
multimodal round trip, automation check/once/status, worker-entrypoint, and
mode-0600 configuration checks.
GitHub CI run #39 (`33301375054`) passed the exact v0.18 capability tree on
Python 3.12 and 3.13, the separately deployable worker image
build/entrypoint, and the installed automation-service lifecycle.

The first v0.19 complete run executed 172 tests: 171 passed and the
documentation version-consistency contract caught that `BUILD_STATE.md` still
reported v0.18 after the code/package version moved to v0.19. The state file
was corrected; the failed attempt remains recorded in `RELEASE_REPORT.md` and
is not counted as a passing gate. The corrected complete suite passed all 172
tests in 22.177 seconds. An auxiliary JavaScript check first targeted an
obsolete path and failed after the suite; `node --check` on the actual packaged
dashboard path and Git whitespace checks then passed.
An initial clean wheel was invalidated after final review added append-only
remove/rebuild history. A fresh zero-dependency non-editable `0.19.0a1` wheel
from the final capability tree installed without an index. It passed installed
blueprint prepare/build/reload/routing, remove/rebuild history, multimodal
round-trip, automation check/once/status, worker-entrypoint, and mode-0600
configuration checks. Its SHA-256 was
`3f29323e7c0fd2ec67b06ba3fe9451ad5b5aa43122a0aaa0229dae913cfd0919`.
GitHub CI run #41 (`33313769623`) passed the exact v0.19 capability tree on
Python 3.12 and 3.13, the separately deployable worker image
build/entrypoint, and the installed automation-service lifecycle.

The first v0.20 complete run executed 179 tests: 178 passed and the
documentation version-consistency contract caught that `BUILD_STATE.md` still
reported v0.19. The state file was corrected; the failed attempt is preserved
in `RELEASE_REPORT.md` and is not counted as a passing gate. A corrected
complete suite passed all 179 tests in 22.690 seconds; a final exact-tree run
passed all 179 tests in 22.564 seconds. Dashboard JavaScript
syntax and Git whitespace checks passed. A zero-dependency non-editable
`0.20.0a1` wheel installed without an index and passed isolated Agent Blueprint
response evaluation/non-disclosure, blueprint reload/routing, multimodal
round-trip, automation check/once/status, worker-entrypoint, and mode-0600
configuration checks. Its SHA-256 was
`a41d689e9fea9cc7eaf16dde4b287aa4d1169351a1a135831140d7e9e505d5f4`.
GitHub CI run #43 (`33314903193`) passed the exact v0.20 capability tree
`99db2e28bfaafff456e42b1c8cce1b51b4f7a631` on Python 3.12 and 3.13, the
separately deployable worker image build/entrypoint, and the installed
automation-service lifecycle. After recording that evidence, the resulting
documentation checkpoint passed all 179 tests in 22.433 seconds.

The v0.21 AI System Blueprint increment added seven focused builder/API/CLI
tests. The first complete run executed 186 tests: 185 passed and the
documentation version-consistency contract caught that `BUILD_STATE.md` still
reported v0.20. After correction, all 186 tests passed in 24.235 seconds; the
final documented tree passed all 186 tests in 24.451 seconds. A zero-dependency
non-editable `0.21.0a1` wheel installed without an index and passed AI system
prepare/build/reload, Agent Blueprint response evaluation/non-disclosure,
multimodal round-trip, automation check/once/status, worker-entrypoint, and
mode-0600 configuration checks. Its SHA-256 was
`6c310495ba44b6e489b30f6b81a2218951fe3e4ae0ad0b0a2bf20e06a8d33510`.
After the development executor reset, the capability was reconstructed over
the exact published v0.20 tree and all 186 tests passed again in 26.097
seconds. Two recovery wheel smokes stopped on invalid test-fixture calls after
the wheel itself built and installed; the corrected fresh no-index gate passed
with wheel SHA-256
`d529a955fdd2f3186aca64d563f5fdeda03443a746be4b3dc760d025c5b74cf7`.
The exact candidate tree then passed all 186 tests in 25.361 seconds.
Capability commit `0256c16bd247f84448baf1ed9ae9f6ecc8f3e0fb` has that exact tree,
`02acd582684da3dd335bc7fe503bc538c4bfbf75`. GitHub CI run #45
(`33329833127`) passed Python 3.12, Python 3.13, worker-image, and
automation-service jobs.

The v0.22 structured-project increment added eight store/API/CLI cases and
expanded dashboard, documentation-version, agent-tool, and proactive
regressions. The first focused run exposed three invalid SQLite escape errors;
the corrected escape then exposed one incorrect literal-underscore fixture
expectation. Both failures are preserved in `RELEASE_REPORT.md`. The corrected
22-test adjacent suite passed in 1.490 seconds, and the complete suite passed
all 194 tests in 26.371 seconds. A zero-dependency non-editable `0.22.0a1`
wheel installed without an index and passed project
create/update/reload/search/proactive/archive, AI-system preparation,
multimodal round-trip, automation check/once/status, worker-entrypoint, and
mode-0600 configuration checks. Its SHA-256 was
`ce44e407b9e281dec6e61c4c3c85e22968475949a3f7c1ea6aa251e89b793d14`.

The v0.23 evidence-derived skill increment added mastery, CLI, and API cases
plus dashboard, agent-tool, proactive, automation, documentation, and prior-
capability regressions. Final hardening added future-evidence rejection and one
immediate transaction around active-state checking, bound enforcement,
insertion, and level recomputation. Ten focused mastery cases pass. The
hardened focused integration set passed 16 tests in 0.836 seconds, the adjacent
suite passed 75 tests in 13.024 seconds, and the complete suite passed all 206
tests in 28.122 seconds. Dashboard JavaScript syntax and Git whitespace checks
passed.

The first fresh no-index `0.23.0a1` wheel built and installed, but its smoke
used an invalid multimodal envelope fixture and is recorded as failed even
though later commands ran. A new fail-fast environment corrected the fixture.
Installed mastery create/evidence/reload/search, duplicate rejection,
proactive non-disclosure, multimodal canonical round-trip, worker help, and
automation-service checks passed. The corrected wheel SHA-256 was
`a24c71033c316c8fae274ac705b134e08678bf7a2af379b2cf952c856a0410a6`.
A subsequent fresh no-index wheel containing the final hardening installed and
passed installed mastery create/evidence/reload/read-only search, proactive
non-disclosure, version/status, mode-0600 configuration, automation
check/once/status, and worker-entrypoint gates. Its SHA-256 was
`43e225a2af529754067f0ebc14f181f992f4b8d45b447e6f0f6b22e6671dd1d8`.

The v0.24 AI System Draft increment added six focused compiler/store/CLI cases
and one API integration case. The corrected focused suite passed in 0.449
seconds, the 12-case adjacent draft/Blueprint/API suite passed in 2.381
seconds, and the initial full suite passed all 213 tests in 29.139 seconds.
After version and documentation alignment, the first documented tree passed all 213
tests in 28.180 seconds; dashboard JavaScript syntax and Git whitespace checks
passed. A corrected fresh offline `0.24.0a1` wheel installed without an index
and passed installed draft compilation/isolation/content-free evidence,
version/status, automation configuration, worker help, and mode-0600
configuration gates. Its SHA-256 was
`9c4a06f3994e564d6c96bfd92072e0dd4056f6a3b366afd4439e97a8446aaf6d`.

Release-state reconciliation recovered the exact v0.24 capability commit/tree,
backfilled the stale changelog, aligned the worker HTTP version marker, and
expanded the version-consistency contract across release documents and runtime
markers. The official pre-change gate passed all 213 tests in 28.658 seconds;
the reconciled tree passed all 213 tests in 28.252 seconds. The supplied
independent pytest run reported 213 passed tests, 173 passed subtests, and eight
warnings in approximately 26 seconds; pytest is not installed in this runtime,
so that presentation was not rerun locally. A first reconciliation wheel smoke
used a nonexistent singular model-status field and stopped after installation.
A new fresh fail-fast no-index gate passed version/status, draft protocol,
credential-absence, worker entrypoint, and automation-service checks. Its
SHA-256 was
`560a647978d36e796c93bdb57c2ffe879a1e3c1111a09173bc8fa75a83f45be6`.

The v0.25 AI System Implementation Plan increment added five focused
planner/store/CLI cases and one authenticated API integration case. The
focused planner/Blueprint/draft/API/documentation set passed all 21 tests in
6.724 seconds. The complete official suite passed all 219 tests in 29.397
seconds; dashboard JavaScript syntax and Git whitespace checks passed. A fresh
zero-dependency `0.25.0a1` wheel installed without an index and passed
deterministic plan preparation, approval-gated plan-only materialization,
version/status, no-source assertions, worker help, and automation-service
configuration. Its SHA-256 was
`76b0ac4d3776be18790f4120f09a1e717bb08bef015bbd8d9d09274c66a6bac0`.

The v0.26 Source Candidate increment added nine focused lifecycle, disclosure,
metadata, malformed-output, path/plan mismatch, review, static verification,
tamper, isolation, trace, and CLI cases. The focused suite passed 9/9 in 0.225
seconds. The first full run executed 228 tests in 28.326 seconds: all product
tests passed and the documentation contract alone caught BUILD_STATE still at
v0.25 during the version update. After reconciliation, the complete official
suite passed 228/228 in 28.524 seconds; dashboard JavaScript syntax and Git
whitespace checks passed. The final reconciled pre-checkpoint rerun passed
228/228 again in 28.360 seconds. A fresh zero-dependency `0.26.0a1` wheel installed
without an index and passed installed version/protocol/status, empty candidate
evidence, worker help, and automation-service configuration gates. Its SHA-256
was `e6ddca7b1241b4156b013e0b2276821b3d08f838621b76367c6c095a29c2acd3`.

The v0.27 Runtime Evaluation increment added seven focused methods covering
approval, contract/candidate/plan rejection, requested-to-terminal state
transitions, unavailable/authentication/replay/protocol/timeout/execution/
criteria failures, success, content-free persistence, trace linkage, signed
limit binding, evaluation-workspace isolation, and non-promotion. Corrected
focused tests pass 7/7 in 0.658 seconds; the adjacent evaluator/client/service
set passes 28/28 in 9.901 seconds. An authenticated API approval/listing test
passes independently in 0.832 seconds. The complete official suite passes
236/236 in 69.872 seconds, plus dashboard syntax and whitespace checks. A fresh
no-index `0.27.0a1` wheel passed installed status/protocol/listing and automation
checks; worker readiness correctly refused the absent signing key. Wheel
SHA-256: `d71a6e4dd3de0b49f72e17dacfdac1e36d81c6b240e9713b23ea4f23a9a58ab9`.

The v0.28 Controlled Source Promotion increment adds twelve focused methods
covering successful exact staging, separate approval, failed/missing/mismatched
evaluation and identity, stale approval, invalidation, supersession, source and
metadata tamper, traversal, overwrite, deterministic and concurrent replay,
partial-copy cleanup, digest failure, explicit reapproval/retry, lifecycle
guards, content-free evidence, CLI, and trace non-claims. One authenticated API
listing/refusal test is also added. The documented complete suite passed
249/249 in 24.766 seconds; the focused promotion suite passed 12/12 in 0.219
seconds and the runtime/worker suite passed 29/29 in 3.761 seconds. Dashboard
syntax, whitespace, tracked-tree audits, and a fresh no-index wheel/install
gate passed. The `0.28.0a1` wheel SHA-256 is
`ad897af2dff56f4613acc67ce3ab0ec42c328ed7ba64263ebed26e2fbd49ebab`.
The identical tree is published at GitHub commit
`efaad29824365655c28dcbc09880deec053be1ce`. SPARKLE CI run #54 passed Python
3.12, Python 3.13, worker-image, and automation-service on that commit.

The v0.29 Controlled Build increment adds eleven focused methods covering exact
promotion lineage, separate approval, digest identity, stale approval,
post-approval staged-tree tamper, deterministic archive contents, source
mutation during packaging, idempotent and concurrent replay, conflicting
requests, fail-closed artifact errors,
content-free evidence, strict contracts, and CLI behavior. One authenticated
HTTP/status wiring case is also added. The final reconciled complete suite
passed 261/261 in 25.412 seconds; the latest focused controlled-build suite passed
11/11 in 0.277 seconds; and the adjacent controlled-build/promotion/runtime/
external-worker/service suite passed 52/52 in 4.273 seconds. Dashboard syntax
passed. A fresh no-index `0.29.0a1` wheel passed installed version/status,
controlled-build protocol, empty evidence/eligibility, CLI, worker-help, and
automation checks. Wheel SHA-256:
`59b96669cb86285395664964698cc5204828297c22c3878b4836d2cde41727d7`.
The capability is published at commit
`0caff6c7ab1ffcf149edf052f1119a371a2ea326`, exact tree
`d3afe3ede6252996c6663f428839378cb9c8d0bf`. SPARKLE CI run #56
(`33545518032`) passed Python 3.12, Python 3.13, worker-image, and
automation-service on that commit.

The v0.30 Controlled Execution increment adds focused positive and negative
coverage for immutable-artifact execution through the real local worker service,
full identity and authorization binding, stale authorization, request replay,
artifact tampering and invalidation, safe extraction/path enforcement, signed
result identity/digest verification, distinct timeout/output/execution/result
failures, CLI evidence, cleanup, and the no-deployment boundary. Worker coverage
also exercises the strict v0.30 envelope, fixed resource/network policy, HMAC
authentication, replay storage, output-limit signaling, and executable
Bubblewrap hostile-canary preflight. Bubblewrap 0.9.0 is present locally but
its real preflight fails namespace setup; isolation evidence remains blocked,
not passed. The final local suite passed 269/269 in 26.130 seconds. Controlled
execution passed 8/8 in 0.484 seconds; runtime/worker passed 29/29 in 3.779
seconds; promotion passed 12/12 in 0.237 seconds; build passed 11/11 in 0.294
seconds. Dashboard JavaScript, whitespace, secret, generated-artifact, symlink,
and oversized-file audits passed. A fresh no-index `0.30.0a1` wheel installed
without dependencies and passed version/status, controlled-execution protocol,
empty execution evidence, no-deployment status, CLI, and worker-help checks.
Its SHA-256 is `e433bcea37ccbca85ca7bf5e8b3cbfb2e0f9835f448a1e12ad3f7561358f21a2`.
The capability is published at commit
`2a558379245ddfa29ec2eefcbef492327b59f885`, exact tree
`49b743e115c15152ebd5403168bcb73c6e4281b4`. SPARKLE CI run #58
(`33583190471`) passed Python 3.12, Python 3.13, worker-image, and
automation-service on that exact commit.

The v0.30 software-readiness continuation added exact execution-policy
validation, legal lifecycle-transition enforcement, configured worker-identity
pinning, timestamp ordering, richer content-free traces, single-execution
API/CLI inspection, explicit executed/isolated/verified/deployed dashboard
states, a read-only Bubblewrap artifact mount, seven named hostile canaries, an
explicit non-isolated test harness, a five-job software CI matrix, and a manual
infrastructure-dependent Level 3 workflow. The fresh suite passed 271/271;
execution 9/9; worker 16/16; external-worker/runtime 14/14; promotion 12/12;
build 11/11; API/CLI 38/38. Dashboard JavaScript and whitespace passed. The
fresh offline wheel installed and passed status, CLI failure handling, worker
help, and fail-closed acceptance-probe checks. Wheel SHA-256:
`d857f6e379400bfe9c1d1d404e4ecac099f37e17cbf18999310345a970f5b8c6`.
Secret, generated-artifact, symlink/path, and oversized-file audits passed.

Hardening commit `07084b8bd2f0709d2fbd4313489b650a3e5d05ef`, tree
`59d75d03e92996887e7b0014e313a380ae000080`, passed CI #60
(`33592882854`). Software-readiness commit
`f9f2860bce3714be6827bc6d21dadf9c0f09a14b`, tree
`7e58d44b92bf55695ce97660b5ad418c1986d4fe`, passed CI #61
(`33594016686`) with Python 3.12, Python 3.13, worker-image,
automation-service, and controlled-execution-software. The real local
Bubblewrap result remains `IsolationPreflightFailed`; all seven Level 3 canary
fields remain false and no isolation verification is claimed.

The free/local worker continuation added a credential-free
`SPARKLE-WORKER-HOST-DIAGNOSTIC/1` command, overwrite-protected development
TLS/HMAC bootstrap, externalized systemd configuration, and an offline wheel
installer that deliberately does not create credentials or start the service.
Fresh `make check` passed 273/273 in 31.233 seconds. Controlled execution passed
9/9; worker 18/18; external-worker/runtime 14/14; promotion 12/12; build 11/11;
and API/CLI 38/38. The TLS test accepted the explicitly trusted `localhost`
certificate and rejected both default trust and a wrong hostname. The local
diagnostic reported user, mount, and network namespaces unavailable,
`no_new_privs` available, and Bubblewrap `IsolationPreflightFailed`; all seven
canaries remained false and Level 3 remained blocked.

Dashboard JavaScript, whitespace, secret, generated-artifact, symlink/path, and
oversized-file audits passed. A fresh no-index/no-dependency `0.30.0a1` wheel
installed in a new virtual environment and passed version, status, worker help,
and credential-free diagnostic checks. Its SHA-256 was
`12f939cfd268243e19885e2809664ca966fc3cce8096a9a8d0717ea373ec83da`.
Commit `1e988eb96e66c59890ecd251c80b59a00532f3d2`, tree
`7849e2364f4b01ceeca3f27fcf04f46d21bca1a8`, passed CI #63
(`33605055320`) across all five jobs. This is software-platform evidence, not
Level 3 isolation evidence.

The provider-neutral model-registry continuation added external adapter
factories, exact factory-result identity checks, strict bounded records and
routing, recursive secret-value-field rejection, transactional failed
mutations, deterministic fallback, credential-free local-provider status, and
production modality-declaration enforcement. Explicit adapter injection remains
a test-only future-provider harness. The first focused run correctly exposed
four multimodal compatibility failures when that harness was treated as a
production record; no failing code was published. After preserving the explicit
test-only boundary, the focused model/config/multimodal suite passed 37/37.

Fresh `make check` passed 277/277 in 29.609 seconds. A corrected fail-fast fresh
no-index/no-dependency wheel gate passed installed version, status, default
MiniMax registry loading, adapter disclosure, and worker help. Its SHA-256 was
`c8f5bf81f985904a7103e441ae3b42df65d1a219e26d407eacc5b3b9d09c9f37`.
Dashboard JavaScript, whitespace, secret, generated-artifact, symlink/path, and
oversized-file audits passed. Commit
`ca6c483e1a6fc0b03b1a7b75f63dfd8f99589f6b`, tree
`20e75254d987cab7fa7b92c76c65bb2380bd43a0`, passed all five CI #65
(`33606707170`) jobs. No live MiniMax request was made.

The Nemotron continuation adds deterministic NVIDIA NIM request/response,
authentication refusal, tool-call, usage, retry, safe-error, and SSE tests. It
also covers configuration-versus-runtime health, capability/modality/tool/
stream filtering, latency and timeout policy, explicit fallback, retries,
missing-usage handling, content-free persistence, test-harness separation,
trace routing metadata, API, CLI, and status.

Fresh `make check` passed 290/290. Focused provider, registry, runtime,
orchestrator, API, CLI, and end-to-end coverage passed 61/61. Commit
`c7c1512d8b08b72df8330a769b8a2033037638e2` passed CI #67
(`33625302057`); commit
`5c7d5a06471663462cabbab4edf757adf5e4f1ad` passed CI #68
(`33626993684`). Both exact runs passed all five jobs. No live NVIDIA request
was made, and no Level 3 or deployment claim changed.
