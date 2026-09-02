# SPARKLE

**Strategic Personal AI for Research, Knowledge, Learning, and Execution**

SPARKLE is a model-agnostic personal AI foundation with a configurable model
registry, provider adapters, specialist agents, persistent memory, a separate
knowledge index, execution traces, automations, proactive rules, a CLI, an HTTP
API, and a local dashboard.

Current release: `0.30.0-alpha.1`. This is a tested foundation release, not the
final system described in the long-term Definition of Done. See
[`docs/BUILD_STATE.md`](docs/BUILD_STATE.md) and
[`docs/ACCEPTANCE.md`](docs/ACCEPTANCE.md) for exact evidence and gaps.

## What works now

- Provider-neutral model, request, response, tool, and routing contracts.
- Deterministic `SPARKLE-CONTENT/1` envelopes for bounded text, image, audio,
  document, and mixed-modality requests. Contract transport and tracing are
  tested; semantic non-text understanding awaits a capable provider adapter.
- NVIDIA Nemotron 3.5 Lightning is the primary configured model through a
  standard-library NIM Chat Completions adapter. MiniMax remains a disabled
  legacy adapter; neither provider is imported by the core.
- Evidence-based model health, capability/modality/tool/stream/latency/timeout
  request policy, explicit fallback, and content-free usage records.
- Model registry with add, remove, enable, disable, activate, route, inspect,
  and credential-presence checks.
- Personal, Learning, Skill, Exam, Research, Coding, Software Engineering,
  Application Builder, AI Builder, Agent Builder, Project, Data Analysis,
  Content, Productivity, Automation, and System agents.
- Single-agent and multi-agent orchestration with bounded tool execution.
- Deterministic `SPARKLE-AGENT-BLUEPRINT/1` requirements-to-manifest generation,
  static routing fixtures, explicit approval, persistent installation,
  hot-loading, removal, and routing.
- Approval-gated `SPARKLE-AGENT-EVALUATION/1` response-contract runs through
  an isolated no-context/no-tool orchestrator profile with content-free
  persisted evidence.
- Provider-neutral `SPARKLE-AI-SYSTEM-BLUEPRINT/1` requirements validation,
  registry-backed model capability/modality routing, agent/tool access checks,
  deterministic manifests, explicit approval, bounded workspace
  materialization, and safe persisted attempt evidence.
- Approval-gated `SPARKLE-AI-SYSTEM-DRAFT/1` natural-language-to-structured-
  requirements conversion through the shared model router and isolated no-
  context/no-tool execution profile, followed by exact JSON and full Blueprint
  validation with bounded content-free evidence. Deterministic adapter tests
  pass; live-provider semantic quality is not yet verified.
- Deterministic `SPARKLE-AI-SYSTEM-IMPLEMENTATION-PLAN/1` derivation from a
  revalidated Blueprint, with provider-neutral architecture inputs, bounded
  proposed source/evaluation paths, ordered work and release gates, explicit
  human-review state, approval-gated plan-only workspace materialization, and
  content-free evidence. It does not generate source or execute evaluations.
- Bounded `SPARKLE-AI-SYSTEM-SOURCE-CANDIDATE/1` generation with separate
  provider disclosure, human review, static verification, final approval, and
  isolated candidate storage.
- Provider-neutral `SPARKLE-AI-SYSTEM-RUNTIME-EVALUATION/1` contracts through
  the authenticated external-worker boundary, with distinct lifecycle and
  failure evidence and no false isolation claim.
- `SPARKLE-AI-SYSTEM-SOURCE-PROMOTION/1` binds a separate post-evaluation
  approval to exact identities and atomically copies unchanged candidate source
  into dedicated controlled staging. It stops before build, package, publish,
  production replacement, or deployment.
- Provider-neutral `SPARKLE-PROJECT/1` project state with strict lifecycle,
  priority/deadline/dependency/risk/milestone/blocker/next-action validation,
  optimistic updates, approval-gated archive, content-free change evidence,
  proactive alerts, least-privilege agent reads, API/CLI, and dashboard access.
- Provider-neutral `SPARKLE-SKILL/1` mastery records whose levels 0–6 are
  derived only from bounded verified evidence, with duplicate protection,
  optimistic metadata updates, approval-gated archive, least-privilege agent
  summaries, proactive integration, API/CLI, and dashboard access.
- SQLite memory, knowledge, trace, and automation stores in separate paths.
- Executable once/daily/weekly/conditional automations with retry, rescheduling,
  run history, and automation-origin traces.
