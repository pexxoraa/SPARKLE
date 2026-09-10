# 0.30.0-alpha.1 verification report

Date: 2026-09-02 UTC

## 2026-09-07 foundation retrieval milestone

Inspected published `21c6f5797460650ce352c5e589bceab84a3443e4`, tree
`f09e534de2bdd5fa123cbc010b7e10322caa1ca1`, clean main, matching remote.
Fresh baseline: 297/297. Updated full suite: 304/304; focused retrieval/storage/
HTTP integration: 22/22. The first focused run caught whitespace loss during
chunk splitting (21/22); corrected before final verification.

Knowledge now has transactional FTS5 migration and maintenance, Unicode/title
ranking, bounded queries/chunks and attributable context. No semantic retrieval,
live NVIDIA, autonomous agent quality or Level 3 claim is made. The
[46-category foundation audit](FOUNDATION_AUDIT.md) supersedes the unsupported
93% completion estimate. Version remains unchanged. Level 3 stays BLOCKED and
deployment FROZEN; prior host Bubblewrap evidence is user-reported, not rerun.

## Controlled immutable-artifact execution

- `SPARKLE-AI-SYSTEM-CONTROLLED-EXECUTION/1` is implemented after controlled
  build. A successful build is insufficient authorization. A separate one-use,
  expiring authorization binds build, artifact ID/digest, promotion, candidate,
  implementation plan, successful evaluation, mode, timeout, output limit,
  actor, and origin.
- The controller accepts no source-tree or staging path. It reloads the
  authoritative chain, rejects invalidated/superseded artifacts, opens the ZIP
  as a stable regular file, verifies record/digest/manifest/entries, safely
  extracts to an ephemeral workspace, and rechecks the archive immediately
  before submission.
- The existing worker boundary is extended, not duplicated. The v0.30 envelope
  reuses HMAC authentication/freshness, strict schemas, replay storage, fixed
  unittest execution, timeout/process-group termination, output limits,
  minimal environment, POSIX rlimits, and cleanup. Its signed result binds the
  execution/request and artifact lineage, worker ID, status, output digest,
  canonical result digest, timestamps, and isolation evidence.
- API, CLI, status, dashboard, and content-free traces distinguish BUILD,
  EXECUTION, VERIFICATION, and DEPLOYMENT. A verified execution never publishes,
  deploys, replaces production, or claims production state.

## Evidence levels

- Level 1 — contract implemented: **yes**.
- Level 2 — genuine local worker execution: **yes**, through the real service,
  HMAC request/response path, fixed process executor, result verifier, and
  ephemeral cleanup. This is functional worker evidence, not hostile isolation.
- Level 3 — independently executable isolation evidence: **blocked on this
  host**. Bubblewrap 0.9.0 is installed, but the real hostile-canary preflight
  returns `IsolationPreflightFailed` because namespace setup is denied. The
  preflight safely tests host read/write, process-root view, secret environment,
  outbound network, and workspace boundary. No isolation pass is claimed.

The final local suite passed 269/269 in 26.130 seconds. Controlled execution
passed 8/8 in 0.484 seconds; runtime/worker 29/29 in 3.779 seconds; promotion
12/12 in 0.237 seconds; build 11/11 in 0.294 seconds. Dashboard JavaScript,
whitespace, secret, generated-artifact, symlink, and oversized-file audits
passed. A fresh no-index `0.30.0a1` wheel installed without dependencies and
passed version/status, controlled-execution protocol, empty execution evidence,
no-deployment status, CLI, and worker-help checks. Wheel SHA-256:
`e433bcea37ccbca85ca7bf5e8b3cbfb2e0f9835f448a1e12ad3f7561358f21a2`.
The capability is published at commit
`2a558379245ddfa29ec2eefcbef492327b59f885`, exact tree
`49b743e115c15152ebd5403168bcb73c6e4281b4`, as a strict non-force descendant
of v0.29 HEAD `6ca5be596b78eaaa3dec251953577b9547c59e73`.
GitHub CI run #58 (`33583190471`) passed Python 3.12, Python 3.13,
worker-image, and automation-service on that exact capability commit.

## Software-readiness continuation

Without changing the version or claiming Level 3, two later non-force commits
completed the infrastructure-independent boundary. Commit
`07084b8bd2f0709d2fbd4313489b650a3e5d05ef`, tree
`59d75d03e92996887e7b0014e313a380ae000080`, binds the exact execution policy,
enforces legal lifecycle transitions, pins the expected worker identity, and
expands content-free traces. CI #60 (`33592882854`) passed all four then-current
jobs. Commit `f9f2860bce3714be6827bc6d21dadf9c0f09a14b`, tree
`7e58d44b92bf55695ce97660b5ad418c1986d4fe`, makes the artifact mount read-only,
signs seven named canary outcomes, validates timestamps and worker identity,
adds status/result API and CLI inspection, separates dashboard states, adds an
explicit non-isolated test harness, and prepares a manual external acceptance
workflow. CI #61 (`33594016686`) passed five jobs including the dedicated
controlled-execution software job.

Fresh evidence is 271/271 overall, 9/9 controlled execution, 16/16 worker,
14/14 external-worker/runtime, 12/12 promotion, 11/11 build, and 38/38 API/CLI.
Dashboard JavaScript, whitespace, offline packaging/install, secret,
generated-artifact, symlink/path, and oversized-file audits passed. The wheel
SHA-256 is `d857f6e379400bfe9c1d1d404e4ecac099f37e17cbf18999310345a970f5b8c6`.
The real local Bubblewrap preflight still fails closed and all seven canary
fields are false. Level 3 remains BLOCKED; deployment remains frozen.

## Free/local worker platform continuation

Commit `1e988eb96e66c59890ecd251c80b59a00532f3d2`, tree
`7849e2364f4b01ceeca3f27fcf04f46d21bca1a8`, adds a credential-free host
diagnostic, reproducible development-only TLS and file-injected HMAC bootstrap,
externalized systemd configuration, and an offline wheel installer that never
creates credentials or starts the worker. The execution protocol and
Bubblewrap preflight were not weakened or redesigned.

Fresh evidence is 273/273 overall, 9/9 controlled execution, 18/18 worker,
14/14 external-worker/runtime, 12/12 promotion, 11/11 build, and 38/38 API/CLI.
Development TLS validation passed; an untrusted certificate and wrong hostname
were rejected. Dashboard JavaScript, whitespace, offline packaging/install,
secret, generated-artifact, symlink/path, and oversized-file audits passed. The
fresh wheel SHA-256 is
`12f939cfd268243e19885e2809664ca966fc3cce8096a9a8d0717ea373ec83da`.
CI #63 (`33605055320`) passed Python 3.12, Python 3.13, worker-image,
automation-service, and controlled-execution-software on that exact commit.

The actual host diagnostic recorded unavailable user, mount, and network
namespaces, available `no_new_privs`, Bubblewrap `IsolationPreflightFailed`,
and seven false canaries. Level 3 therefore remains **BLOCKED**. No cloud
infrastructure is required for continued software development and deployment
remains frozen.

## Provider-neutral model-registry hardening

Commit `ca6c483e1a6fc0b03b1a7b75f63dfd8f99589f6b`, tree
`20e75254d987cab7fa7b92c76c65bb2380bd43a0`, removes the core registry's
closed adapter-factory assumption. Integrators can supply provider factories
without changing orchestration. Factory results are bound to configured
provider/model identity and declared modalities; credential-free local
providers are represented correctly.

Registry loading now rejects invalid or duplicate identities, roles,
modalities, secret references, routing targets, capability-role mismatches,
non-boolean state, and recursively named secret-value fields. Failed disable
and remove operations roll back instead of leaving invalid in-memory state.
Fallback selection is deterministic. Explicit adapter injection remains a
test-only override for future-provider simulations and is never configuration
loadable.

Fresh evidence is 277/277 overall and 37/37 focused
model/config/MiniMax/multimodal tests. A corrected fail-fast offline wheel gate
passed; its SHA-256 is
`c8f5bf81f985904a7103e441ae3b42df65d1a219e26d407eacc5b3b9d09c9f37`.
Security, artifact, symlink/path, size, whitespace, and dashboard checks passed.
CI #65 (`33606707170`) passed all five jobs on the exact capability commit.
MiniMax was exercised only through deterministic HTTP doubles; no live-provider
verification is claimed. Level 3 remains blocked and deployment remains frozen.

## NVIDIA Nemotron and provider-neutral model runtime

NVIDIA adapter commit `c7c1512d8b08b72df8330a769b8a2033037638e2`,
tree `0f5b61f9830f8f456608e9f7b598cb9d53c1364e`, makes
`nvidia/nemotron-3.5-lightning-30b-a3b` the primary configured model.
MiniMax remains present as a disabled legacy record. The adapter normalizes NIM
Chat Completions requests, responses, SSE text, tool calls, provider usage,
bounded errors, retries, and bearer authentication without adding an SDK
dependency. CI #67 (`33625302057`) passed all five jobs.

Model runtime commit `5c7d5a06471663462cabbab4edf757adf5e4f1ad`,
tree `3e36794da7776b62add3635c6de69eccbece622e`, adds
evidence-based health, provider-neutral request policy, explicit fallback, and
content-free request/usage evidence. Configuration alone is not healthy.
Injected adapters are marked test harnesses and cannot satisfy live-provider
verification. Missing usage remains unknown. CI #68 (`33626993684`) passed
Python 3.12, Python 3.13, worker-image, automation-service, and
controlled-execution-software.

Fresh local evidence is 290/290 overall and 61/61 focused
model/registry/provider/API/CLI/system tests. Live Nemotron is **NOT VERIFIED**
because no NVIDIA credential was available. Level 3 remains **BLOCKED** and
deployment remains **FROZEN**.

## Foundation audit and bounded interaction contracts

Commit `acaf61936e305da104bcb7ccaa37086273f880a0`, tree
`e18e0bc8bb2ea7edfabc5661e075ff732e4c71f4`, adds provider-neutral browser and
computer contracts without enabling live control. Browser requests require
credential-free HTTPS on port 443, exact host allowlists, bounded time/output,
and final-destination revalidation. Computer actions are a closed bounded set
with no shell action. Disabled defaults fail closed and injected adapters are
always labeled test harnesses. The dashboard now exposes active model, health,
routing reason, fallback, latency, attempts, and reported-or-unknown usage.

Fresh final evidence is 295/295 overall and 70/70 focused
Nemotron/model/interaction/API/CLI tests. Dashboard JavaScript, whitespace,
token-shaped secret, symlink, and oversized-file audits passed. A fresh offline
wheel install passed; SHA-256 is
`b3f7f94fc9e73afb90828e5239780b6287af17b8469ade1e06392620e3fe817c`.
CI #69 (`33629696189`) passed Python 3.12, Python 3.13, worker-image,
automation-service, and controlled-execution-software on the exact commit.

Live Nemotron remains **NOT VERIFIED**, live browser/computer/voice remains
unavailable, Level 3 remains **BLOCKED**, and deployment remains **FROZEN**.

## Promotion-bound controlled build

- Added `SPARKLE-AI-SYSTEM-CONTROLLED-BUILD/1` as the first deterministic
  consumer of a completed controlled source promotion. It cannot accept an
  arbitrary application workspace or unpromoted candidate.
- A separate expiring approval binds the exact promotion and destination
  digest to the actor and request origin. Approval is consumed atomically when
  the build enters its `building` state.
- Preconditions re-read promotion and candidate evidence, reload the staged
  tree, revalidate exact declared paths and content digest, and reject missing,
  incomplete, mismatched, stale, tampered, replay-conflicting, or concurrent
  requests before reporting success.
- The build creates a deterministic content-addressed ZIP with a canonical
  manifest and fixed entry metadata. The persisted archive is re-read and
  verified against its recorded SHA-256 identity.
- Content-free approval, request, lifecycle, eligibility, trace, CLI,
  authenticated API, status, and dashboard surfaces record no source content,
  credentials, or secrets.
- The boundary does not import or execute promoted source, publish an artifact,
  deploy a target, or modify production source.

## v0.29 local verification state

- The final reconciled complete official suite passed 261/261 in 25.412 seconds.
- The focused controlled-build suite passed 11/11 in 0.277 seconds. Its cases
  cover exact lineage, approval, identity, stale approval, staged-tree tamper,
  deterministic archive contents, source mutation during packaging, concurrent
  replay, conflict refusal, fail-closed artifact errors, content-free evidence,
  and CLI behavior.
- The authenticated HTTP/status integration case passed inside the complete
  suite. The adjacent controlled-build/promotion/runtime/external-worker/service
  suite passed 52/52 in 4.273 seconds, and dashboard JavaScript syntax passed.
- A fresh no-index `0.29.0a1` wheel installed without dependencies and passed
  version/status, controlled-build protocol, empty evidence/eligibility, CLI,
  worker-help, and automation-service checks. Wheel SHA-256:
  `59b96669cb86285395664964698cc5204828297c22c3878b4836d2cde41727d7`.
- The capability is published as normal non-force descendant commit
  `0caff6c7ab1ffcf149edf052f1119a371a2ea326`, tree
  `d3afe3ede6252996c6663f428839378cb9c8d0bf`, with verified v0.28 HEAD
  `5bd7059563cca0a844ff583dc358e88539290405` as its sole parent.
