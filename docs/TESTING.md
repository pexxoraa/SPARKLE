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
Supervised-automation coverage adds legacy-schema migration, expiring claims,
explicit recovery records, old-token fencing, real deterministic orchestrator
execution and traces, singleton lock refusal, mode-0600/no-follow lock policy,
bounded degraded cycles, fresh/stale lifecycle status, pre-requested shutdown,
installed-style CLI check/once/status/health behavior, a real subprocess
SIGTERM drain, and systemd hardening inspection.
Proactive coverage validates exact condition schemas, unknown-field and
unsupported-category rejection, deadline compatibility, structured weak-skill
conditions with cooldown, all six alert types, invalid-evidence suppression,
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

## Phase 33 evidence matrix

| Required category | Executed evidence | Remaining external gap |
|---|---|---|
| Unit | Content, security, stores, routing, tools, services, and validators | None for implemented local units |
| Integration | API, orchestrator/context/model, multimodal, automation, artifact, and worker boundaries | Live provider and deployed external targets |
| System | Composed system, HTTP server, persisted stores, status, dashboard, and service lifecycle | Production identity/TLS/deployment environment |
| Agent | All 16 built-ins plus generated-agent persistence, routing, tools, deterministic execution, and traces | Live-provider response-quality evaluation |
| Model | MiniMax mapping/retry/stream/tool state, registry switching, capability/modality routing, deterministic adapter | Live MiniMax credentialed smoke call |
| Memory | CRUD, search, archive/restore, structured proactive evidence, and backup | Production retention/encrypted backup policy |
| Tool | Allowlists, schemas, bounds, approval, confinement, execution, and failure paths | Disabled web/browser/computer adapters |
| Voice | Disabled failures, adapter injection, and shared-core contract | Real STT/TTS and microphone/speaker hardware |
| Application | Scaffold, static verification, fixed tests, artifacts, worker protocol/service, API/CLI/dashboard | Target-specific build and deployment adapters |
| AI system | Single/multi-agent orchestration, tool loop, generated agents, model independence, multimodal transport | Autonomous requirements-to-deployment evaluation |
| End-to-end | HTTP chat, automations, workspace flows, and client → worker → child unittest → signed result | Live provider, remote isolation, and external actions |
| Regression | Exact `make check` gate on the full standard-library suite | None for implemented local behavior |

`PASS` in this matrix means an executable local path exists and ran. It does
not convert an external or hardware-dependent requirement into a pass.

Documentation regression coverage verifies the complete master-directive file
inventory, repository-confined relative Markdown links, package/display version
consistency, required build-state fields, and continued `PARTIAL`/`BLOCKED`
honesty in acceptance reporting.

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
GitHub CI run #32 (`33289795885`) passed the 145-test Phase 33 tree on Python
3.12 and 3.13, the separately deployable worker image build/entrypoint, and the
installed automation-service lifecycle. The earlier v0.15 capability run #31
passed the same four job types on the exact multimodal release tree. Remote CI
for the 150-test final checkpoint is pending publication.
