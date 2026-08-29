# SPARKLE

**Strategic Personal AI for Research, Knowledge, Learning, and Execution**

SPARKLE is a model-agnostic personal AI foundation with a configurable model
registry, provider adapters, specialist agents, persistent memory, a separate
knowledge index, execution traces, automations, proactive rules, a CLI, an HTTP
API, and a local dashboard.

Current release: `0.12.0-alpha.1`. This is a tested foundation release, not the
final system described in the long-term Definition of Done. See
[`docs/BUILD_STATE.md`](docs/BUILD_STATE.md) and
[`docs/ACCEPTANCE.md`](docs/ACCEPTANCE.md) for exact evidence and gaps.

## What works now

- Provider-neutral model, request, response, tool, and routing contracts.
- MiniMax-M3 adapter using MiniMax's recommended Messages endpoint directly
  over HTTP. There is no OpenAI package or API dependency.
- Model registry with add, remove, enable, disable, activate, route, inspect,
  and credential-presence checks.
- Personal, Learning, Skill, Exam, Research, Coding, Software Engineering,
  Application Builder, AI Builder, Agent Builder, Project, Data Analysis,
  Content, Productivity, Automation, and System agents.
- Single-agent and multi-agent orchestration with bounded tool execution.
- Persistent generated-agent installation, hot-loading, removal, and routing.
- SQLite memory, knowledge, trace, and automation stores in separate paths.
- Executable once/daily/weekly/conditional automations with retry, rescheduling,
  run history, and automation-origin traces.
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
- Text/Markdown/source-code ingestion; optional PDF and DOCX ingestion.
- Dashboard and JSON API served with Python's standard library.
- Optional secret-resolved bearer authentication, exact origin controls, and
  fail-closed non-loopback binding policy for the JSON API.
- Bounded, expiring dashboard sessions with HttpOnly same-site cookies, per-
  session CSRF protection, logout/revocation, and no browser token storage.
- Bounded per-client API rate limiting and a separate secret-free API audit
  database with dashboard visibility.
- Voice and motion/presence interfaces that do not couple the core to hardware.
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

## Configure MiniMax-M3

Set one server-side environment variable. `MINIMAX_API_KEY` is preferred;
`SPARKLE_LLM_API_KEY` is supported for existing SPARKLE deployments.

```bash
export MINIMAX_API_KEY='configured-outside-source'
sparkle smoke-test --live
```

The smoke test reports presence, provider/model metadata, token usage, latency,
and an exact response match. It never prints the key.

## Test

```bash
make check
```

Full documentation starts at [`docs/USER_GUIDE.md`](docs/USER_GUIDE.md).
Worker deployment and security evidence are documented in
[`docs/WORKER.md`](docs/WORKER.md).