- SPARKLE CI run #56 (`33545518032`) completed successfully for the published
  capability. Python 3.12, Python 3.13, worker-image, and automation-service all
  passed.

## Inherited v0.28 controlled source promotion

- Added `SPARKLE-AI-SYSTEM-SOURCE-PROMOTION/1` as a provider-neutral stage
  after successful runtime evaluation. Promotion approval is separate from
  candidate approval and is bound to the exact candidate/content digest,
  implementation plan/digest, evaluation/contract digest, actor, origin, and
  expiry.
- Preconditions re-read authoritative stores and reject missing, unapproved,
  invalidated, superseded, tampered, mismatched, failed, stale, replayed, or
  conflicting identities. Runtime success never creates promotion approval.
- Exact candidate text is copied only into
  `promotion_environment/staging/<system-name>`. The writer uses a private
  lock, exclusive files, a temporary directory, digest verification before and
  after atomic rename, no overwrite, and rollback of materialization it created
  on failure.
- Content-free evidence records promotion, request, candidate, plan,
  evaluation, approval, actor/origin, source/destination digest, resulting
  promoted-artifact identity, lifecycle, trace, timestamps, and bounded failure
  class. It stores no source, outputs, review notes, credentials, or secrets.
- Identical request replay is deterministic. Concurrent replay produces one
  promotion and destination. Failed materialization consumes its approval and
  requires a new explicit approval before a clean retry.
- CLI and authenticated API operations expose separate approval, request,
  exclusion, status, and result boundaries. Dashboard evidence distinguishes
  ineligible, awaiting approval, approval recorded, requested, promoting,
  promoted, rejected, and failed states without claiming build or deployment.

## Published v0.28 verification evidence

- The documented complete regression passed 249/249 in 24.766 seconds. The
  focused controlled-promotion suite passed 12/12 in 0.219 seconds, and the
  runtime/external-worker/worker-service suite passed 29/29 in 3.761 seconds.
- Dashboard JavaScript syntax and Git whitespace checks passed. The tracked-tree
  audit found no secrets, generated databases, wheels, caches, virtual
  environments, temporary files, unexpected binaries, symlinks, or oversized
  files. The documented credential example is a non-secret placeholder.
- A fresh no-index `0.28.0a1` wheel built and installed without dependencies.
  Installed version/status, promotion protocol, empty promotion
  evidence/eligibility, promotion CLI, worker entrypoint, and automation checks
  passed. Wheel SHA-256:
  `ad897af2dff56f4613acc67ce3ab0ec42c328ed7ba64263ebed26e2fbd49ebab`.
- Local content checkpoint `4a886ce55825cd42e3807ba34933271204c64103`
  and GitHub-published commit
  `efaad29824365655c28dcbc09880deec053be1ce` have the identical verified tree
  `21008f91275ea50a4a7d366acdd81871e7aaeb2f`. The SHA differs only because the
  authenticated GitHub commit API assigned the remote commit metadata; both
  commits have published v0.27 HEAD `8a320691a29c43ade27a8514a7361dc7ec502cbb`
  as their sole parent.
- Private GitHub `main` was advanced normally and non-force to the published
  v0.28 commit. Post-publication Git data verification confirmed the exact
  parent and tree.
- SPARKLE CI run #54 (`33466540615`) completed successfully for the published
  commit. Python 3.12, Python 3.13, worker-image, and automation-service all
  passed.
- Completion remains 93%. Controlled staging promotion is remotely published
  and CI verified; it does not change any external-worker/isolation or live
  provider limitation.

## Honest limits

- Controlled build stops at a verified immutable source-bundle artifact. It
  does not import or execute promoted source, publish the artifact, deploy a
  target, replace production source, or modify application workspaces.
- No named external worker endpoint or signing key is configured. No genuine
  external evaluation or executable Bubblewrap/hostile-canary isolation proof
  exists. `isolation_verified` remains false.
- Live MiniMax verification remains blocked by the intentionally absent key.

---

# 0.27.0-alpha.1 verification report

Date: 2026-08-31 UTC

## Repository reconciliation and publication

- Original local checkpoint:
  `e2ebfd454bf0b1b194a453b716628e34d4407235`; original tree:
  `b5f94e9366263fd0f4f9a2abe07220b61c076b47`.
- Remote `main` before replay:
  `78032c1fbbaeab7253421f8cdde6e70da5d6f97c`. Its tree matched the local
  v0.23 capability tree, but the complete remote and local commit histories had
  no common ancestor.
- The seven intended local commits following the content-equivalent v0.23 tree
  were replayed without conflicts onto remote `78032c1`. No force push,
  unrelated-history merge, remote deletion, or history replacement occurred.
- Published replayed v0.27 capability checkpoint:
  `76aec2e439e82d9766c0dccf4ca3487c54288e3c`; published capability tree:
  `b5f94e9366263fd0f4f9a2abe07220b61c076b47`. The original local commit SHA
  was not published and remains preserved locally as `audit/original-v0.27`.
- Post-replay official verification passed 236/236 tests in 35.407 seconds.
  The corrected focused runtime/external-worker/service command passed 29/29
  tests in 9.534 seconds. Dashboard JavaScript syntax, Git whitespace, tracked
  artifact/binary/secret-signature audits, and version checks passed.
- A fresh no-index `0.27.0a1` wheel installed and passed version, status,
  empty runtime-evaluation protocol, worker entrypoint, and automation-service
  checks. Its SHA-256 is
  `7622f86967efb2429d55a4576653c1c0729e46c4f9c6e55f917cc58feca688b4`.
- SPARKLE CI run #50 (`33398943322`) for `76aec2e` completed successfully.
  `test (3.12)`, `test (3.13)`, `worker-image`, and `automation-service` all
  passed. This proves remote publication and CI for the replayed capability
  commit, not live MiniMax availability or executable Bubblewrap isolation.
- Documentation checkpoint `eb707aaf28602f2a7ec69cb5dedf7cc6375d319f`,
  tree `03232c1aeba537f21d9865fa03b0c7f76f6c47f0`, was published as a normal
  descendant. SPARKLE CI run #51 (`33399507776`) also passed the Python 3.12,
  Python 3.13, worker-image, and automation-service jobs.
- Two stopped local packaging harness attempts are not release evidence: one
  expected a bare array instead of the documented runtime-list envelope; the
  next used positional `check` instead of `sparkle-automations --check`.
  The fresh successful gate above supersedes both.

## Executed evidence

- Added `SPARKLE-AI-SYSTEM-RUNTIME-EVALUATION/1` with exact candidate/plan
  identity, requested capabilities, fixed runtime requirements, bounded input,
  expected behavior, limits, criteria, harness files, and result format.
- Missing approval creates no request. Approved invalid contracts/candidates
  receive unique evaluation/trace IDs and a distinct `rejected` result. Valid
  requests persist requested, queued, submitted, running, completed, and
  evaluated events; start, timeout, unavailable-worker, protocol, execution,
  and criteria failures remain separate.
- Evaluator-owned bundles are outside candidate, application, production,
  artifact, and deployment trees. Submission reuses the existing HTTPS/HMAC
  client and binds contract timeout/output limits into the signed body.
- Persisted results and traces are content-free. They retain identifiers,
  result metadata/digests, criterion booleans, worker/runtime labels,
  response-verification state, and honest false production/promotion/deployment
  flags. Worker sandbox fields do not establish isolation verification.
- The first focused run executed six methods but produced eight errors because
  the new trace finish call omitted mandatory model/provider labels. After the
  integration fix, one assertion used a positional trace limit and errored.
  Corrected focused runtime tests pass 6/6 in 0.620 seconds.
- The runtime evaluator plus existing external-worker client/service suite
  passes 28/28 in 9.901 seconds, including request/response authentication,
  tamper rejection, replay conflict, timeout, executor failure, worker
  unavailability, criteria failure, success, persistence, trace, and isolation
  non-claims. This is deterministic contract/integration evidence, not a live
  named isolated-worker run.
- The initial complete official suite passed 234/234 in 70.513 seconds. After
  adding the authenticated API approval/listing regression, the suite passed
  235/235 in 70.275 seconds. Dashboard JavaScript syntax and Git whitespace
  checks passed.
- A final candidate-symlink isolation regression passed and the complete suite
  then passed 236/236 in 69.872 seconds. The focused runtime set passes 7/7 in
  0.658 seconds.
- A fresh no-index `0.27.0a1` wheel built and installed. Installed
  version/protocol/status, empty content-free evaluation listing, and automation
  service checks passed. Worker readiness refused because
  `SPARKLE_WORKER_SIGNING_KEY` is intentionally absent; no connection was
  attempted. Wheel SHA-256 is
  `d71a6e4dd3de0b49f72e17dacfdac1e36d81c6b240e9713b23ea4f23a9a58ab9`.

## Honest limits

- No endpoint or signing key is configured in this build process. No live
  external worker was called.
- Bubblewrap namespace preflight remains denied on this executor. No hostile
  canary has produced executable filesystem/network isolation evidence.
- `runtime_verified` is contract/result evidence; `isolation_verified` remains
  false. Production verification, source promotion, publication, and deployment
  are unimplemented and never inferred.
- Replayed v0.27 capability publication and four-job remote CI are verified.
  Completion remains 93%.

---

# 0.26.0-alpha.1 verification report

Date: 2026-08-31 UTC

## Executed evidence

- `SPARKLE-AI-SYSTEM-SOURCE-CANDIDATE/1` consumes only a materialized plan
  whose review is explicitly approved, revalidates its requirements/digest,
  and generates exact bounded JSON through the existing model router and
  isolated no-context/no-tool profile.
- Provider/model/registry identity, task, timestamps, related plan/candidate,
  generated path labels, and generation status are stored in a separate
  disclosure record. Disclosure and generation each require approval; source
  and credentials are absent from disclosure evidence.
- Candidate files are restricted to plan-declared paths, 1–20 files, 64,000
  bytes per file, and 256,000 bytes total. They are written only beneath
  `candidate_environment/source_candidates`, with read-only files and a
  canonical digest-bound manifest; no application or production source is
  modified.
- The state machine distinguishes generation, human-review-required, reviewed
  or rejected, static-verification failed or passed, and approved. Generated
  source cannot skip human review or static verification, and no operation
  automatically claims review or approval.
- Static verification validates isolation, paths, manifests, byte/file/overall
  digests, formatting, credential patterns, Python syntax/imports/dependencies
  and unsafe AST patterns, JSON configuration, and JavaScript syntax where
  Node is available. Candidate Python is never imported or executed.
- Nine focused tests passed in 0.225 seconds. They cover disclosure approval,
  missing/incorrect provider metadata, valid lifecycle, automatic-approval
  refusal, malformed JSON, invalid paths, plan mismatch, human rejection,
  static success/failure, symlink isolation, manifest-digest tampering,
  content-free trace lifecycle, CLI gates, and production-source isolation.
- The first full documented-tree run executed 228 tests in 28.326 seconds. All
  product tests passed; the sole failure was the cross-surface documentation
  check observing BUILD_STATE at v0.25 after package metadata had advanced to
  v0.26. BUILD_STATE was then reconciled. Final exact-tree and installed-wheel
  evidence are recorded only after those commands execute successfully.
- The corrected documented tree passed 228/228 official tests in 28.524
  seconds; dashboard JavaScript syntax and Git whitespace checks passed.
- The final reconciled pre-checkpoint tree passed 228/228 again in 28.360
  seconds; dashboard JavaScript syntax and Git whitespace checks remained clean.
- A fresh no-index `0.26.0a1` wheel built and installed with no dependencies.
  Installed version/protocol/status and empty content-free candidate listing
  passed, as did worker help and automation-service configuration checks. The
  wheel SHA-256 is
  `e6ddca7b1241b4156b013e0b2276821b3d08f838621b76367c6c095a29c2acd3`.

## Honest limits

- Deterministic injected-adapter tests do not establish live MiniMax semantic
  quality or provider availability.
- `STATICALLY VERIFIED` does not mean runtime tested, semantically correct,
  isolated by the external worker, production-ready, published, or deployed.
- Approval preserves a candidate in its isolated workspace; it does not copy,
  merge, package, execute, publish, or deploy source.
- Remote v0.26 publication and CI have not occurred. Completion remains 93%.

---

# 0.25.0-alpha.1 verification report

Date: 2026-08-31 UTC

## Executed evidence

- `SPARKLE-AI-SYSTEM-IMPLEMENTATION-PLAN/1` revalidates exact structured AI
  system requirements through the existing Blueprint builder, then derives a
  deterministic provider-neutral plan without calling a model.
- Plans contain capability/modality requirements rather than provider or model
  identities, bounded unique proposed source/evaluation paths, an ordered
  acyclic work sequence, declared evaluation contracts, and an explicitly
  unverified deployment review.
- Preparation is non-mutating. Separate approval permits only the canonical
  `SPARKLE_IMPLEMENTATION_PLAN.json` manifest to be added to the bounded
  application workspace with overwrite protection. No proposed source or test
  file is generated.
- The separate evidence store retains the latest 1,000 attempts and returns at
  most 100. It contains system name, Blueprint/plan digests, plan size, status,
  workspace build link, timestamps, and safe error type—not purpose, workflow,
  criteria, plan content, or source.
- Five focused planner/store/CLI cases and an authenticated API integration
  case cover deterministic preparation, provider neutrality, path uniqueness,
  digest scope, approval, plan-only materialization into an existing Blueprint
  workspace, content-free evidence, invalid input, duplicate refusal,
  retention, API/CLI, system status, and dashboard integration.
