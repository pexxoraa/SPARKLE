# Data location map

| Data type | Location | Purpose | Owner | Retention | Used by |
|---|---|---|---|---|---|
| API key | Hosting/OS secret manager | Provider authentication | User | Until rotated/deleted | Secret resolver, provider adapter |
| Model config | `ai_environment/configurations/models.json` | Registry and routing | System owner | Versioned | Model registry/router |
| App config | `application/config.json` | Runtime policy | System owner | Versioned | System composition |
| User profile/goals | Memory SQLite | Personal context | User | Until archived/deleted | Context and personal agents |
| Documents/papers | Knowledge SQLite | Retrieval | User | Until source deletion | Knowledge/context system |
| Automations | Data SQLite | Schedules and conditions | User | Until disabled/deleted | Automation engine |
| Execution trace | Trace SQLite | Verification/diagnosis | System owner | Policy not yet configured | Dashboard/system agent |
| Source code | Git repository | Product implementation | System owner | Git history | Development/build |
