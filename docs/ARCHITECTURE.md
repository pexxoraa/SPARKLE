# Architecture

```mermaid
flowchart TD
    UI["Text / image / audio / document"] --> Content["Content contract"]
    Content --> Core["Core orchestrator"]
    Core --> Context["Context builder"]
    Context --> Stores["Memory + knowledge"]
    Core --> Agents["Agent registry"]
    Agents --> Router["Model router"]
    Router --> Adapter["Provider adapter"]
    Core --> Tools["Allowlisted tools"]
    Core --> Trace["Trace environment"]
```

The public model contract is in `contracts.py` and `model.py`. The MiniMax
protocol is isolated in `providers/minimax.py`. Agents select capabilities such
as `reasoning` or `coding`; the model router maps capabilities to registry IDs.
No agent imports a MiniMax class.

`content.py` defines the provider-neutral `SPARKLE-CONTENT/1` envelope. Legacy
string messages remain strings and serialize exactly as before. Explicit
envelopes carry bounded text, image, audio, or document parts into the same
context, agent, routing, request, adapter, and trace path. Adapters declare
their supported modalities and validation fails closed before a provider call.
The MiniMax adapter remains text-only; a future adapter can add non-text
provider mapping without changing orchestration, agents, stores, or interfaces.
See `MULTIMODAL.md` for the exact contract and evidence boundary.

## Runtime composition

`SparkleSystem` constructs independent stores, registries, the context builder,
tool registry, orchestrator, voice service, presence engine, proactive engine,
automation store, notification store, static verifier, and opt-in fixed
workspace test runner.
Structured projects are owned by an independent store. Only a read-only search
tool is exposed to Personal, Project, and Productivity agents; create, update,
and archive remain explicit interface actions. The proactive engine consumes
validated project fields and emits content-free evidence rather than parsing
memory prose.
Structured skill mastery is also owned by an independent store. Its current
level is derived from verified evidence rather than accepted as input. Only
bounded content-free mastery summaries reach Personal, Learning, and Skill
agents; all writes remain explicit interface actions.
The agent-blueprint builder is a separate provider-neutral composition over the
agent registry. It deterministically converts exact structured requirements to
an `AgentSpec`, executes production routing fixtures without registry mutation,
and persists an approved blueprint separately from the installed manifest.
The response evaluator is composed only after the orchestrator exists. It
revalidates the installed blueprint and calls the common router through an
isolated orchestrator profile that disables context and tools. Its evidence
store receives hashes and check metadata, never raw prompts or responses.
The AI System Blueprint builder composes the model, agent, and tool registries
with the bounded workspace manager. Structured capability/modality
requirements resolve against enabled model records without constructing an
adapter. Approved builds materialize a canonical architecture manifest while
preserving the memory, knowledge, data, trace, provider, and secrets
boundaries. It does not call models, run evaluations, or deploy targets.
An independent artifact manager reads bounded application workspaces and emits
deterministic content-addressed ZIPs; it never starts an executable.
The automation service is another independent entrypoint over the existing
automation runner. It adds a POSIX singleton lock, expiring claim tokens,
recovery/fencing, persisted lifecycle health, and signal-driven draining; it
does not duplicate orchestration or introduce command execution.
It also composes an operator-only external-worker client outside the model tool
registry. That client owns bounded source packaging, HTTPS/HMAC protocol
validation, and result persistence. The independently installable
`sparkle-worker` service implements the other side of the fixed protocol; it
has its own configuration, secret resolution, replay database, request
validator, and executor interface. The application never imports or starts the
worker service.
Interfaces call this object; they do not own intelligence.

The production executor builds one immutable Bubblewrap command with a
read-only runtime, a single writable ephemeral workspace, cleared environment,
all namespaces unshared, no network namespace interface, and the trusted
unittest runner. Readiness is false unless an executable preflight confirms the
host filesystem is hidden, the environment is allowlisted, and outbound
network connection fails. A separate process executor exists for loopback
protocol testing only and always reports filesystem/network isolation false.

The HTTP boundary composes an independent bearer access policy, bounded rate
limiter, secret-free audit store, and process-local browser-session manager.
Dashboard sessions wrap the API boundary only; agents, models, memory, tools,
and orchestration do not depend on cookie or browser implementation details.

## Storage boundaries

- `var/memory_environment/memory.sqlite3`
- `var/knowledge_environment/knowledge.sqlite3`
- `var/data_environment/automations.sqlite3`
- `var/data_environment/notifications.sqlite3`
- `var/data_environment/generated_agents.sqlite3`
- `var/data_environment/agent_blueprints.sqlite3`
- `var/data_environment/agent_evaluations.sqlite3`
- `var/data_environment/ai_system_blueprints.sqlite3`
- `var/data_environment/projects.sqlite3`
- `var/data_environment/skills.sqlite3`
- `var/data_environment/automation-service.lock`
- `var/data_environment/builds.sqlite3`
- `var/data_environment/verifications.sqlite3`
- `var/data_environment/test_runs.sqlite3`
- `var/data_environment/external_worker_runs.sqlite3`
- `var/data_environment/artifacts.sqlite3`
- `var/data_environment/artifacts/`
- `var/trace_environment/api_audit.sqlite3`
- `var/trace_environment/traces.sqlite3`

The worker owns a separate deployment state root containing only its bounded
job replay database. It does not read the application memory, knowledge, trace,
provider, or secrets databases.

`var/` is excluded from Git and is the source-checkout default. Installed POSIX
packages use the user's XDG state directory. Override either with
`SPARKLE_DATA_DIR`.

## Tool loop

The orchestrator supplies only tools allowed by the selected agent. A model can
request a tool, the registry validates the allowlist, the result is returned as
a tool message, and the full provider response state is preserved for
interleaved thinking. The loop stops after the configured maximum.