- The focused planner/Blueprint/draft/API/documentation set passed all 21 tests
  in 6.724 seconds. The complete official gate passed all 219 tests in 29.397
  seconds; dashboard JavaScript syntax and Git whitespace checks passed.
- A fresh zero-dependency `0.25.0a1` wheel built and installed without an
  index. Installed deterministic preparation and approved materialization
  produced only `SPARKLE_IMPLEMENTATION_PLAN.json`, left every generated-source
  and execution claim false, created no source directory, updated status, and
  passed worker and automation-service entrypoint checks. Its SHA-256 is
  `76b0ac4d3776be18790f4120f09a1e717bb08bef015bbd8d9d09274c66a6bac0`.
- Local capability commit
  `2b98f25468a48bed992fb30fc187288f0de63705` has tree
  `a74ff1148a00f543ca923ebffaa6258ab70b5ca3` over the reconciled v0.24
  checkpoint `59c1396caa37b5a474a14d6c7ba9f7ffe1da05c0`. This is local Git evidence;
  the commit has not been sent to GitHub and has no remote CI run.

## Honest limits

- The plan is a statically derived proposal that still requires human review.
  Materializing it does not mark review complete or approve later generation.
- No implementation source or executable test is generated. No runtime
  evaluation, package installation, external worker job, or deployment runs.
- Live MiniMax semantic verification and remote v0.25 publication/CI have not
  occurred. Completion remains 93%.

---

# 0.24.0-alpha.1 verification report

Date: 2026-08-31 UTC

## Executed evidence

- Release-state reconciliation confirmed that local commit
  `e5895087e082287df197f4e5c27b925f6dbe4a4d` has tree
  `8b0d76e414bd6e8bc547e3ad649e74b58a1b409a` and contains the complete
  v0.24 draft-compiler increment described below. The repository's official
  pre-reconciliation `make check` rerun passed all 213 tests in 28.658 seconds;
  dashboard JavaScript syntax and Git whitespace checks also passed.
- The supplied independent pytest evidence reports 213 passed tests, 173
  passed subtests, and eight pytest warnings in approximately 26 seconds. This
  runtime does not include pytest, so that display was not rerun here and is
  recorded as independently supplied rather than local command evidence.
- A tracked-tree audit found no generated archives, wheels, SQLite databases,
  bytecode, virtual environments, symlinks, `.env` files, or known live-secret
  prefixes. Ignored local build/cache directories are not release artifacts and
  are excluded from Git. `CHANGELOG.md` was the only stale release surface; it
  stopped at v0.9 and is now backfilled through v0.24 with a regression check
  that binds its first entry to package metadata.
- Read-only GitHub evidence during reconciliation showed private `main` still
  at `78032c1fbbaeab7253421f8cdde6e70da5d6f97c`. GitHub did not contain
  `e5895087e082287df197f4e5c27b925f6dbe4a4d` and reported no workflow runs
  for that SHA. No remote publication or v0.24 CI is claimed.
- After the reconciliation changes, the complete official gate passed all 213
  tests in 28.252 seconds. A first fresh wheel smoke incorrectly addressed a
  nonexistent singular `status["model"]` field and stopped with `KeyError`
  after the wheel had built and installed; this was a harness failure, not a
  product assertion. A new fresh, fail-fast, no-index gate installed
  `sparkle-personal-ai==0.24.0a1`, verified version/status and the draft
  protocol with the live credential absent, and passed the installed worker
  help and automation-service configuration checks. The reconciled wheel
  SHA-256 is
  `560a647978d36e796c93bdb57c2ffe879a1e3c1111a09173bc8fa75a83f45be6`.

- `SPARKLE-AI-SYSTEM-DRAFT/1` accepts 20–20,000 bytes of natural-language AI
  system requirements only with explicit operator approval, because the text
  is disclosed to the configured model provider.
- The current provider-neutral vocabulary is derived from the existing model,
  agent, tool, and artifact registries. The compiler uses the Application
  Builder through the common orchestrator's isolated evaluation profile, which
  rejects history, user identity, additional context, memory/knowledge access,
  and tools. A model tool request fails closed.
- Generated text must be one exact JSON object. Markdown fences, duplicate
  keys, extra/provider-specific fields, unknown or inaccessible tools, invalid
  capability/modality routes, and all existing Blueprint schema/size failures
  are rejected before a draft is returned. Successful JSON is independently
  passed through the complete `SPARKLE-AI-SYSTEM-BLUEPRINT/1` validator.
- The latest 1,000 attempts persist separately. Evidence retains only status,
  request byte count, response digest/length, bounded provider/model labels,
  trace ID, and safe error type. It excludes natural-language requirements,
  generated JSON, memory/knowledge context, and exception messages. API list
  results are bounded to 100.
- CLI, authenticated HTTP API, system status, and dashboard metrics expose the
  new boundary. Successful output explicitly reports that semantic correctness,
  live-provider verification, runtime evaluation, source generation, and
  external deployment are false or absent.
- The first focused command used a nonexistent `.venv` and executed no tests;
  the second lacked `PYTHONPATH=src` and executed only an import failure. The
  first valid six-case run executed but produced five setup errors because the
  injected test adapter omitted the abstract `health()` method. After that was
  added, one case failed because the fixture used an unsupported memory
  category. The corrected six-case suite passed in 0.449 seconds.
- The 12-case draft/Blueprint/API adjacent suite passed in 2.381 seconds. The
  initial complete suite passed all 213 tests in 29.139 seconds. After version
  and documentation updates, the first version-aligned documented tree passed all 213 tests
  in 28.180 seconds; dashboard JavaScript syntax and Git whitespace checks
  passed.
- Before reconciliation, the first wheel command stopped before building because this runtime's
  `build` module has no executable `__main__`. A `pip wheel` retry was stopped
  by the runtime before execution because it could consider the network. The
  offline retry built successfully but its gate expected the wrong distribution
  filename and therefore installed nothing. The next fresh wheel installed and
  its compiler smoke passed, then the gate stopped on the incorrect executable
  name `sparkle-automation`. The corrected fresh no-index gate used the declared
  `sparkle-automations` entrypoint and passed installed draft compilation,
  isolation/evidence assertions, version/status, automation configuration
  check, worker help, and mode-0600 configuration checks. The final wheel
  SHA-256 was
  `9c4a06f3994e564d6c96bfd92072e0dd4056f6a3b366afd4439e97a8446aaf6d`.

## Honest limits

- Tests used a deterministic injected adapter. No live MiniMax conversion ran,
  so natural-language semantic fidelity is not live-provider verified.
- A statically valid draft is not proof that it captures the user's intent.
  Human review remains required before approved workspace materialization.
- The boundary generates structured requirements and a Blueprint, not source
  code, semantic runtime evaluation, a working application, or a deployment.
- Publication and four-job v0.24 CI evidence remain pending.
- Private GitHub publication is paused because the repository tool requires
  explicit approval for the project-file payload and destination. No bypass was
  attempted.

---

# 0.23.0-alpha.1 verification report

Date: 2026-08-31 UTC

## Executed evidence

- `SPARKLE-SKILL/1` validates bounded skill targets and question, exercise,
  test, project, implementation, and independent-problem-solving evidence.
  Levels 0–6 are recomputed from verified counts, type diversity, applied
  evidence, and average score; no interface can write the current level.
- Canonical evidence digests reject exact replay. Review found and closed this
  integrity gap before broad regression; it did not produce a failed test run.
- Ten focused mastery cases pass: promotion through level 6, unverified
  evidence exclusion, duplicate rejection, validation, timezone normalization,
  future-evidence rejection, active/evidence bounds, optimistic
  metadata/archive behavior, least-privilege agent reads, content-free
  proactive evidence, and matching conditional-notification execution.
- Final review placed active-state checking, evidence-bound enforcement,
  insertion, and level recomputation in one immediate transaction so a
  concurrent archive or append cannot cross a checked boundary. Read results
  recompute the public level from evidence, and occurrence times more than five
  minutes in the future fail before persistence.
- The hardened focused mastery/CLI/API/documentation set passed all 16 tests in
  0.836 seconds. The adjacent storage/automation/agent/CLI/API/system set passed
  all 75 tests in 13.024 seconds. The complete suite passed all 206 tests in
  28.122 seconds; dashboard JavaScript syntax and Git whitespace checks passed.
- The first fresh no-index wheel built and installed, and its mastery checks
  passed, but the combined smoke then supplied an unsupported envelope-level
  `metadata` field to the multimodal fixture. Because that shell did not fail
  fast, later entrypoint checks ran; the gate is recorded as failed, not passed.
  A new fail-fast environment used the actual `SPARKLE-CONTENT/1` constructor.
  Installed mastery create/evidence/reload/search, duplicate refusal,
  proactive non-disclosure, multimodal canonical round-trip, worker help, and
  automation-service checks passed. The corrected wheel SHA-256 was
  `a24c71033c316c8fae274ac705b134e08678bf7a2af379b2cf952c856a0410a6`.
- A subsequent fresh no-index wheel containing the final transactional and
  future-evidence safeguards installed as `0.23.0a1`. Installed
  create/evidence/reload/read-only-agent-search, proactive non-disclosure,
  version/status, mode-0600 configuration, automation check/once/status, and
  worker entrypoint gates passed. Its SHA-256 was
  `43e225a2af529754067f0ebc14f181f992f4b8d45b447e6f0f6b22e6671dd1d8`.

## Honest limits

- Evidence verification is a trusted authenticated user/API assertion. SPARKLE
  does not independently authenticate external artifacts or issue a
  professional certification.
- Deterministic mastery accounting does not establish live-provider teaching
  quality, semantic assessment quality, or external learning-platform sync.
- The initial capability tree was published and passed CI. The subsequent
  transaction/future-evidence hardening exact tree remains local and unpublished.

## GitHub publication and CI

Result: PARTIAL — private repository `pexxoraa/SPARKLE` received capability
commit `78032c1fbbaeab7253421f8cdde6e70da5d6f97c` on `main` by a non-force
fast-forward from the verified v0.22 checkpoint. Its tree
`9bd67ce08f5bfb9dd3b73b9cd30ddcd6881cbebe` exactly matches the locally tested
pre-hardening capability commit tree.

SPARKLE CI run #49 (`33348526415`) completed successfully. All required jobs
passed: `test (3.12)`, `test (3.13)`, `worker-image`, and
`automation-service`.

The later hardened local commit `d889eee0b108d5a5ea10c0a9a8572c79f30a65e7`
has tree `4e07ee076a6ce1a03de0318df893559cc5caf35d`; it includes transactional
append/recompute protection, future-evidence refusal, public read recomputation,
and final documentation. That tree has not been published or run in GitHub CI.

---

# 0.22.0-alpha.1 verification report

Date: 2026-08-31 UTC

## Executed evidence

- `SPARKLE-PROJECT/1` validates the requested project lifecycle, status,
  priority, deadline, dependencies, risks, milestones, blockers, next action,
  progress, optimistic version, and archive boundaries in a separate data
  environment.
- Create/update/list/search/archive flows execute through API and CLI. Archive
  requires explicit interface approval, stale updates fail closed, active
  projects are bounded to 1,000, lists to 100, and agent searches to 20.
- Personal, Project, and Productivity agents receive a read-only project tool;
  unrelated agents do not. No model-facing tool can write project state.
- Change evidence retains at most 10,000 records and contains only identifier,
  action, version, changed fields, status, priority, progress, and timestamp.
  Structured proactive alerts use status/count/progress/deadline evidence and
  do not copy project descriptions, risks, blockers, milestones, or next
  actions.
- The first focused run executed eight cases and exposed three errors from an
  invalid SQLite `LIKE` escape expression. After switching to a literal `!`
  escape, the second run exposed one incorrect test expectation: `_` is a
  legitimate literal character in both fixture identifiers. The expectation
  was corrected; all eight focused cases passed. Two additional bound and
  proactive cases were then added, and the 22-test project/automation/API/CLI
  adjacent suite passed in 1.490 seconds.
- The complete suite passed all 194 tests in 26.371 seconds. Dashboard
  JavaScript syntax, Python compilation, documentation contracts, and Git
  whitespace checks passed.
- A zero-dependency non-editable `0.22.0a1` wheel installed without an index in
  a fresh virtual environment. Installed project
  create/update/reload/search/proactive/archive, AI-system preparation,
  multimodal round-trip, automation check/once/status, worker help, and
  mode-0600 configuration checks passed. Its SHA-256 was
  `ce44e407b9e281dec6e61c4c3c85e22968475949a3f7c1ea6aa251e89b793d14`.

## Honest limits

- Structured project state and deterministic read access do not establish
  live-provider project-decision quality.
- Third-party project-management, calendar synchronization, and external
  notification connectors remain absent.
- Third-party runtime limits remain unchanged by the successful private
  repository publication and CI verification below.

## GitHub publication and CI

Result: PASS — private repository `pexxoraa/SPARKLE` received capability
commit `8db4ab1d66ce1bdd81449d88d54ea3b4d8c98490` on `main` by a non-force
fast-forward from the verified v0.21 documentation checkpoint. Its tree
`db4fedf6cdb0aa5c8c96be4cefb1e6ef22e0d9ee` exactly matches local tested
commit `434af780deeab61d666d6ca26119f93cf466c2df`.

