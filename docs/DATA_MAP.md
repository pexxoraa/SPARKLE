# Data location map

| Data type | Location | Purpose | Owner | Retention | Used by |
|---|---|---|---|---|---|
| API key | Hosting/OS secret manager | Provider authentication | User | Until rotated/deleted | Secret resolver, provider adapter |
| API bearer token | Hosting/OS secret manager | SPARKLE API authentication | User | Until rotated/deleted | API access policy |
| Dashboard session ID digest and CSRF token | Bounded process memory only | Same-origin dashboard authentication | API server | Absolute TTL, eviction, logout, or restart | Session manager/API guard |
| Model config | Checkout `ai_environment/configurations/models.json` or installed runtime `SPARKLE_DATA_DIR/ai_environment/configurations/models.json` | Writable registry and routing | System owner | Versioned/default materialized | Model registry/router |
| App config | Checkout `application/config.json` or installed runtime `SPARKLE_DATA_DIR/application/config.json` | Runtime policy | System owner | Versioned/default materialized | System composition |
| User profile/goals | Memory SQLite | Personal context | User | Until archived/deleted | Context and personal agents |
| Documents/papers | Knowledge SQLite | Retrieval | User | Until source deletion | Knowledge/context system |
| Generated agents | `data_environment/generated_agents.sqlite3` | Persistent runtime agent definitions | User | Until replaced/deleted | Agent registry/router |
| Agent blueprints | `data_environment/agent_blueprints.sqlite3` | Structured requirements outcome and deterministic static-evaluation evidence | User/system owner | Build history; deletion policy not yet configured | Agent Builder/API/CLI/system status |
| Agent response evaluations | `data_environment/agent_evaluations.sqlite3` | Content-free assertion outcomes, response hashes/lengths, provider/model labels, trace links, and safe error types | User/system owner | Latest 1,000 records | Agent evaluator/API/CLI/system status |
| AI system blueprints | `data_environment/ai_system_blueprints.sqlite3` | Canonical provider-neutral architecture plans, static-check outcomes, workspace links, and safe failure types | User/system owner | Latest 1,000 attempts | AI System Builder/API/CLI/system status |
| Structured projects and change evidence | `data_environment/projects.sqlite3` | Versioned status, priority, deadlines, dependencies, risks, milestones, blockers, next actions, archive state, and content-free change events | User/system owner | At most 1,000 active projects and latest 10,000 change events | Personal/Project/Productivity agents, project API/CLI/dashboard, proactive engine |
| Automations, claims, runs, and service state | `data_environment/automations.sqlite3` | Schedules, expiring claims, recovery/fencing, execution and lifecycle evidence | User/system owner | Until deleted | Automation engine/service/dashboard |
| Dashboard notifications | `data_environment/notifications.sqlite3` | Bounded local delivery, deduplication, and read state | User/system owner | Latest 1,000 records | Notification API/dashboard/automation runner |
| Automation service lock | `data_environment/automation-service.lock` | Prevent concurrent local service instances | System owner | Persistent mode-0600 inode | Automation service |
| Proactive alerts | Computed in process from validated memory and knowledge evidence; not separately persisted | Bounded evidence-backed prioritization and conditional automation matching | User/system owner | Recomputed per inspection or runner cycle | Proactive API/dashboard/automation runner |
| Multimodal request content | Validated in-process `SPARKLE-CONTENT/1` envelope; sent only to the selected compatible adapter | Bounded text/image/audio/document input | User | Request lifetime unless an explicit separate memory/knowledge action stores it | API/orchestrator/context/model adapter |
| Application workspaces | Configured applications data root | Bounded generated project files | User | Until operator deletion | Builder agents |
| Application build records | `data_environment/builds.sqlite3` | File hashes, sizes, and scaffold evidence | System owner | Policy not yet configured | Dashboard/builder |
| Workspace verifications | `data_environment/verifications.sqlite3` | Static check results and durations | System owner | Policy not yet configured | Builder agents/dashboard |
| Workspace test runs | `data_environment/test_runs.sqlite3` | Fixed unittest outcomes and bounded redacted output | System owner | Policy not yet configured | Builder agents/API/dashboard |
| External worker signing key | Hosting/OS secret manager | HMAC request/response authentication | User | Until rotated/deleted | Operator-only external worker client |
| External worker source transfer | Configured HTTPS worker request only; not persisted as a bundle | Fixed-test job input | User/operator | Worker policy; absent from SPARKLE result store | External worker |
| External worker runs | `data_environment/external_worker_runs.sqlite3` | Signed-response evidence, bounded output, and declared sandbox claims | System owner | Policy not yet configured | Operator CLI/API/dashboard |
| Application artifacts | `data_environment/artifacts/` | Immutable content-addressed ZIPs with embedded source manifests | System owner | Until operator deletion policy is implemented | Application/AI/Agent Builders, operator CLI/API/dashboard |
| Artifact and deployment records | `data_environment/artifacts.sqlite3` | Package hashes/manifests and append-only unverified external-action reports | System owner | Policy not yet configured | Builders, operator CLI/API/dashboard |
| Execution trace | Trace SQLite | Verification/diagnosis | System owner | Policy not yet configured | Dashboard/system agent |
| Multimodal trace metadata | Trace SQLite, without raw content | Modalities, content-derived IDs, MIME types, byte sizes, hashes, stages, transformations, and outcomes | System owner | Trace retention policy | Orchestrator/dashboard/system agent |
| API audit | `trace_environment/api_audit.sqlite3` | Secret-free HTTP outcome evidence | System owner | Policy not yet configured | API/dashboard/system status |
| Rate-limit buckets | Bounded process memory only | Per-client request quota | API server | One fixed window/eviction | API guard |
| Source code | Git repository | Product implementation | System owner | Git history | Development/build |
