# Data location map

| Data type | Location | Purpose | Owner | Retention | Used by |
|---|---|---|---|---|---|
| API key | Hosting/OS secret manager | Provider authentication | User | Until rotated/deleted | Secret resolver, provider adapter |
| API bearer token | Hosting/OS secret manager | SPARKLE API authentication | User | Until rotated/deleted | API access policy |
| Dashboard session ID digest and CSRF token | Bounded process memory only | Same-origin dashboard authentication | API server | Absolute TTL, eviction, logout, or restart | Session manager/API guard |
| Model config | `ai_environment/configurations/models.json` | Registry and routing | System owner | Versioned | Model registry/router |
| App config | `application/config.json` | Runtime policy | System owner | Versioned | System composition |
| User profile/goals | Memory SQLite | Personal context | User | Until archived/deleted | Context and personal agents |
| Documents/papers | Knowledge SQLite | Retrieval | User | Until source deletion | Knowledge/context system |
| Generated agents | `data_environment/generated_agents.sqlite3` | Persistent runtime agent definitions | User | Until replaced/deleted | Agent registry/router |
| Automations, claims, runs, and service state | `data_environment/automations.sqlite3` | Schedules, expiring claims, recovery/fencing, execution and lifecycle evidence | User/system owner | Until deleted | Automation engine/service/dashboard |
| Automation service lock | `data_environment/automation-service.lock` | Prevent concurrent local service instances | System owner | Persistent mode-0600 inode | Automation service |
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
| API audit | `trace_environment/api_audit.sqlite3` | Secret-free HTTP outcome evidence | System owner | Policy not yet configured | API/dashboard/system status |
| Rate-limit buckets | Bounded process memory only | Per-client request quota | API server | One fixed window/eviction | API guard |
| Source code | Git repository | Product implementation | System owner | Git history | Development/build |