SPARKLE CI run #47 (`33331355984`) completed successfully. All required jobs
passed: `test (3.12)`, `test (3.13)`, `worker-image`, and
`automation-service`.

---

# 0.21.0-alpha.1 verification report

Date: 2026-08-30 UTC

## Executed evidence

- `SPARKLE-AI-SYSTEM-BLUEPRINT/1` converts an exact bounded structured
  requirement into deterministic provider-neutral model routes, agent/tool
  references, separate data environments, interfaces, workflow, evaluation
  contracts, and an explicitly unverified deployment plan.
- Model requirements resolve capability roles and modalities against enabled
  registry records without importing provider-specific behavior, constructing
  an adapter, or calling a model. Selected tools must be registered and allowed
  by at least one selected installed agent.
- Preparation is non-mutating. Explicitly approved materialization writes only
  deterministic `README.md` and `SPARKLE_AI_SYSTEM.json` files through the
  existing bounded workspace manager with overwrite disabled.
- The latest 1,000 blueprint attempts persist separately. Successful records
  link to workspace build evidence; failures retain only a safe exception type,
  not source content or an exception message.
- Seven focused builder/API/CLI cases passed. The first complete run executed
  186 tests: 185 passed and the documentation version contract caught the stale
  v0.20 value in `BUILD_STATE.md`. After correction, all 186 tests passed in
  24.235 seconds. The final documented tree passed all 186 tests in 24.451
  seconds; dashboard JavaScript syntax and Git whitespace checks passed.
- A zero-dependency non-editable `0.21.0a1` wheel installed without an index in
  a fresh virtual environment. Installed AI system prepare/build/reload,
  isolated Agent Blueprint response evaluation/non-disclosure, multimodal
  round-trip, automation check/once/status, worker help, and mode-0600
  configuration checks passed. Its SHA-256 was
  `6c310495ba44b6e489b30f6b81a2218951fe3e4ae0ad0b0a2bf20e06a8d33510`.
- The development executor then reset before publication. A clean recovery
  worktree was reconstructed over the exact published v0.20 tree. Its complete
  suite passed all 186 tests again in 26.097 seconds.
- The first recovery wheel smoke called a nonexistent convenience constructor
  after the wheel had built and installed; the second used a tuple where the
  contract intentionally requires a list. Neither is counted as a passing
  release gate. The corrected third fresh no-index build/install passed AI
  system prepare/build/reload, multimodal round-trip, automation
  check/once/status, worker help, and mode-0600 configuration checks. The
  recovery wheel SHA-256 was
  `d529a955fdd2f3186aca64d563f5fdeda03443a746be4b3dc760d025c5b74cf7`.

## Honest limits

- The blueprint is a statically validated architecture scaffold. It does not
  generate implementation source, run declared evaluations, call a model, or
  deploy a target. All four claims remain explicit in its output.
- Requirements are structured JSON. Natural-language requirements conversion,
  semantic runtime evaluation, and external deployment remain incomplete.
- No live provider, external deployment, or semantic evaluation ran.

## GitHub publication and CI

Result: PASS — private repository `pexxoraa/SPARKLE` received capability
commit `0256c16bd247f84448baf1ed9ae9f6ecc8f3e0fb` on `main` by a non-force
fast-forward from the verified v0.20 checkpoint. Its tree
`02acd582684da3dd335bc7fe503bc538c4bfbf75` exactly matches local tested commit
`7a66793f23a4ee1eb26a520d3aac64343b846018`.

SPARKLE CI run #45 (`33329833127`) completed successfully. All required jobs
passed: `test (3.12)`, `test (3.13)`, `worker-image`, and
`automation-service`.

---

# 0.20.0-alpha.1 verification report

Date: 2026-08-30 UTC

## Executed evidence

- `SPARKLE-AGENT-EVALUATION/1` runs bounded lexical/length response contracts
  for an installed, revalidated Agent Blueprint through the common model
  router. Model calls require explicit operator approval.
- The isolated orchestrator profile rejects history, additional context, and
  user identity; skips memory/knowledge retrieval; advertises no tools; and
  fails if the model requests one.
- The latest 1,000 evaluation records contain check booleans, response hashes
  and lengths, provider/model labels, trace IDs, and safe error types without
  prompts, responses, assertion phrases, or personal context. Evaluation
  traces use generic summaries.
- Twelve focused builder/evaluation/API/CLI cases passed before the isolation
  injection boundary case was added. The first complete run then passed 178 of
  179 tests and caught a stale v0.19 version in `BUILD_STATE.md`; the corrected
  complete suite passed all 179 tests in 22.690 seconds. The final exact-tree
  run passed all 179 tests in 22.564 seconds. Dashboard JavaScript syntax and
  Git whitespace checks passed.
- A zero-dependency non-editable `0.20.0a1` wheel installed without an index in
  a fresh virtual environment. Installed blueprint build/evaluate/reload,
  isolated content-free evidence, multimodal round-trip, automation
  check/once/status, worker help, and mode-0600 configuration checks passed.
  Its SHA-256 was
  `a41d689e9fea9cc7eaf16dde4b287aa4d1169351a1a135831140d7e9e505d5f4`.
- Capability commit `e1e4066671672671ec48d3c2b7f76059c0207427` has exact tree
  `99db2e28bfaafff456e42b1c8cce1b51b4f7a631`. GitHub CI run #43
  (`33314903193`) passed Python 3.12, Python 3.13, worker-image, and
  automation-service jobs. The documentation checkpoint that records this
  evidence passed all 179 tests in 22.433 seconds.

## Honest limits

- These deterministic response contracts are not semantic correctness
  judgments. `semantic_evaluation_executed` and `live_provider_verified`
  remain false.
- No live MiniMax evaluation, natural-language source generation, or external
  agent deployment ran.

---

# 0.19.0-alpha.1 verification report

Date: 2026-08-30 UTC

## Executed evidence

- `SPARKLE-AGENT-BLUEPRINT/1` converts exact bounded structured requirements
  into a provider- and model-neutral `AgentSpec`, workflow, guardrails, and
  evaluation fixtures without mutating the registry.
- Preparation rejects unknown fields/tools, invalid scalar and collection
  bounds, duplicates, oversized JSON, built-in/existing names, and fixtures
  that do not select the candidate through the production routing scorer.
- Approved builds persist the agent and separate blueprint evidence, hot-load
  routing, survive process reload, and roll back the agent manifest when
  blueprint persistence fails. API and CLI preparation/build/list paths run.
- Six focused builder/API/CLI cases passed. A first complete run passed 171 of
  172 tests and caught a stale v0.18 version in `BUILD_STATE.md`; this report
  preserves that corrected documentation failure rather than counting it as a
  pass. The corrected complete suite passed all 172 tests in 22.177 seconds.
- The first auxiliary JavaScript command used the obsolete
  `dashboard/assets/app.js` path after the suite had passed and failed with
  `MODULE_NOT_FOUND`. The corrected repository path
  `src/sparkle/dashboard/app.js` passed `node --check`; Git whitespace checks
  also passed.
- An initial clean wheel passed before final review added append-only
  remove/rebuild history; that earlier wheel was invalidated and is not release
  evidence. A fresh zero-dependency non-editable `0.19.0a1` wheel from the
  final capability tree installed without an index. Preparation remained
  non-mutating; approved install/reload/routing and remove/rebuild history
  passed; multimodal canonical round-trip, automation check/once/status,
  worker help, and mode-0600 configuration checks also passed. The final wheel
  SHA-256 was
  `3f29323e7c0fd2ec67b06ba3fe9451ad5b5aa43122a0aaa0229dae913cfd0919`.

## Honest limits

- Static routing fixtures prove deterministic selection, not semantic response
  quality. No live model evaluation ran.
- Requirements are structured JSON. Natural-language source generation and
  external agent deployment are not implemented by this increment.

## GitHub publication and CI

Result: PASS — private repository `pexxoraa/SPARKLE` received capability
commit `f6e0466a449ff19aa49357b2875a95255267de2e` on `main` by a non-force
fast-forward. Its tree `d2c8d4621946db9fcbb67b6777c04d63e055d289`
exactly matches local tested commit
`646359e58e3530295a06a3ca74c055aa15fb89cb`.

SPARKLE CI run #41 (`33313769623`) completed successfully. All required jobs
passed: `test (3.12)`, `test (3.13)`, `worker-image`, and
`automation-service`.

---

# 0.18.0-alpha.1 verification report

Date: 2026-08-30 UTC

## Executed evidence

- `SPARKLE-NOTIFICATION/1` defines a provider-neutral dashboard delivery
  channel with strict title/body/severity/dedupe/source validation.
- The local notification store preserves delivery/read state, updates matching
  dedupe keys, caps retention at 1,000 records, and exposes bounded lists.
- Manual API delivery/list/read and dashboard rendering execute. Conditional
  automations can deliver without a model and link a trace containing only
  channel, severity, notification ID, transformation, and destination.
- The focused notification/automation/API/dashboard set passed. The adjacent
  notification, storage, automation runner/service, and API set passed 52
  tests in 17.048 seconds.
- After adding the dedupe-refresh retention boundary, the complete suite passed
  166 tests in 36.292 seconds. Dashboard JavaScript syntax and Git whitespace
  checks passed.
- A zero-dependency non-editable `0.18.0a1` wheel installed without an index in
  a fresh virtual environment and passed notification automation/read-state,
  trace non-disclosure, multimodal round trip, automation check/once/status,
  worker-entrypoint, and mode-0600 configuration checks. Its SHA-256 was
  `c1df89da337becced79392045737106872435e47f084ac3d1b932778087791c7`.

## GitHub publication and CI

Result: PASS — private repository `pexxoraa/SPARKLE` received capability
commit `c801e4dbaa55462b50681b33a9e11e8e9c5f26e3` on `main` by a non-force
fast-forward. Its tree `c15469bc2d537389d51715b103bace63565c5b89`
exactly matches local tested commit
`1badcf119b2007ded512fa5b86b5691415e7a5a3`.

SPARKLE CI run #39 (`33301375054`) completed successfully. All required jobs
passed: `test (3.12)`, `test (3.13)`, `worker-image`, and
`automation-service`.

## Honest limits

- Dashboard delivery is local to SPARKLE. Email, SMS, mobile push, calendar,
  and webhook adapters are not implemented.
- Notification title/body are intended user-visible data in the notification
  database and API; they are deliberately excluded from traces and automation
  result summaries.

---

# 0.17.0-alpha.1 verification report

Date: 2026-08-30 UTC

## Executed evidence

- Explicit knowledge observations receive deterministic SHA-256 content
  digests inside the separate knowledge database. The two latest same-key
  observations produce a `research_change` view only when content changed.
- Monitoring metadata is limited to 4 KiB; opt-in must be boolean and monitor
  keys must be safe 1-64 character identifiers. Existing knowledge databases
  migrate in place without a rebuild.
- Evaluation reads at most 200 observations, emits at most 100 changes, expires
  changes after seven days, and exposes no content, title, URI, or digest.
- Six focused knowledge-revision/automation/API cases passed. The first pass
  contained one over-broad test assertion that banned `paper` even though the
  public monitor key was `robotics.papers`; the assertion was narrowed to the
  actual private title, and the corrected set passed.
- The corrected adjacent storage, automation, and API set passed 38 tests in
  13.418 seconds.
- After adding the CLI revision flow, the corrected complete suite passed 160
  tests in 34.371 seconds. Dashboard JavaScript syntax and Git whitespace
  checks passed.
- The first clean-wheel command was stopped before execution because the
  environment classified pip as potentially networked; no build or check ran.
  Retrying with `PIP_NO_INDEX=1` completed without network access.
- A zero-dependency non-editable `0.17.0a1` wheel installed in a fresh virtual
  environment and passed installed status, research-change/non-disclosure,
  multimodal round trip, automation check/once/status, worker-entrypoint, and
  mode-0600 configuration checks. Its SHA-256 was
  `4a545e5f0770247f1fce62c047f1b967544f0f2342f231fd823e7fcf88d79d63`.

## GitHub publication and CI

Result: PASS — private repository `pexxoraa/SPARKLE` received capability
commit `e737c627c8a190440df15dde12ad32aa7f16977e` on `main` by a non-force
fast-forward. Its tree `97dba5c1cb597f0d41a059bae0d9cf6ba287463e`
exactly matches local tested commit
`05c52de8dce02a7e8ba632806c8ad8c44edc1207`.

SPARKLE CI run #37 (`33300452288`) completed successfully. All required jobs
passed: `test (3.12)`, `test (3.13)`, `worker-image`, and
`automation-service`.

## Honest limits

- SPARKLE detects changes only when an operator or future connector submits a
  new observation. It does not poll websites or discover sources in this
  release.
- Notification/calendar/webhook delivery remains absent.

---

# 0.16.0-alpha.1 verification report

Date: 2026-08-30 UTC

## Executed evidence

- Four focused schedule-conflict storage/automation/API cases passed after one
  corrected horizon-boundary fixture; the corrected adjacent storage,
  automation-runner, and API set passed 33 tests in 8.939 seconds.
- The engine validates positive ISO-8601 intervals no longer than seven days,
  considers at most 200 recent records and a 30-day horizon, emits at most 200
  deterministic conflicts, and exposes only safe pair evidence.
- Conditional automations can match `schedule_conflict` with existing strict
  category/key filters and cooldowns. API output contains no memory free text.
