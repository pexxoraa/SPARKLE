# Data location map

| Data type | Location | Purpose | Owner | Retention | Used by |
|---|---|---|---|---|---|
| API key | Hosting/OS secret manager | Provider authentication | User | Until rotated/deleted | Secret resolver, provider adapter |
| API bearer token | Hosting/OS secret manager | SPARKLE API authentication | User | Until rotated/deleted | API access policy |
| Model config | `ai_environment/configurations/models.json` | Registry and routing | System owner | Versioned | Model registry/router |
| App config | `application/config.json` | Runtime policy | System owner | Versioned | System composition |
| User profile/goals | Memory SQLite | Personal context | User | Until archived/deleted | Context and personal agents |
| Documents/papers | Knowledge SQLite | Retrieval | User | Until source deletion | Knowledge/context system |
| Generated agents | `data_environment/generated_agents.sqlite3` | Persistent runtime agent definitions | User | Until replaced/deleted | Agent registry/router |
| Automations and runs | `data_environment/automations.sqlite3` | Schedules, conditions, retries, and execution evidence | User | Until deleted | Automation engine/dashboard |
| Application workspaces | Configured applications data root | Bounded generated project files | User | Until operator deletion | Builder agents |
| Application build records | `data_environment/builds.sqlite3` | File hashes, sizes, and scaffold evidence | System owner | Policy not yet configured | Dashboard/builder |
| Workspace verifications | `data_environment/verifications.sqlite3` | Static check results and durations | System owner | Policy not yet configured | Builder agents/dashboard |
| Execution trace | Trace SQLite | Verification/diagnosis | System owner | Policy not yet configured | Dashboard/system agent |
| API audit | `trace_environment/api_audit.sqlite3` | Secret-free HTTP outcome evidence | System owner | Policy not yet configured | API/dashboard/system status |
| Rate-limit buckets | Bounded process memory only | Per-client request quota | API server | One fixed window/eviction | API guard |
| Source code | Git repository | Product implementation | System owner | Git history | Development/build |
