# Agent Builder

The Agent Builder specializes in purpose, capability, tool, memory, model,
workflow, guardrail, testing, and deployment requirements. Agent definitions are
data-driven `AgentSpec` records, so installing a new generated agent does not
change the orchestrator.

Generated-agent manifests are validated, stored in
`data_environment/generated_agents.sqlite3`, hot-loaded into routing, and
reloaded at process startup. Unknown tools, invalid capabilities, duplicate
names, and attempts to replace built-in agents are rejected. Installation,
replacement, and removal require an explicit approval flag through the tool,
CLI, or API.

```bash
sparkle agent-install agent.json --approve
sparkle agent-remove robotics_research --approve
```

A manifest contains `name`, `capability`, `purpose`, `instructions`, `tools`,
and routing `keywords`. `--replace` updates an existing generated definition.

The runtime does not yet turn a natural-language request into source code,
evaluation fixtures, and a deployed external service without review. The
verified capability is persistent runtime-agent installation, not fully
autonomous agent engineering.