- The corrected complete `make check` passed 154 tests in 19.378 seconds;
  dashboard JavaScript syntax and Git whitespace checks passed.

- A zero-dependency non-editable `0.16.0a1` wheel installed in a fresh virtual
  environment and passed installed status, schedule-conflict
  evaluation/non-disclosure, multimodal round trip, automation
  check/once/status, worker-entrypoint, and mode-0600 configuration checks.

## GitHub publication and CI

Result: PASS — private repository `pexxoraa/SPARKLE` received capability
commit `d570107a57f879d72f035adab41c42b86a142948` on `main` by a non-force
fast-forward. Its tree `ef33e08fb040e5480bf56372dfe68d05d01c014f`
exactly matches local tested commit
`bf7e54b76c2f5be6747860f4618e18785a5f3ad7`.

SPARKLE CI run #35 (`33299313086`) completed successfully. All required jobs
passed: `test (3.12)`, `test (3.13)`, `worker-image`, and
`automation-service`.

## Honest limits

- Conflicts require explicit structured time metadata; SPARKLE does not infer a
  calendar from memory prose.
- External calendar ingestion, notification delivery, and research-change
  monitoring remain absent.

---

# 0.15.0-alpha.1 verification report

Date: 2026-08-30 UTC

## Executed evidence

- The focused multimodal set passed 17 tests in 1.505 seconds after validation,
  routing, trace-migration, and provider-failure hardening.
- The adjacent MiniMax/orchestrator/storage/security regression set passed 58
  tests in 9.625 seconds.
- The first complete pre-publication `make check` passed 138 tests in 23.005
  seconds. The final documented rerun passed all 138 in 22.472 seconds.
  Dashboard JavaScript syntax and Git whitespace checks also passed.
- A zero-dependency non-editable `0.15.0a1` wheel installed into a fresh
  virtual environment. Installed status, deterministic mixed-content round
  trip, exact legacy serialization, automation check/once/status, and the
  worker entrypoint passed. Both independently materialized application/model
  configuration files were mode 0600.
- Legacy string messages remain byte-for-byte serialization compatible. Text,
  image, audio, document, and mixed envelopes flow through API validation,
  context construction, capability routing, model requests, a compatible
  deterministic adapter, agent results, and execution traces.
- Bounds and failure tests cover part/envelope/request/API sizes, empty and
  malformed payloads, wrong MIME families, non-canonical base64, unsupported
  types, duplicate/forged IDs, invalid metadata, and a text-only MiniMax
  refusal before any network operation.
- Trace migration and integration tests prove that modalities, derived content
  identifiers, processing stages, transformations, output modalities, and safe
  execution metadata are recorded without raw input or caller metadata.

The locally tested release tree is `b7d4365b185ad5c5b8bcad57cf41c1cf4da216e6`.

## Honest limits

- The release proves provider-neutral contract transport and failure behavior,
  not semantic understanding of image, audio, or document bytes.
- MiniMax-M3 remains configured and verified as a text-only adapter. No
  undocumented provider-specific multimodal mapping was added.
- Video, camera, sensor, spatial, and gesture types remain future extensions.

## GitHub publication and CI

Result: PASS — private repository `pexxoraa/SPARKLE` received capability commit
`61cab3f4cf786276edcc5428b83960355d109448` on `main` by a non-force
fast-forward. Its tree `b7d4365b185ad5c5b8bcad57cf41c1cf4da216e6`
exactly matches local tested commit
`4ff0eafc63d9ef8a969af8c1a5c8def12d8faadc`.

SPARKLE CI run #31 (`33289468321`) completed successfully. All required jobs
passed: `test (3.12)`, `test (3.13)`, `worker-image`, and
`automation-service`, including compile/test, worker image build/entrypoint,
non-editable package installation, and installed service lifecycle steps.

## Phase 33 continuation evidence

After the capability release, four dedicated voice/presence contract tests and
three data-driven built-in-agent evaluation groups were added. The agent matrix
checks all 16 agents' domain contracts, routing, tool boundaries, common safety
prompts, deterministic orchestrator execution, and trace linkage. Focused runs
passed 4/4 and 3/3; the complete suite passed 145 tests in 22.919 seconds.
This does not claim real speech I/O or live-provider response quality. The
local checkpoint is `c3cc1957e60c44c323677008d53b1543a448e7d2`,
tree `b2b437d2d2a7bed6136af4ee78705aad906f019a`. Remote non-force
fast-forward commit `cba15105cd50f7d567c1c5a9f19c98a4ed58342c` has the
same tree. CI run #32 (`33289795885`) passed all four required jobs.

## Phase 34-35 continuation evidence

Four documentation contract tests now require the complete directive inventory,
resolve repository-relative links, align package/display versions, and retain
the build-state and honest acceptance fields. The audit corrected one stale
worker-image claim. A cohesive deterministic system test then exercised HTTP
memory/knowledge writes, mixed text/document chat, context injection, explicit
research-agent/model routing, result modalities/identifiers, raw-document-free
trace retrieval, and final presence linkage. Its focused run passed; the full
suite passed 150 tests in 28.012 seconds. A fresh non-editable `0.15.0a1` wheel
then installed without dependencies or an index and passed installed version,
content round-trip, exact legacy serialization, honest security/multimodal
status, automation check/once/status, worker entrypoint, and separate mode-0600
configuration checks. Local commit
`81096223b892558f2f6ccd61129ece7c5f3c0122` has tree
`59658768df608a10fcc6174bb55d95128e511d53`; remote non-force
fast-forward commit `6ec020a40e9ee6675a4591d5b563f45449507b35` has the
same tree. CI run #33 (`33290153808`) passed all four required jobs.

---

# 0.14.0-alpha.1 verification report

Date: 2026-08-29 UTC

## Executed evidence

- The focused proactive storage/runner/API set passed 28 tests in 8.376 seconds
  after version and documentation alignment.
- The final pre-publication `make check` passed 120 tests in 21.283 seconds,
  including deterministic ordering and the hard 200-alert response bound.
- A non-editable `0.14.0a1` wheel was built without dependency resolution,
  installed in a fresh virtual environment, and ran `sparkle status` plus the
  automation check/once/status lifecycle. Runtime defaults materialized as two
  separate mode-0600 files, status surfaces reported
  `credentials_exposed: false`, and the service completed one clean cycle.
- Dashboard JavaScript syntax and Git whitespace checks passed.
- The engine emits six bounded alert types exclusively from validated
  structured memory metadata. Invalid, incomplete, unstructured, non-finite,
  and out-of-range evidence produces no alert; serialized alerts omit memory
  free text.
- Strict conditional-automation schemas reject unknown types, alert names,
  categories, fields, empty/oversized keys, and invalid cooldowns. A real
  weak-learning condition executed once and respected its cooldown.
- `GET /api/proactive` and the dashboard panel are integration tested, and the
  query-free audit path is recorded separately.

## Honest limits

- Proactive output is deterministic evidence-based prioritization, not
  prediction or autonomous understanding of unstructured memory text.
- Schedule-conflict detection, research-change monitoring, notification
  delivery, and calendar/webhook connectors are not implemented.
## GitHub publication and CI

Result: PASS — private repository `pexxoraa/SPARKLE` received capability commit
`99f5bd27853145fec00fb80d356c6f45bdd52f50` on `main` by a non-force
fast-forward. Its tree `fa068d1e7f15dfdb8306abd93febdd53d1cb593a`
exactly matches the locally tested v0.14 tree in commit
`6c086530100181c3d77bf504cfa6abde995bbb68`.

SPARKLE CI run #29 (`33287645323`) completed successfully. All required jobs
passed: `test (3.12)`, `test (3.13)`, `worker-image`, and
`automation-service`, including the compile/test, worker image build and
entrypoint, non-editable package install, and service lifecycle steps.

---

# 0.13.0-alpha.1 verification report

Date: 2026-08-29 UTC

## Executed evidence

- The focused automation/API set passed 27 tests in 9.234 seconds.
- The dedicated service set passed 10 tests in 0.899 seconds, including a real
  foreground subprocess heartbeat → SIGTERM → draining → exit-0 workflow.
- The first full pre-release run passed 113 tests in 20.231 seconds before the
  SIGTERM case was added. After the signal-safety refinement, the final
  release-state `make check` passed all 114 tests in 21.288 seconds with no
  failures or errors. Dashboard JavaScript
  syntax and Git whitespace checks also passed.
- Offline editable installation initially succeeded as
  `sparkle-personal-ai==0.13.0a1`, and its entrypoints passed from the checkout.
  CI then correctly showed that this was insufficient wheel evidence. After
  the fix, a non-editable wheel was built without dependencies or an index,
  installed into a fresh virtual environment, and its `sparkle-automations`
  check → once → status workflow returned ready, one cycle, stopped state, and
  `credentials_exposed: false`. Both separate mode-0600 runtime configuration
  files were materialized from bundled defaults. With `SPARKLE_DATA_DIR`
  absent, the wheel also used `XDG_STATE_HOME/sparkle` rather than an installed
  code directory. The final corrected suite passed 116 tests in 20.023 seconds.

## Verified v0.13 capability paths

- The existing scheduler remains the execution core; the new
  `sparkle-automations` entrypoint adds supervision rather than a parallel
  scheduling implementation.
- Atomic claims carry bounded expiring tokens. Startup and each cycle recover
  expired claims, append an `AutomationLeaseExpired` run, and make work eligible
  again. A recovered/cancelled token cannot commit a result.
- A no-follow, mode-0600 POSIX flock prevents concurrent local service
  instances. Lifecycle state records only heartbeats, counts, timestamps,
  bounds, and safe error types.
- `--check`, `--once`, `--status`, and `--healthcheck` are exercised. The
  signal-safe SIGTERM handler performs no I/O, prevents another cycle, and
  normal control flow persists a clean stop after the active bounded operation.
- The non-root systemd profile supplies restart policy, forced-stop bound,
  read-only host protection, one writable state path, empty capabilities, and
  no embedded provider credential.

## Honest limits

- Recovery is at least once, not exactly once. Future external actions need
  independent idempotency keys.
- The systemd profile is inspected and the service lifecycle runs locally, but
  no named persistent host has installed the unit.
- Notification/calendar/webhook connectors, live MiniMax scheduled execution,
  and external delivery remain unavailable or unverified.

## GitHub publication and CI

The initial capability commit
`01050be68ffa8915c414f2fc181a380a24bbb0c5` has exact local/remote tree
`442d2b3ef5f6301b6b8d1471c538ecc949302e43`. CI run #26
(`33265181873`) passed Python 3.12, Python 3.13, and worker-image jobs, but its
new automation-service job failed: the built wheel omitted top-level
application/model configuration, so `--check` passed but `--once` raised
`FileNotFoundError`. Bundled separated defaults plus installed-runtime
materialization fix that packaging defect; replacement evidence follows.

Result: PASS AFTER CORRECTION — remote commit
`c223942a5b01c132629930f1735b7ba1a729a418` points to corrected tree
`6e097298640407b704e3ec2390de9aa010c44b31`, exactly matching local commit
`7e0b53a1b353f86e4cf50aeb59c610ba2a680226`. CI run #27
(`33265747867`) passed `test (3.12)`, `test (3.13)`, `worker-image`, and the
non-editable installed `automation-service` check/once/status lifecycle.

---

# 0.12.0-alpha.1 verification report

Date: 2026-08-29 UTC

## Executed commands

### Focused artifact/API regression

```bash
PYTHONPATH=src python3 -m unittest \
  tests.test_external_worker tests.test_artifacts tests.test_orchestrator_api
```

Result: PASS — 30 tests passed in 7.690 seconds after the database fixture fix.

### Compile and full regression suite

```bash
make check
```

Result: PASS — the final release-state run passed 104 tests in 19.728 seconds;
0 failures and 0 errors.
The first full run exposed a test-only database allocator that counted SQLite
WAL/SHM sidecars and could reopen an earlier database. The fixture now assigns
a monotonic database index. Production job IDs remain UUID4 values and the
append-only uniqueness constraint remains intact.

### Offline editable installation and installed modules

```bash
python3 -m pip install -e . --no-build-isolation --no-deps --no-index
python3 -m sparkle status
python3 -m sparkle.worker_service --check
```

Result: PASS — the zero-dependency core built and installed as
`sparkle-personal-ai==0.12.0a1` without an index. Application and worker modules
both reported `0.12.0-alpha.1`; the application truthfully reported `limited`
without a live model credential, while the explicitly unsafe process-worker
check reported ready with filesystem/network isolation false and credential
exposure false. An initial bare `sparkle` lookup exited 127 because this
executor omits its user script directory from `PATH`; direct installed-module
execution succeeded. A first result formatter also addressed isolation fields
at the response root instead of the `executor` object and exited with
`KeyError`; the corrected formatter passed. Neither failure was a product
execution failure.

## Verified v0.12 capability paths

- Approval-gated application packaging accepts no command, arguments,
  dependencies, target credentials, or environment input and never executes
  workspace code.
- Stable no-follow reads, strict count/size bounds, sensitive/reserved path
  rejection, and case-fold collision detection protect portable archive input.
- Canonical per-file manifests, source digests, fixed ZIP timestamps/modes,
  stored compression, sorted entries, and whole-artifact SHA-256 hashes make
  identical inputs byte reproducible.
- Artifacts are content-addressed and immutable. Identical source reuses verified
  bytes, changed source creates a new artifact, and tampering is refused.