- A separately installable supervised automation service with a no-follow
  single-instance lock, expiring claims, crash recovery records, stale-runner
  fencing, persisted health, SIGTERM draining, and a hardened systemd profile.
- Evidence-backed proactive rules for deadlines, schedule conflicts, research
  revisions, weak learning, revision, incomplete projects, and repeated
  mistakes. Rules read only validated structured evidence, expose bounded
  metadata without memory or research text, and can trigger strictly validated
  conditional automations with cooldowns.
- A provider-neutral notification contract with bounded dashboard delivery,
  deduplication, unread/read state, API/UI access, automation actions, and
  content-free execution traces.
- Bounded application workspace scaffolding with path confinement, size limits,
  overwrite protection, and explicit approval.
- Persistent, approval-gated workspace verification with non-executing Python
  compile, JavaScript syntax, and JSON parse checks.
- Disabled-by-default, approval-gated Python unittest execution for dedicated
  secret-free POSIX workers, with fixed commands and bounded evidence.
- A separately deployable external fixed-test worker with exact signed schemas,
  replay/idempotency storage, bounded concurrency, secret-file support,
  fail-closed Bubblewrap preflight, and a deliberately unisolated loopback-only
  development executor. Container/Caddy and hardened systemd profiles are
  included; live namespace isolation still requires deployment-host evidence.
- Deterministic, content-addressed application ZIP artifacts with embedded
  SHA-256 manifests, immutable integrity checks, portable-path validation, and
  explicit approval. Append-only deployment events remain unverified evidence;
  they do not execute or claim an external deployment.
- Controlled execution authorizes one exact immutable controlled-build artifact,
  verifies and safely extracts it, submits it through the authenticated worker,
  and verifies an identity-bound result. Execution, verification, publication,
  deployment, and production modification remain distinct states. Local worker
  execution is demonstrated; Bubblewrap isolation is not verified on this host.
- Text/Markdown/source-code ingestion; optional PDF and DOCX ingestion.
- Dashboard and JSON API served with Python's standard library.
- Optional secret-resolved bearer authentication, exact origin controls, and
  fail-closed non-loopback binding policy for the JSON API.
- Bounded, expiring dashboard sessions with HttpOnly same-site cookies, per-
  session CSRF protection, logout/revocation, and no browser token storage.
- Bounded per-client API rate limiting and a separate secret-free API audit
  database with dashboard visibility.
- Voice and motion/presence interfaces that do not couple the core to hardware.
- Fail-closed browser/computer interaction contracts with exact HTTPS
  allowlists, bounded results, and typed GUI actions. Only deterministic test
  harnesses exist; no live browser or GUI execution is claimed.
- Unit, integration, API, security-boundary, and deterministic end-to-end tests.

## Quick start

Requirements: Python 3.12 or newer.

```bash
python3 -m venv .venv
source .venv/bin/activate
python3 -m pip install -e .
sparkle status
sparkle serve
```

Open `http://127.0.0.1:8765`.

For PDF and DOCX ingestion:

```bash
python3 -m pip install -e '.[documents]'
```

## Configure NVIDIA Nemotron

Set `NVIDIA_API_KEY` outside source control. `SPARKLE_LLM_API_KEY` remains a
provider-neutral deployment alias. Live Nemotron has not been verified in the
published build because no key was available.

```bash
export NVIDIA_API_KEY='configured-outside-source'
sparkle smoke-test --live
```

The smoke test reports presence, provider/model metadata, token usage, latency,
and an exact response match. It never prints the key.

## Test

```bash
make check
```

Full documentation starts at [`docs/USER_GUIDE.md`](docs/USER_GUIDE.md).
The multimodal contract is specified in
[`docs/MULTIMODAL.md`](docs/MULTIMODAL.md).
Worker deployment and security evidence are documented in
[`docs/WORKER.md`](docs/WORKER.md).
Controlled execution contracts, lifecycle, limits, and evidence levels are in
[`docs/EXECUTION.md`](docs/EXECUTION.md).
Dashboard notification contracts are documented in
[`docs/NOTIFICATIONS.md`](docs/NOTIFICATIONS.md).
Structured project contracts are documented in
[`docs/PROJECTS.md`](docs/PROJECTS.md).
Evidence-based skill contracts are documented in
[`docs/SKILLS.md`](docs/SKILLS.md).
Browser/computer boundaries are documented in
[`docs/INTERACTION.md`](docs/INTERACTION.md). The capability classification is
in [`docs/FOUNDATION_AUDIT.md`](docs/FOUNDATION_AUDIT.md).