- Deployment records are append-only reports only. They always expose
  `verification_status: unverified` and `external_action_executed: false`.
- CLI, authenticated API, dashboard, system status, builder-agent tool access,
  storage map, and documentation expose the same honest boundary.

## Not verified

- Target-specific application builds, package installation, signing/notarizing,
  cloud credentials, an external deployment action, or independent deployment
  attestation.
- Named remote worker/TLS deployment and live hostile-code namespace isolation.
- A real MiniMax-M3 response, real voice, browser/computer control, sensors, or
  robotics hardware.

## GitHub publication and CI

Result: PASS — remote commit
`37e4d05a73d0158963fd95ea93af8675fcb976b3` points to tree
`79969d371a213b1bd92b5a61564d64db9caa2c49`, exactly matching local capability
commit `3a7f1ed19b065aa834c4c002f90b7029c4283d6d`. SPARKLE CI run #24
(`33264113348`) completed successfully: `test (3.12)`, `test (3.13)`, and the
worker-image build/installed-entrypoint job all passed.

---

# 0.11.0-alpha.1 verification report

Date: 2026-08-29 UTC

## Executed commands

### Compile and regression suite

```bash
make check
```

Result: PASS — the corrected final v0.11 release-state run executed 96 tests in
24.139 seconds; 96 passed, 0 failed, 0 errors. Fifteen new cases cover the
worker server, real fixed child execution, application imports, timeout and
process-group termination, exact HMAC/schema/digest/path/limit validation,
private no-follow key files, replay and job conflicts, concurrency refusal,
fail-closed executor recovery, exact-key redaction, signed HTTP exchange,
Bubblewrap command and real preflight behavior, deployment policy, and the true
client → service → executor → signed response path.

### Actual isolation preflight

Result: BLOCKED/SAFE REFUSAL — `/usr/bin/bwrap` is installed and the executable
preflight ran, but this build executor does not permit the nested namespace
operation. `sparkle-worker` reports `ready: false`, the safe failure type, and
both filesystem/network isolation fields false. It does not execute submitted
source in this state. The development process executor completed the end-to-end
protocol test but correctly reported both isolation fields false.

### Deployment assets

Result: IMPLEMENTED/LOCALLY INSPECTED — the package exports a separate
`sparkle-worker` entrypoint. `worker_environment/` contains an unprivileged
image, read-only/capability-dropped Compose policy, private worker network,
Caddy TLS gateway, file-mounted secret, bounded state/tmp, health preflight,
and a hardened systemd service. Regression tests inspect the critical policy.
Docker is unavailable in the local executor, so the actual image build is
assigned to the v0.11 GitHub CI worker-image job and is not yet marked verified.

## Verified v0.11 capability paths

- The application and service remain separate processes/packages with no
  application store, model, agent, or provider dependency in the worker.
- The server accepts only `SPARKLE-WORKER/1` `python_unittest`, exact fields,
  valid paths/digests/UTF-8 source, fresh signed requests, and requested
  isolation controls.
- A SQLite replay store binds job ID to exact request hash. Exact completed
  duplicates replay one result; changed or in-flight duplicates conflict.
- The fixed runner applies wall/POSIX resource bounds, receives a cleared
  environment, imports submitted application code, redacts output, and writes
  only inside an ephemeral workspace.
- Production readiness requires a real Bubblewrap host-canary/environment/
  network preflight. Any dependency, denial, timeout, or failed check refuses
  jobs. Development process mode requires explicit unsafe opt-in and never
  reports filesystem/network isolation.
- Signing keys resolve through existing secret references or private no-follow
  files and are absent from source, status, logs, request persistence, and
  deployment configuration.

## Not verified

- A built/pulled container image, named remote deployment, public TLS endpoint,
  live isolated hostile-code execution, cgroup/seccomp behavior at a target,
  or independent promotion of sandbox claims to isolation evidence.
- A real MiniMax-M3 response, public application deployment, multi-user role
  authorization, real voice, browser/computer control, sensors, or robotics.

## GitHub publication and CI

Result: PASS — capability commit `de9b1c7f2c58178ea691982c231ab4a13358eba0`
published the worker and tree `a94eb92258ad971184a610546eea00b1160ae510`.
CI run #21 built the worker image and verified its entrypoint successfully, but
the Python 3.13 job exposed an environment-dependent test assumption: the fake
command-construction preflight still required an installed `bwrap` executable.
The implementation was not executed on that path. The test now supplies an
inert existing binary to its injected runner; the separate real-preflight case
continues to cover dependency discovery and fail-closed behavior.

The corrected remote commit is
`e1b014b2530d0ae5ee762573d81e093fb46aa834`. Its tree
`9db377f73b86589c34c50d5174fd5cf20ea727d1` exactly matches local commit
`55d897e0738fd3f4e52a3b41fcafd0bc2eeb4201`. SPARKLE CI run #22
(`33253329992`) completed successfully: `test (3.12)`, `test (3.13)`, the
worker-image build, and the installed image entrypoint check all passed.

---

# 0.10.0-alpha.1 verification report

Date: 2026-08-29 UTC

## Executed commands

### Compile and regression suite

```bash
make check
```

Result: PASS — the final release-state run executed 81 tests in 13.819 seconds;
81 passed, 0 failed, 0 errors. New evidence covers signed request/response exchange, source hashes
and bounds, strict result validation, safe failure persistence, operator-only
approval, API/CLI/dashboard integration, and explicit non-verification of
remote sandbox claims. Adversarial cases include bad signatures, stale
timestamps, wrong job IDs, unknown fields, inconsistent status, oversized
responses, transport failures, symlinks, hidden/credential-like/binary/
oversized files, and source containing the configured signing key.

Editable installation with build isolation disabled also succeeded for package
`sparkle-personal-ai==0.10.0a1`. Dashboard JavaScript syntax and Git whitespace
checks passed.

A first compact status-evidence formatter failed with a `TypeError` because it
tried to sort tool-record dictionaries. SPARKLE itself had exited 0 and written
valid JSON. The formatter was corrected and the status check was rerun
successfully; this was an evidence-script error, not a product test failure.

### External worker live/isolation status

Result: BLOCKED — the repository implements and tests the client protocol with
a deterministic signed worker double. No compatible external worker endpoint,
container image, or signing secret is configured in this build process. No
source was transferred and no remote code was executed. Worker sandbox fields
remain claims and `isolation_verified` is false.

## Verified v0.10 capability paths

- External execution is disabled by default, accepts only the fixed
  `python_unittest` operation, and requires explicit approval per submission.
- The operator facade is not in the agent/model tool registry, preventing a
  model from manufacturing source-transfer approval.
- Source packaging is workspace-confined, deterministic, UTF-8-only, hashed,
  and bounded; symlinks and sensitive/hidden/key-containing inputs are rejected.
- The endpoint must be credential-free HTTPS. Canonical requests and responses
  carry fresh timestamped HMAC-SHA256 authentication with a secret-resolved
  key that is never persisted or returned.
- Responses are size-bounded, schema-exact, job-matched, type-checked,
  status-consistent, HTTP/JSON/protocol-checked, output-redacted, and safely
  recorded. Redirects are denied. Transport and
  protocol failures store only bounded metadata and error type.
- CLI, authenticated API, read-only dashboard history, system status, data map,
  security guidance, and development guidance expose the actual boundary.

## Not verified

- A deployed compatible worker, hostile-code container isolation, network
  denial, ephemeral filesystem, cgroup/seccomp limits, job deduplication, or a
  real remote test. Authenticated worker claims are not proof of those controls.
- A real MiniMax-M3 response, production TLS/reverse proxy, multi-user role
  authorization, packaging/deployment, real voice, browser/computer control,
  sensors, or robotics hardware.

## GitHub publication and CI

Result: PASS — private repository `pexxoraa/SPARKLE` received v0.10 capability
commit `d26ba2bb951d6943ad305c187d99d86f66d0b57a` on `main` without a force
update. Its Git tree `c440cfb9f01acadd2043b03dde21cfd61349d066`
exactly matches the locally tested tree in commit
`4691b09a5a3c989c309fdb55b2c10cce4aa305ef`.

SPARKLE CI run #19 (`33251219676`) completed successfully in 22 seconds. Both
matrix jobs, `test (3.12)` and `test (3.13)`, completed successfully, including
the `Compile and test` step.

---

# 0.9.0-alpha.1 verification report

Date: 2026-08-29 UTC

## Executed commands

### Compile and regression suite

```bash
make check
```

Result: PASS — 72 tests ran in 8.634 seconds; 72 passed, 0 failed,
0 errors. New evidence covers session creation, hashed-ID storage, absolute
expiry, bounded capacity/eviction, cookie attributes, CSRF rejection and
acceptance, session restoration after dashboard reload, logout/revocation,
bearer compatibility, configuration bounds, and secret-free audit/status paths.

### Static release checks

```bash
node --check src/sparkle/dashboard/app.js
git diff --check
```

Result: PASS — the dashboard JavaScript parsed and the working diff contained
no whitespace errors.

### Sanitized runtime and bind-policy checks

A fresh process with an empty environment except the documented runtime paths
ran `sparkle status` with exit 0. It reported version `0.9.0-alpha.1`, no
configured provider key, sessions disabled while API authentication is off,
zero active sessions, non-persistent session state, and
`credentials_exposed: false`.

A separate sanitized process supplied a placeholder API token, required API
authentication, requested a non-loopback bind, and deliberately left secure
cookies disabled. Startup failed closed with exit 1 and the exact policy error
`Non-loopback dashboard sessions require secure cookies and TLS termination`.
The placeholder credential did not appear in output.

The live provider smoke in a sanitized environment exited 2 at
`credential_presence`, with `configured: false` and
`secret_value_exposed: false`. No MiniMax request was made; this remains
BLOCKED rather than PASS.

## Verified v0.9 capability paths

- The existing secret-resolved bearer credential can be exchanged for an
  opaque 256-bit dashboard session without exposing it in response bodies,
  status, audit, or browser storage.
- Session IDs are represented only by SHA-256 digests in bounded process memory;
  sessions expire absolutely, evict the oldest entry at capacity, revoke on
  logout, and disappear on restart.
- Cookies are host-only, HttpOnly, `SameSite=Strict`, path `/`, and optionally
  `Secure`; a non-loopback session bind fails unless secure cookies are enabled.
- Every cookie-authenticated mutation requires a separate per-session CSRF
  token. The same-origin session endpoint recovers it after reload without
  exposing the HttpOnly session ID.
- Bearer clients remain compatible, session/login/logout routes are rate-,
  origin-, and audit-gated, and the audit schema still cannot accept headers,
  cookies, bodies, client identity, or credentials.
- The dashboard clears the credential field after submission, uses neither
  `localStorage` nor `sessionStorage`, restores valid sessions, and explicitly
  revokes them through **End session**.

## Not verified

- TLS termination, reverse-proxy forwarding policy, public deployment, or a
  real remote browser session. Secure-cookie configuration is enforced, but
  the standard-library server cannot provide or validate edge TLS.
- Multi-user identity, role/owner authorization, distributed session/rate-limit
  state, or session revocation across multiple processes.
- A real MiniMax-M3 response, hardened hostile-code container worker, real
  voice, browser/computer control, sensors, or robotics hardware.

## GitHub publication and CI

Result: PASS — private repository `pexxoraa/SPARKLE` received v0.9 capability
commit `e8d988f8627c83e32b888a3bd7ab93e525542b12` on `main` without a force
update. Its Git tree `92b6ab3240de1cfbbe46e73947320d388d47ef5b`
exactly matches the locally tested tree in commit
`697927c47a98d964230d88944323361d2e0be0aa`.

SPARKLE CI run #17 (`33245128813`) completed successfully in 26 seconds. Both
matrix jobs, `test (3.12)` and `test (3.13)`, completed successfully, including
the `Compile and test` step.

---

# 0.8.0-alpha.1 verification report

Date: 2026-08-29 UTC

## Executed commands

### Compile and regression suite

```bash
make check
```

Result: PASS — 68 tests ran in 9.102 seconds; 68 passed, 0 failed,
0 errors. Added evidence executes real fixed unittest runs and covers resource
limits, wall-time process-group termination, strict parent-environment refusal,
stripped child environment, file-backed pre-persistence output bounds, redaction, symlink/size/command-field
rejection, persistence, and CLI/API/dashboard integration.

### Static and isolation-capability checks

```bash
node --check src/sparkle/dashboard/app.js
git diff --check
unshare --user --map-root-user true
bwrap --ro-bind /usr /usr --proc /proc --dev /dev --unshare-net -- /usr/bin/true
```

Result: PASS for JavaScript and Git whitespace. Both kernel namespace checks
were BLOCKED with `Operation not permitted`; bubblewrap 0.9.0 is installed but
cannot create a namespace in this container. The implementation and status
therefore report `filesystem_isolation: false` and `network_isolation: false`.

### Isolated-status and provider smoke

A fresh, sanitized process ran `sparkle status` with exit 0 and reported
version `0.8.0-alpha.1`, workspace tests disabled, POSIX resource limits true,
filesystem/network isolation false, a sanitized parent, and arbitrary
commands false.

The live provider smoke in the same sanitized environment exited 2 at
`credential_presence`, with `configured: false` and
`secret_value_exposed: false`. No MiniMax request was made; this remains
BLOCKED rather than PASS.

## Verified v0.8 capability paths

- Execution is disabled by default and requires configuration opt-in plus
  explicit approval for each project run.
- The model/user cannot choose an executable, arguments, environment, package,
  or working directory; unsupported fields are rejected.
- A complete workspace scan rejects symlinks and enforces file-count,
  individual-file, and total-byte bounds before execution.
- The trusted child runs only isolated-mode standard-library unittest discovery
  and receives a fixed environment with no inherited provider/API variables.
- POSIX CPU, memory, file-size, descriptor, process, and core limits are applied;
  the parent kills the whole process group on wall timeout.
- A parent containing any non-allowlisted environment variable is refused, because
  same-user process access cannot be safely excluded without a real sandbox.
- Results and bounded credential-pattern-redacted output persist separately and
  are exposed through the CLI, API, dashboard, system status, and tool registry.

## Not verified

- Hostile-code filesystem or network isolation; the runner is not a container
  sandbox and must use a disposable, secret-free worker.
- Package installation, arbitrary application/build execution, packaging, or
  deployment.
- A real MiniMax-M3 response, remote authenticated UI, role authorization, TLS,
  real voice, browser/computer control, sensors, or robotics hardware.

## GitHub publication and CI

Result: PASS — private repository `pexxoraa/SPARKLE` received v0.8 capability
commit `228c302fa23927356e72723f792530ab1e948cee` on `main` without a force
update. Its Git tree `c756d7cbdc239fcf1c518b22f5b01dcf7f6e1344`
exactly matches the locally tested tree in commit
`155dd04335f82d8edad52c9a9e14430d38954f17`.

SPARKLE CI run #15 (`33239100793`) completed successfully in 19 seconds. Both
matrix jobs, `test (3.12)` and `test (3.13)`, completed successfully, including
the `Compile and test` step.

The v0.8 documentation checkpoint commit
`cd0fdfb96365122985081614184e3af3d7157a39` was then verified by SPARKLE CI
run #16 (`33239280620`) in 18 seconds; both Python matrix jobs and their
`Compile and test` steps completed successfully.

---

# 0.7.0-alpha.1 verification report

Date: 2026-08-29 UTC

## Executed commands

### Compile and regression suite

```bash
make check
```

Result: PASS — 61 tests ran in 8.744 seconds; 61 passed, 0 failed,
0 errors. Added evidence covers deterministic fixed-window enforcement/reset,
bounded client state, rate limiting before authentication, response quota
headers, HTTP 429 behavior, query-free audit paths and request logs, and absence of tokens,
query values, origins, headers, and client identifiers from audit records.

### Static release checks

```bash
node --check src/sparkle/dashboard/app.js
git diff --check
```

Result: PASS — dashboard JavaScript parsed and the working diff contained no
whitespace errors.

### Runtime security and provider smoke

Authenticated `sparkle status` with a placeholder test token exited 0. Output
reported authentication required/configured, `credentials_exposed: false`, and
the 120-request/60-second quota; the placeholder value was absent.

`python -m sparkle serve` with a non-loopback host and authentication disabled
exited 1 before binding. Required authentication with no token also exited 1
before binding. Both messages were concise and contained no traceback or
credential value.

The live MiniMax smoke command exited 2 at credential presence with
`configured: false` and `secret_value_exposed: false`; no provider request was
made, so this remains BLOCKED rather than PASS.

The first composite smoke wrapper had a shell quoting error after its successful
status command. The simpler rerun produced all results above; this was a test
harness error, not an application failure.

## Verified v0.7 capability paths

- Every API method consumes a per-client fixed-window quota before origin or
  authentication checks, including OPTIONS requests.
- Client buckets are protected by a lock, expire by window, and are capped at
  10,000 entries with deterministic stale/oldest eviction.
- Quota headers accompany API responses; blocked requests return HTTP 429 and
  `Retry-After` without reaching authorization or application state.
- One API audit record is attempted before each API response. The store accepts
  only method, query-free `/api/` path, status, coarse outcome, bounded
  duration, and timestamp.
- Unknown API paths are normalized to `/api/[unknown]` in both audit records
  and request logs so attacker-controlled path segments are not retained.
- Audit storage is separate from execution traces, and audit failures cannot
  interrupt response delivery.
- System status, `GET /api/audit`, and the dashboard expose only aggregate quota
  configuration and secret-free audit fields.

## Not verified

- A real MiniMax-M3 network response.
- Role/owner authorization, authenticated browser sessions, TLS termination,
  distributed edge rate limiting, configured audit retention, or production
  deployment.
- Execution of generated applications/tests, builds, packaging, or deployment.
- Real voice, wake word, camera, browser automation, GUI computer control, or
  robots.

## GitHub publication and CI

Result: PASS — private repository `pexxoraa/SPARKLE` received v0.7 capability
commit `c379ec4b01f00cf03de6ede7028b7df5bd704a3f` on `main` without a force
update. Its Git tree `42f6ed82862757c88cd989f6b9b7069806b69bbe`
exactly matches the locally tested tree in commit
`1f7bbea8811a259ed2ac06dd00e1bfe784327428`.

SPARKLE CI run #13 (`33228183633`) completed successfully in 24 seconds. Both
matrix jobs, `test (3.12)` and `test (3.13)`, completed successfully, including
the `Compile and test` step.

The documentation checkpoint commit
`d98d90827ac57487b3ffff8b0af6a89fccd2c6e7` was then verified by SPARKLE CI
run #14 (`33228285510`) in 23 seconds; both Python matrix jobs and their
`Compile and test` steps completed successfully.

---

# 0.6.0-alpha.1 verification report

Date: 2026-08-29 UTC

## Executed commands

### Compile and regression suite

```bash
make check
```

Result: PASS — 54 tests ran in 6.953 seconds; 54 passed, 0 failed,
0 errors. Added evidence covers bearer success/failure, no secret in status or
responses, unauthorized non-mutation, exact same-origin and explicit allowlist
behavior, wildcard/invalid-origin rejection, preflight, boolean configuration,
non-loopback/missing-token startup refusal, and traceback-free console errors.

### Static release checks

```bash
node --check src/sparkle/dashboard/app.js
git diff --check
```

Result: PASS — dashboard JavaScript parsed and the working diff contained no
whitespace errors.

### API-security command smoke

Authenticated `sparkle status` with a fake test token exited 0 and reported only
`authentication_required: true`, `token_configured: true`, an allowed-origin
count, and `credentials_exposed: false`. The token text was absent from output.

`python -m sparkle serve` with a non-loopback host and no authentication exited
1 before binding with `Non-loopback API binding requires authentication`.
Required authentication with no token also exited 1 before binding. Both
refusals contained no traceback or secret value.

### Live-provider smoke test

```bash
SPARKLE_DATA_DIR=<fresh-directory> PYTHONPATH=src python3 -m sparkle smoke-test --live
```

Result: BLOCKED — process exited 2 at `credential_presence`, reported
`configured: false` and `secret_value_exposed: false`, and made no MiniMax
request. This is not a live-provider PASS.

## Verified v0.6 capability paths

- Optional bearer authentication protects every `/api/` route before request
  bodies are read or state is accessed.
- Tokens are resolved only from configured environment secret references and
  compared in constant time; status returns presence booleans only.
- Same-origin requests are allowed; cross-origin requests require an exact
  configured HTTP(S) origin; wildcard and malformed origins are rejected.
- Origin-approved preflight advertises only GET, POST, OPTIONS, Authorization,
  and Content-Type.
- Required authentication without a token fails server startup, and a
  non-loopback bind is refused unless authentication is required and configured.

## Not verified

- A real MiniMax-M3 network response.
- Role/owner authorization, authenticated browser sessions, TLS termination,
  rate limiting, or production deployment.
- Execution of generated applications/tests, builds, packaging, or deployment.
- Real voice, wake word, camera, browser automation, GUI computer control, or
  robots.

## GitHub publication and CI

Result: PASS — private repository `pexxoraa/SPARKLE` received v0.6 capability
commit `b003f4caaef856014e176841ab086f0c54aae0a1` on `main` without a force
update. Its Git tree `fb593326823b9bcb8956f9e37a7ae717b6880689`
exactly matches the locally tested tree in commit
`a090c2bd8e2fc0767d771c1745d8064d0d857258`.

SPARKLE CI run #11 (`33227542117`) completed successfully in 17 seconds. Both
matrix jobs, `test (3.12)` and `test (3.13)`, completed successfully, including
the `Compile and test` step.

Documentation evidence commit
`a2d31ca84693ab3884b99ac81d5aca70ffabf822` also passed SPARKLE CI run #12
(`33227624913`) in 14 seconds; both Python matrix jobs and their compile/test
steps succeeded.

---

# 0.5.0-alpha.1 verification report

Date: 2026-08-29 UTC

## Executed commands

### Compile and regression suite

```bash
make check
```

Result: PASS — 47 tests ran in 4.910 seconds; 47 passed, 0 failed,
0 errors. The added coverage verifies Python compilation without execution,
JavaScript and JSON validation, syntax-failure evidence, missing-Node handling,
path traversal and symlink rejection, undeclared-field/type rejection, explicit
approval, API integration, persistence, and a CLI scaffold-to-verify workflow.

### Static release checks

```bash
node --check src/sparkle/dashboard/app.js
git diff --check
```

Result: PASS — dashboard JavaScript parsed and the working diff contained no
whitespace errors.

### Isolated runtime status

```bash
SPARKLE_DATA_DIR=<fresh-directory> PYTHONPATH=src python3 -m sparkle status
```

Result: PASS — process exited 0 and reported version `0.5.0-alpha.1`, 16
built-in agents, eight registered tools, ready verification storage,
`static_verification: true`, and `arbitrary_command_execution: false`.

### Live-provider smoke test

```bash
SPARKLE_DATA_DIR=<fresh-directory> PYTHONPATH=src python3 -m sparkle smoke-test --live
```

Result: BLOCKED — process exited 2 at `credential_presence` with
`configured: false` and `secret_value_exposed: false`. No MiniMax request was
made; this is not a live-provider PASS.

## Verified v0.5 capability paths

- Generated workspaces can be checked with `python_compile`,
  `javascript_syntax`, and `json_parse` only.
- Python is compiled without module execution; JavaScript uses Node `--check`;
  JSON uses the standard parser.
- Project paths reject traversal, missing files, symlinks, wrong file types,
  undeclared fields, more than 50 checks, and files over 500 KB.
- Node runs from an absolute discovered binary, without a shell or inherited
  provider secrets, with a five-second timeout and 8,000-character output cap.
- Verification results and durations persist outside source code and appear in
  the CLI, API, dashboard, agent tools, and system status.

## Not verified

- A real MiniMax-M3 network response.
- Execution of generated applications or tests, package installation, builds,
  packaging, or deployment.
- Production service scheduling or external notification delivery.
- Production deployment, authentication, and authorization.
- Real voice, wake word, camera, browser automation, GUI computer control, or
  robots.

## GitHub publication and CI

Result: PASS — private repository `pexxoraa/SPARKLE` received v0.5 capability
commit `f0f880e3c011fd8ecae33a572347c399e40a80a6` on `main` without a force
update. Its Git tree `bfaaec45474c385327bc430b5be2cddd9124a16b`
exactly matches the locally tested tree in commit
`d0f31c9b8f0c03f155032b48b25c57bf9c5690cc`.

SPARKLE CI run #9 (`33227000794`) completed successfully in 14 seconds. Both
matrix jobs, `test (3.12)` and `test (3.13)`, completed successfully, including
the `Compile and test` step.

---

# 0.4.0-alpha.1 verification report

Date: 2026-08-29 UTC

## Executed commands

### Compile and regression suite

```bash
make check
```

Result: PASS — latest release-state run executed 41 tests in 4.293 seconds;
41 passed, 0 failed,
0 errors. Coverage added for persistent generated-agent lifecycle, bounded
application workspaces, automation claiming/execution/retry/recurrence/cooldown
and history, memory restore/export/delete/backup, and knowledge
list/delete/backup.

### Static release checks

```bash
node --check src/sparkle/dashboard/app.js
git diff --check
```

Result: PASS — dashboard JavaScript parsed successfully and the working diff
contained no whitespace errors.

### Isolated runtime status

```bash
SPARKLE_DATA_DIR=<fresh-directory> PYTHONPATH=src python3 -m sparkle status
```

Result: PASS — process exited 0 and reported version `0.4.0-alpha.1`, 16
built-in agents, seven registered tools, ready generated-agent/automation/build
stores, zero initial records, and `arbitrary_command_execution: false`. Overall
status was correctly `limited` because the MiniMax credential was absent.

### Live-provider smoke test

```bash
SPARKLE_DATA_DIR=<fresh-directory> PYTHONPATH=src python3 -m sparkle smoke-test --live
```

Result: BLOCKED — process exited 2 at `credential_presence` with
`configured: false` and `secret_value_exposed: false`. No provider request was
made. This is not a live-provider PASS.

## Verified v0.4 capability paths

- Generated agents validate, persist outside source, hot-load, route, reload,
  replace, and remove while built-ins remain protected.
- Agent installation and workspace scaffolding require explicit approval.
- Workspaces reject traversal, symlinks, unsafe names, unapproved overwrite,
  oversized files, and oversized manifests; file hashes are recorded.
- Once/daily/weekly/conditional automations claim work, run single or multiple
  agents, retry within bounds, record execution evidence, reschedule, and honor
  condition cooldowns.
- Automation execution traces use input source `automation`.
- Memory supports archive, restore, permanent delete, export, and database
  backup; knowledge supports source listing, source deletion, and backup.
- The CLI, HTTP API, system status, and dashboard expose the new capabilities.

## Not verified

- A real MiniMax-M3 network response.
- Arbitrary build/test execution, packaging, or deployment.
- Production service scheduling or external notification delivery.
- Production deployment, authentication, and authorization.
- Real voice, wake word, camera, browser automation, GUI computer control, or
  robots.

## GitHub publication and CI

Result: PASS — the private repository `pexxoraa/SPARKLE` received v0.4
capability commit `d5984f709b3a0bd67b0131e4306e2c00498ef514` on `main` without
a force update. Its Git tree
`f472afe902d8bd902cddf7a7a4eb3f954cd9d555` exactly matches the locally tested
tree in commit `027c19a4649483086d55a42f0853a0e8c37a0ee8`.

SPARKLE CI run #7 (`33226436851`) completed successfully in 15 seconds. Both
matrix jobs, `test (3.12)` and `test (3.13)`, completed successfully, including
the `Compile and test` step. The workflow reported no artifacts and no
annotations.

---

# 0.3.0-alpha.1 verification report

Date: 2026-08-28 UTC

## Executed commands

### Environment inspection

Executed OS, CPU, RAM, storage, language/toolchain, GPU, audio, browser, Docker,
and editor checks. Recorded results are in `ENVIRONMENT.md`.

### Compile and regression suite

```bash
make check
```

Latest post-CI-upgrade result: PASS — 32 tests ran in 2.497 seconds; 32 passed,
0 failed, 0 errors.

An earlier `make check` attempt failed during test discovery with five
`ModuleNotFoundError: sparkle` errors because the Makefile omitted
`PYTHONPATH=src`. The Makefile was corrected and the exact command was rerun to
the passing result above.

### Runtime status

```bash
python3 -m sparkle status
```

Result: PASS — process exited 0; model registry, 16 agents, five tools, memory,
knowledge, tracing, automation, voice state, proactive state, and presence state
were reported. Overall runtime state was correctly `limited` because no accepted
MiniMax secret reference exists in the build process.

### Live-provider smoke test

```bash
python3 -m sparkle smoke-test --live
```

Result: BLOCKED — process exited 2 at `credential_presence`; configured was
false and `secret_value_exposed` was false. No API request was made. This is not
a live-provider PASS.

### Secret-pattern inspection

Searched tracked candidate files for `sk-` and `Bearer` patterns. Matches were
limited to documentation placeholders, runtime header construction, and fake
test fixtures. No credential value was found.

## Verified paths

- Model mapping, response parsing, retries, streaming, and tool state.
- Registry add/remove/enable/disable/activate.
- Memory upsert/search/archive and category boundaries.
- Knowledge ingest/chunk/search and format rejection.
- Trace sequence, success/failure metadata, and redaction.
- Automation due selection and proactive deadline alerts.
- Calculator AST and file-path confinement.
- Agent routing, tool loop, multi-agent synthesis.
- HTTP health/chat/memory/knowledge/static dashboard and security headers.

## Not verified

- Real MiniMax network response.
- Production deployment.
- Voice, wake word, camera, browser automation, GUI computer control, or robots.

## GitHub publication

Result: PASS — the source is published to the private repository
`pexxoraa/SPARKLE` on branch `main`. Connector access was limited to the
authorized account and the target repository; no unrelated repository was
modified.

The remote foundation tree
`dd4bd9833f9675cc8333065d2487d5dfb2317312` exactly matches local foundation
commit `d5c001be05193411d7b90b03d09390e2702f8e82`. The imported release-state tree
`66ccd2f802d93e6a0e91494db693936141e64aa9` exactly matches local commit
`01f8e816a55513e647674c21ea12c1ef6e495db2` and is recorded remotely in commit
`9561b1208e5c44d744bf7293fef8a7c6f7ee7361`.

Because the target was an empty repository and the connector's commit API
requires an existing parent, publication includes one bootstrap commit before
the imported foundation and release-state commits. This changes commit IDs but
not the verified file trees.

## GitHub Actions

Result: PASS — SPARKLE CI run #5 completed successfully in 15 seconds for
commit `32be63286ca0ce9b5dd07eea6b07c4942a93a5a9`. Both matrix jobs passed on
Python 3.12 and Python 3.13. The workflow uses `actions/checkout@v7` and
`actions/setup-python@v7`; the successful run reported no annotations.


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

## Bounded orchestration and continuous backlog — 2026-09-09

Started from published `b74be146296175d74738479af89c296905f44be5` after fetch and
fast-forward verification. Found that round limits did not bound tools per response
and explicit specialist lists had no count/uniqueness bound. Requests now share a
validated tool-attempt budget across specialists and synthesis; oversized batches
are rejected before any action in that batch. Failed attempts count. Previously
completed actions are not rolled back. Explicit duplicate/oversized specialist
lists fail before model invocation. Existing tool permission checks remain intact.

Fresh baseline: 387 passed + 1 optional live skip (388 total), 58.040 seconds.
Final full suite: 394 passed + 1 optional live skip (395 total), 63.926 seconds.
Focused orchestrator/API/configuration suite: 46/46, 14.397 seconds. Seven new
regressions test batch atomic refusal, cumulative and shared limits, failure
accounting, fresh request state, specialist validation and configuration bounds.
Wheel build/fresh offline installation, compile/JavaScript and current-tree audits
passed. Scripted agent outcomes and retrieval metrics remain exactly unchanged.

[Machine-readable capability backlog](capability_backlog.json) records all 46
categories, priorities, blockers, next actions, tests and acceptance requirements.
Next implementable work is staged independently validated memory updates. Global
wall-time budgeting and action idempotency remain distinct unfinished concerns;
tool-count limits alone do not solve them. No new version or competence claim.
Live benchmark diagnosis still needs the missing host evidence; no live rerun.
Level 3 remains BLOCKED/PARKED. Deployment remains FROZEN.

## Literal memory-query correction — 2026-09-09

Continued from `5bbe4f0d2a76fc330f1da7fc040e98910993c1a7` after its CI #89
passed all five jobs. A deterministic probe showed that Japanese and punctuation
queries each returned one unrelated recent record. Memory search now supports
literal Unicode tokens, escapes underscores, limits distinct terms to 64, and
returns no matches for nonempty unsearchable queries. Blank-query recent behavior
is preserved. Context integration proves unrelated memory is not injected for the
Unicode query. This is lexical correctness, not semantic quality or new authority
to write memory.

Baseline at the preceding verified checkpoint: 394 passed + 1 optional live skip
(395 total). New focused memory/storage/retrieval tests: 25/25, 0.183 seconds.
Final full suite: 399 passed + 1 optional live skip (400 total), 61.198 seconds.
Five new regressions exercise Unicode, punctuation/blank distinction, wildcard
literalness, term/result/category/archive bounds and context behavior. Wheel and
fresh offline installation, compile/JavaScript, documentation and tracked-tree
audits passed. Scripted agent outcomes and retrieval metrics remain unchanged.
Memory stays IMPLEMENTED BUT INSUFFICIENTLY VERIFIED; Unicode case folding and
semantic retrieval are not claimed. Staged validated memory updates remain next
in the machine-readable backlog. No live benchmark was rerun, no version changed,
and Level 3 remains BLOCKED/PARKED with deployment FROZEN.

## Independent operator review for agent memory

Continued from `4831615033e4aaa54cc6861da6ee6fc06561584a`. Default agent
`memory_write` now stages bounded proposals excluded from retrieval; CLI/API
review approves the exact digest and prior row state. Expiry, tampering, stale
overwrite and duplicate/concurrent reviews fail closed. Approval and memory
update commit atomically. Traces link proposal IDs without proposal values.
Direct operator writes remain supported. Automated factual validation is not
implemented; memory capability is not upgraded to fully verified.

Fresh verification: baseline 400 tests (399 passed, 1 optional live skip),
58.244 seconds. Focused review/orchestration/CLI/API/security: 40/40 passed,
3.299 seconds. Full suite: 411 tests (410 passed, 1 optional live skip),
59.607 seconds. Eleven new tests. Deterministic retrieval and agent outcomes
unchanged; the benchmark explicitly uses its legacy direct-write fixture tool,
so these metrics are not evidence for default staged writes. Task definitions,
scoring, validators and NVIDIA configuration unchanged.

Compile, dashboard JavaScript, whitespace, 190-file credential-pattern/path/
symlink/oversized-file audit passed. Wheel built with no dependency downloads;
fresh offline installation and installed CLI help passed. Wheel SHA256:
`16df3c14192b3f61e160cd1f16b5e79ab554267853feebf72ccf54ced1c164e9`.
Version remains 0.30.0a1.

Current user-supplied real Nemotron baseline: 12 tasks executed, 3 validated,
9 rejected (25%). This supersedes the earlier 8.33% historical run; no live
benchmark was rerun here. Agent competence is not established. Level 3 remains
BLOCKED/PARKED; deployment FROZEN. Next: trusted machine-observed evidence for
memory validation, retention policy, and user-facing review workflow quality.

## Pending memory review queue

Continued from `0c1882ebb7b98d187f273873b3bb613a34c9a009` (CI #91 passed).
Default listing now selects pending proposals oldest first; completed reviews
cannot bury pending work. CLI `--status` and API `?status=` expose bounded
approved/rejected/all history. Authorization and exact-digest checks unchanged.
Two new regression tests plus CLI/API integration assertions.

Focused queue/CLI/API/security: 34/34 passed (3.149 seconds). Initial full
run: 413 tests, 411 passed, one transport deadline error, one optional live
skip. The isolated existing deadline suite then passed 9/9 (3.274 seconds).
An incomplete-summary run is not counted as passed. A subsequent diagnostic
runner from stdin caused multiprocessing spawn import failures (`<stdin>`);
that runner was replaced with a guarded file-based runner, without altering
SPARKLE timeout code or tests. Final full run: 413 tests, 412 passed, one
optional live skip, zero failures/errors (65.616 seconds). The initial timing
failure is retained as observed intermittent test evidence, not explained away.

Compile, JavaScript syntax, whitespace and 190-file credential-pattern/path/
symlink/size audits passed. Fresh wheel and offline installation passed. Wheel
SHA256: `e5792b8f706219a6734af9a5064d2a61aad6ecc6ae74d19214ae7489524c5a04`.
No benchmark task/scoring/validator/model configuration change; no live rerun.
Current user-supplied real-agent baseline remains 3/12 validated, 9 rejected
(25%); competence unverified. Level 3 BLOCKED/PARKED; deployment FROZEN.
Automatic factual memory validation, retention, and dashboard review remain
unfinished. The proposal lifecycle does not establish truth of an agent claim.

## Operator-attested factual memory validation

Base: bcf1a4ebb002a95ef49aa9e61225aada8cc9d0cd. Exact operator-attested
field claims now receive VERIFIED / REJECTED / INCONCLUSIVE evidence. Approval
remains separate; strict retrieval rechecks current facts after revocation,
expiry or conflicts. General semantic truth and external source verification
are not claimed. See MEMORY.md for the trust contract and limitations.

Baseline: 413 tests, 412 passed, one optional live skip (62.786 seconds).
Focused memory/resource/security/API/CLI: 69/69 (6.783 seconds).
Full suite: 424 tests, 423 passed, one optional live skip, zero failures/errors
(77.422 seconds). Eleven added tests. Deterministic benchmark outcomes unchanged.
Compile, dashboard syntax, whitespace and 192-file secret-pattern/path/symlink/size
audit passed. Fresh offline wheel installation and installed CLI help passed.
Wheel SHA256: `177c4e2baa1b289640b208257bda6c7e83f049f2fab3d206987c6bf09eb5d5c8`. Version unchanged.
No live benchmark or host acceptance run. Current user-supplied live baseline:
3 validated / 9 rejected (25%); agent competence unverified. Level 3 stays
BLOCKED/PARKED; deployment FROZEN. Retention and dashboard review are next.

## Memory retention and version history

Base: a22a1fba70a45530c5db59ab523232652c5f2713 (CI #93 passed).
Explicit expiry/revocation policies now exclude records before retrieval limits.
Restoration/upsert cannot bypass revoked/expired eligibility. Transactional
version snapshots preserve supersession and deletion history; migration captures
one baseline without inventing older revisions. See MEMORY.md for privacy and
audit limits. This is not cryptographic tamper-proof storage or privacy erasure.

Focused memory/resource/API/CLI/security suite: 78/78 passed (6.889 seconds).
Final full suite: 433 tests, 432 passed, one optional live skip, zero failures
or errors (85.372 seconds), recorded by the guarded file-based runner. An earlier
ordinary runner returned an incomplete summary and was not counted as passed.
Nine new tests; deterministic benchmark outcomes unchanged. Compile, JavaScript
syntax, whitespace, fresh wheel/offline installation and installed CLI help passed.
Wheel SHA256: fe604e96b264ca096a444f8c95c00884a8d476e1f9c3c690a1042fb81d28d4c3.
No live/host run, task/scoring change or version increase. Current real-agent
baseline remains user-supplied 3/12 validated (25%); competence unverified.
Level 3 BLOCKED/PARKED, deployment FROZEN. Dashboard review is next.
